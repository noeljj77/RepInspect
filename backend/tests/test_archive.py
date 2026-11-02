import tarfile

import pytest

from app.services.ingestion.archive import (
    ExtractionLimits,
    extract_tar_gz,
    is_portable_path,
    relative_member_path,
)
from app.services.ingestion.errors import RepositoryTooLarge, UnsafeArchive
from tests.fakes import make_tarball, raw_file, raw_symlink

LIMITS = ExtractionLimits(
    max_scan_bytes=10_000_000,
    max_files=100,
    max_file_bytes=10_000,
    max_total_bytes=1_000_000,
    max_listed_skipped=50,
)


def extract(tmp_path, tarball: bytes, limits: ExtractionLimits = LIMITS):
    archive = tmp_path / "repo.tar.gz"
    archive.write_bytes(tarball)
    destination = tmp_path / "out"
    return extract_tar_gz(archive, destination, limits), destination


def limits(**overrides) -> ExtractionLimits:
    return ExtractionLimits(**{**LIMITS.__dict__, **overrides})


def stored_files(destination) -> set[str]:
    return {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}


# --- normal operation ---


def test_extracts_files_without_the_wrapper_folder(tmp_path):
    tarball = make_tarball({"app.py": "a = 1\nb = 2\n", "src/util.js": "export {}"})

    result, out = extract(tmp_path, tarball)

    assert stored_files(out) == {"app.py", "src/util.js"}
    assert (out / "app.py").read_text() == "a = 1\nb = 2\n"
    by_path = {f.path: f for f in result.files}
    assert by_path["app.py"].line_count == 2
    assert by_path["app.py"].language == "Python"
    assert by_path["src/util.js"].line_count == 1  # no trailing newline still counts
    assert result.kept_count == 2
    assert result.total_bytes == len("a = 1\nb = 2\n") + len("export {}")


def test_empty_files_are_kept(tmp_path):
    result, out = extract(tmp_path, make_tarball({"pkg/__init__.py": ""}))

    assert stored_files(out) == {"pkg/__init__.py"}
    assert result.files[0].line_count == 0


def test_an_archive_with_no_files_gives_an_empty_result(tmp_path):
    result, out = extract(tmp_path, make_tarball({}))

    assert result.kept_count == 0
    assert stored_files(out) == set()


# --- hostile paths ---


@pytest.mark.parametrize(
    "name",
    [
        "../evil.txt",
        "owner-repo/../../evil.txt",
        "owner-repo/a/../../../evil.txt",
        "/etc/evil.txt",
        "C:/Windows/evil.txt",
        "c:\\evil.txt",
        "owner-repo\\..\\..\\evil.txt",
        "owner-repo/..\\..\\evil.txt",
    ],
)
def test_path_traversal_aborts_the_import_and_writes_nothing_outside(tmp_path, name):
    tarball = make_tarball({"ok.py": "x = 1"}, extra=(raw_file(name, b"pwned"),))

    with pytest.raises(UnsafeArchive):
        extract(tmp_path, tarball)

    assert not (tmp_path / "evil.txt").exists()
    assert not list(tmp_path.parent.glob("evil.txt"))


def test_symlinks_and_hardlinks_are_never_created(tmp_path):
    hardlink = tarfile.TarInfo("owner-repo/hard")
    hardlink.type = tarfile.LNKTYPE
    hardlink.linkname = "owner-repo/app.py"
    tarball = make_tarball(
        {"app.py": "x = 1"},
        extra=(
            raw_symlink("owner-repo/passwd", "/etc/passwd"),
            raw_symlink("owner-repo/up", "../../outside"),
            (hardlink, None),
        ),
    )

    result, out = extract(tmp_path, tarball)

    assert stored_files(out) == {"app.py"}
    assert not (out / "passwd").exists() and not (out / "up").is_symlink()
    assert result.skipped_counts == {"special_file": 3}


def test_a_file_cannot_be_written_through_a_symlinked_directory(tmp_path):
    tarball = make_tarball(
        {},
        extra=(
            raw_symlink("owner-repo/linked", str(tmp_path / "elsewhere")),
            raw_file("owner-repo/linked/pwned.txt", b"x"),
        ),
    )
    (tmp_path / "elsewhere").mkdir()

    extract(tmp_path, tarball)

    assert list((tmp_path / "elsewhere").iterdir()) == []


@pytest.mark.parametrize(
    "name",
    ["bad:name.txt", "CON.txt", "nul", "trailing.", "q?.py", "a*b.py", "x|y.py", "tab\tname"],
)
def test_names_that_are_unsafe_on_windows_are_skipped(tmp_path, name):
    tarball = make_tarball({name: "x", "good.py": "y"})

    result, out = extract(tmp_path, tarball)

    assert stored_files(out) == {"good.py"}
    assert result.skipped_counts == {"unsupported_name": 1}


def test_a_file_and_a_directory_with_the_same_name_do_not_crash(tmp_path):
    tarball = make_tarball({"a": "file", "a/b.py": "nested"})

    result, out = extract(tmp_path, tarball)

    assert result.skipped_counts.get("unwritable") == 1
    assert result.kept_count == 1


# --- filtering ---


def test_sensitive_binary_ignored_and_generated_files_are_not_stored(tmp_path):
    tarball = make_tarball(
        {
            "app.py": "print('hi')",
            ".env": "SECRET=abc",
            "keys/server.pem": "-----BEGIN-----",
            "logo.png": b"\x89PNG\r\n",
            "package-lock.json": "{}",
            "static/app.min.js": "x",
            "node_modules/dep/index.js": "x",
            ".git/config": "x",
            ".env.example": "SECRET=changeme",
        }
    )

    result, out = extract(tmp_path, tarball)

    assert stored_files(out) == {"app.py", ".env.example"}
    reasons = {f.path: f.skipped_reason for f in result.files if f.skipped_reason}
    assert reasons == {
        ".env": "sensitive",
        "keys/server.pem": "sensitive",
        "logo.png": "binary",
        "package-lock.json": "lockfile",
        "static/app.min.js": "generated",
    }
    # Files inside ignored directories are only counted, never listed.
    assert result.skipped_counts["ignored_directory"] == 2


def test_oversized_files_are_skipped(tmp_path):
    tarball = make_tarball({"big.py": "x" * 10_001, "small.py": "x"})

    result, out = extract(tmp_path, tarball)

    assert stored_files(out) == {"small.py"}
    assert result.skipped_counts == {"too_large": 1}


def test_files_that_look_binary_are_skipped_even_with_a_text_extension(tmp_path):
    tarball = make_tarball(
        {"data.txt": b"abc\x00def", "latin.txt": "café".encode("latin-1"), "ok.txt": "hi"}
    )

    result, out = extract(tmp_path, tarball)

    assert stored_files(out) == {"ok.txt"}
    assert result.skipped_counts == {"binary": 2}


def test_secrets_are_redacted_before_files_are_written(tmp_path):
    source = 'key = "AKIAIOSFODNN7EXAMPLE"\npassword = "hunter2hunter2"\nprint(1)\n'

    result, out = extract(tmp_path, make_tarball({"config.py": source}))

    stored = (out / "config.py").read_text()
    assert "AKIAIOSFODNN7EXAMPLE" not in stored and "hunter2hunter2" not in stored
    assert stored.count("\n") == source.count("\n")
    assert result.redaction_count == 2


def test_skipped_files_listed_individually_are_capped(tmp_path):
    tarball = make_tarball({f"img{i}.png": b"x" for i in range(10)} | {"a.py": "x"})

    result, _ = extract(tmp_path, tarball, limits(max_listed_skipped=3))

    assert len([f for f in result.files if f.skipped_reason]) == 3
    assert result.skipped_counts["binary"] == 10  # the count still covers all of them


# --- limits ---


def test_stops_at_the_file_count_limit_and_says_so(tmp_path):
    tarball = make_tarball({f"f{i:03}.py": "x" for i in range(10)})

    result, out = extract(tmp_path, tarball, limits(max_files=4))

    assert result.truncated is True
    assert result.kept_count == 4
    assert len(stored_files(out)) == 4


def test_stops_at_the_total_size_limit(tmp_path):
    tarball = make_tarball({f"f{i}.py": "x" * 100 for i in range(10)})

    result, _ = extract(tmp_path, tarball, limits(max_total_bytes=350))

    assert result.truncated is True
    assert result.kept_count == 3


def test_not_truncated_when_everything_fits(tmp_path):
    result, _ = extract(tmp_path, make_tarball({"a.py": "x"}))

    assert result.truncated is False


def test_archives_that_expand_too_much_are_rejected(tmp_path):
    # 200 KB of zeros compresses to almost nothing: a miniature archive bomb.
    tarball = make_tarball({"zeros.bin": b"\x00" * 200_000})

    with pytest.raises(RepositoryTooLarge):
        extract(tmp_path, tarball, limits(max_scan_bytes=50_000))


def test_corrupt_archives_are_rejected_cleanly(tmp_path):
    with pytest.raises(UnsafeArchive):
        extract(tmp_path, b"this is not a gzip archive at all")


def test_truncated_archives_are_rejected_cleanly(tmp_path):
    tarball = make_tarball({"a.py": "x" * 5000})

    with pytest.raises(UnsafeArchive):
        extract(tmp_path, tarball[: len(tarball) // 2])


# --- path helpers ---


def test_relative_member_path_drops_the_wrapper_folder():
    assert relative_member_path("owner-repo-abc/src/app.py") == "src/app.py"
    assert relative_member_path("owner-repo-abc/./src//app.py") == "src/app.py"
    assert relative_member_path("owner-repo-abc") is None
    assert relative_member_path("owner-repo-abc/") is None


@pytest.mark.parametrize("path", ["src/app.py", "docs/guide v2.md", "a.b.c", ".github/ci.yml"])
def test_portable_paths(path):
    assert is_portable_path(path) is True


@pytest.mark.parametrize(
    "path", ["a/CON", "a/com1.txt", "a/b:c", "a/b\\c", "a/b.", "a/b ", "a/\x01"]
)
def test_non_portable_paths(path):
    assert is_portable_path(path) is False
