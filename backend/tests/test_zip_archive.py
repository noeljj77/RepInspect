import hashlib
import io
import stat
import zipfile

import pytest

from app.services.ingestion.archive import extract_zip
from app.services.ingestion.errors import RepositoryTooLarge, UnsafeArchive
from tests.test_archive import LIMITS, limits, stored_files


def make_zip(files: dict[str, str | bytes], *, prepare=None) -> bytes:
    """A .zip in memory. `prepare(info)` may adjust each entry before it is written."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            if prepare:
                prepare(info)
            zf.writestr(info, content)
    return buffer.getvalue()


def extract(tmp_path, data: bytes, extraction_limits=LIMITS):
    archive = tmp_path / "upload.zip"
    archive.write_bytes(data)
    destination = tmp_path / "out"
    return extract_zip(archive, destination, extraction_limits), destination


def test_a_single_top_level_folder_is_dropped(tmp_path):
    data = make_zip({"shop-main/README.md": "# Shop\n", "shop-main/app/main.py": "print(1)\n"})

    result, out = extract(tmp_path, data)

    assert stored_files(out) == {"README.md", "app/main.py"}
    assert result.kept_count == 2


def test_files_at_the_top_level_are_kept_as_they_are(tmp_path):
    data = make_zip({"README.md": "# Shop\n", "app/main.py": "print(1)\n"})

    _, out = extract(tmp_path, data)

    assert stored_files(out) == {"README.md", "app/main.py"}


def test_each_stored_file_gets_a_hash_of_its_stored_text(tmp_path):
    result, _ = extract(tmp_path, make_zip({"app.py": "print(1)\n"}))

    assert result.files[0].content_hash == hashlib.sha256(b"print(1)\n").hexdigest()


@pytest.mark.parametrize("name", ["../evil.py", "src/../../evil.py", "/etc/passwd", "C:/evil.py"])
def test_paths_that_escape_the_folder_stop_the_import(tmp_path, name):
    with pytest.raises(UnsafeArchive):
        extract(tmp_path, make_zip({"README.md": "# ok\n", name: "x"}))
    assert not (tmp_path / "evil.py").exists()


def test_symlinks_are_never_created(tmp_path):
    def as_symlink(info):
        if info.filename.endswith("link"):
            info.external_attr = (stat.S_IFLNK | 0o777) << 16

    result, out = extract(
        tmp_path, make_zip({"app.py": "x = 1\n", "link": "/etc/passwd"}, prepare=as_symlink)
    )

    assert stored_files(out) == {"app.py"}
    assert result.skipped_counts == {"special_file": 1}


def mark_encrypted(data: bytes, name: str) -> bytes:
    """Set the "encrypted" flag of one entry in the central directory. zipfile clears that
    flag when writing, so the bytes are edited afterwards (the flags sit 8 bytes into a
    central directory record, the name length 28 and the name 46)."""
    raw = bytearray(data)
    start = raw.find(b"PK\x01\x02")
    while start != -1:
        length = int.from_bytes(raw[start + 28 : start + 30], "little")
        if raw[start + 46 : start + 46 + length] == name.encode():
            raw[start + 8] |= 0x1
        start = raw.find(b"PK\x01\x02", start + 4)
    return bytes(raw)


def test_encrypted_entries_are_skipped(tmp_path):
    data = mark_encrypted(make_zip({"app.py": "x = 1\n", "secret.py": "y"}), "secret.py")

    result, out = extract(tmp_path, data)

    assert stored_files(out) == {"app.py"}
    assert result.skipped_counts == {"special_file": 1}


def test_archives_that_expand_too_much_are_refused(tmp_path):
    data = make_zip({"a.txt": "a" * 6000, "b.txt": "b" * 6000})  # compresses to a few bytes

    with pytest.raises(RepositoryTooLarge):
        extract(tmp_path, data, limits(max_scan_bytes=10_000))


def test_large_binary_and_sensitive_files_are_skipped_and_secrets_redacted(tmp_path):
    data = make_zip(
        {
            "big.py": "x" * 20_000,
            "logo.png": b"\x89PNG\x00\x00\x00",
            ".env": "PASSWORD=hunter2",
            "config.py": 'GITHUB_TOKEN = "ghp_abcdEFGHijklMNOPqrstUVWXyz0123456789"\n',
        }
    )

    result, out = extract(tmp_path, data)

    assert stored_files(out) == {"config.py"}
    assert "abcdEFGH" not in (out / "config.py").read_text()
    assert result.redaction_count == 1
    assert {"too_large", "binary", "sensitive"} <= set(result.skipped_counts)


def test_a_repeated_path_keeps_the_first_copy(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf, pytest.warns(UserWarning):
        zf.writestr("app.py", "first = 1\n")
        zf.writestr("app.py", "second = 2\n")  # zipfile warns: duplicate name

    _, out = extract(tmp_path, buffer.getvalue())

    assert (out / "app.py").read_text() == "first = 1\n"


def test_something_that_is_not_a_zip_is_refused(tmp_path):
    with pytest.raises(UnsafeArchive, match="ZIP"):
        extract(tmp_path, b"PK\x03\x04 but then garbage" * 10)
