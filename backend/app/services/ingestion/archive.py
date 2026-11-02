"""Safely unpack a repository archive into a directory of filtered, redacted text files.

Two formats: the .tar.gz GitHub serves, and .zip files people upload. Both go through
the same per-file checks below. The archive is untrusted input. Protections:
- Path traversal: absolute paths, drive letters and ".." components abort the import,
  and every file is checked to land inside the destination directory.
- Links and special files (symlinks, hardlinks, devices) are never created. Encrypted
  ZIP entries are skipped.
- Names that are unsafe on Windows (": * ? \\", reserved device names) are skipped.
- Archive bombs: the sizes of everything read through are summed against a limit, and
  only files up to max_file_bytes are ever read into memory.
- File and byte limits end the import early instead of filling the disk.
- Nothing is executed, and extracted files get default permissions (never executable).
"""

import hashlib
import re
import stat
import tarfile
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings, get_settings
from app.services.analysis.languages import detect_language
from app.services.ingestion import file_filter
from app.services.ingestion.errors import RepositoryTooLarge, UnsafeArchive
from app.services.ingestion.secrets import redact_secrets

# Skip reasons produced here, in addition to those from file_filter.
TOO_LARGE = "too_large"
SPECIAL_FILE = "special_file"
UNSUPPORTED_NAME = "unsupported_name"
IGNORED_DIRECTORY = "ignored_directory"
UNWRITABLE = "unwritable"

_WINDOWS_UNSAFE_CHARS = re.compile(r'[<>:"|?*\\\x00-\x1f]')
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
_DRIVE_LETTER = re.compile(r"^[A-Za-z]:")


@dataclass(frozen=True)
class ExtractionLimits:
    max_scan_bytes: int
    max_files: int
    max_file_bytes: int
    max_total_bytes: int
    max_listed_skipped: int

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "ExtractionLimits":
        s = settings or get_settings()
        return cls(
            max_scan_bytes=s.max_archive_scan_bytes,
            max_files=s.max_files,
            max_file_bytes=s.max_file_bytes,
            max_total_bytes=s.max_total_bytes,
            max_listed_skipped=s.max_listed_skipped_files,
        )


@dataclass
class FileRecord:
    path: str
    size_bytes: int
    language: str | None
    line_count: int | None = None
    skipped_reason: str | None = None  # None means the file was stored
    # SHA-256 of the stored (redacted) text, used to see which files changed between versions.
    content_hash: str | None = None


@dataclass
class ExtractionResult:
    files: list[FileRecord] = field(default_factory=list)
    skipped_counts: dict[str, int] = field(default_factory=dict)
    redaction_count: int = 0
    total_bytes: int = 0
    truncated: bool = False
    kept_count: int = 0
    listed_skipped: int = 0

    @property
    def kept(self) -> list[FileRecord]:
        return [f for f in self.files if f.skipped_reason is None]

    def count_skipped(self, reason: str) -> None:
        self.skipped_counts[reason] = self.skipped_counts.get(reason, 0) + 1


def relative_member_path(member_name: str, strip_wrapper: bool = True) -> str | None:
    """Path inside the repository, or None for the wrapper directory itself.

    GitHub wraps everything in one top-level folder ("owner-repo-sha/..."), which is
    dropped here. Raises UnsafeArchive for anything that could escape the destination.
    """
    slashed = member_name.replace("\\", "/")
    if "\x00" in member_name or slashed.startswith("/") or _DRIVE_LETTER.match(slashed):
        raise UnsafeArchive("The archive contains an unsafe file path, so it was not imported.")
    parts = slashed.split("/")
    if ".." in parts:
        raise UnsafeArchive("The archive contains an unsafe file path, so it was not imported.")

    # Keep the original separators for names that contain backslashes, so the
    # portability check below can reject them instead of silently rewriting them.
    original_parts = [p for p in member_name.split("/") if p not in ("", ".")]
    inner = original_parts[1:] if strip_wrapper else original_parts
    return "/".join(inner) if inner else None


def is_portable_path(path: str) -> bool:
    """True if every part of the path is a safe file name on Linux, macOS and Windows."""
    for part in path.split("/"):
        if _WINDOWS_UNSAFE_CHARS.search(part) or part.endswith((".", " ")):
            return False
        if part.split(".")[0].upper() in _WINDOWS_RESERVED:
            return False
    return True


def count_lines(text: str) -> int:
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)


# Reads a member's content, at most `limit` bytes. None for something that is not a file.
Reader = Callable[[int], bytes | None]


def extract_tar_gz(archive: Path, destination: Path, limits: ExtractionLimits) -> ExtractionResult:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    result = ExtractionResult()
    scanned = 0

    try:
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar:
                scanned += max(member.size, 0)
                if scanned > limits.max_scan_bytes:
                    raise RepositoryTooLarge(
                        "This repository expands to more data than the import limit allows."
                    )
                if member.isdir():
                    continue
                path = relative_member_path(member.name)
                if path is None:
                    continue
                if not member.isfile():
                    result.count_skipped(SPECIAL_FILE)
                    continue

                def read(limit: int, member: tarfile.TarInfo = member) -> bytes | None:
                    source = tar.extractfile(member)
                    return None if source is None else source.read(limit)

                if not _handle_file(read, member.size, path, root, limits, result):
                    break
    except (tarfile.TarError, EOFError, OSError, zlib.error):
        raise UnsafeArchive("The repository archive could not be read.") from None

    return result


def _has_single_wrapper(names: list[str]) -> bool:
    """True when every entry sits in one top-level folder, as in GitHub's "Download ZIP"."""
    tops = {name.replace("\\", "/").lstrip("/").split("/", 1)[0] for name in names}
    return len(tops) == 1 and all("/" in name.replace("\\", "/").strip("/") for name in names)


def _is_zip_link_or_special(info: zipfile.ZipInfo) -> bool:
    """ZIP files made on Unix store the file mode in the upper bits of external_attr.

    Many tools store only permission bits (no file type); those are ordinary files. Only
    an explicit type other than file or directory (a symlink, a device) is refused.
    """
    kind = stat.S_IFMT(info.external_attr >> 16)
    return kind not in (0, stat.S_IFREG, stat.S_IFDIR)


def extract_zip(archive: Path, destination: Path, limits: ExtractionLimits) -> ExtractionResult:
    """Unpack an uploaded .zip. A single top-level folder is dropped, like GitHub's wrapper."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    result = ExtractionResult()
    scanned = 0

    try:
        with zipfile.ZipFile(archive) as zf:
            entries = [info for info in zf.infolist() if not info.is_dir()]
            strip = _has_single_wrapper([info.filename for info in entries])
            for info in entries:
                # The declared size, summed. ZipFile never returns more than the declared size
                # for an entry, so this bounds what is decompressed (zip bombs included).
                scanned += max(info.file_size, 0)
                if scanned > limits.max_scan_bytes:
                    raise RepositoryTooLarge(
                        "This archive expands to more data than the import limit allows."
                    )
                path = relative_member_path(info.filename, strip_wrapper=strip)
                if path is None:
                    continue
                if _is_zip_link_or_special(info) or info.flag_bits & 0x1:  # 0x1: encrypted
                    result.count_skipped(SPECIAL_FILE)
                    continue

                def read(limit: int, info: zipfile.ZipInfo = info) -> bytes | None:
                    with zf.open(info) as source:
                        return source.read(limit)

                if not _handle_file(read, info.file_size, path, root, limits, result):
                    break
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, OSError, zlib.error):
        raise UnsafeArchive("The ZIP file could not be read. Is it a valid .zip archive?") from None
    except NotImplementedError:  # an unsupported compression method
        raise UnsafeArchive(
            "The ZIP file uses a compression method that is not supported."
        ) from None

    return result


def _handle_file(
    read: Reader,
    size: int,
    path: str,
    root: Path,
    limits: ExtractionLimits,
    result: ExtractionResult,
) -> bool:
    """Process one regular file. Returns False once a limit means we should stop."""
    if file_filter.in_ignored_directory(path):
        result.count_skipped(IGNORED_DIRECTORY)
        return True
    if not is_portable_path(path):
        result.count_skipped(UNSUPPORTED_NAME)
        return True

    reason = file_filter.skip_reason(path)
    if reason is None and size > limits.max_file_bytes:
        reason = TOO_LARGE
    if reason is not None:
        _record_skipped(result, path, size, reason, limits)
        return True

    if result.kept_count >= limits.max_files or result.total_bytes + size > limits.max_total_bytes:
        result.truncated = True
        return False

    data = read(limits.max_file_bytes + 1)
    if data is None:
        result.count_skipped(SPECIAL_FILE)
        return True
    if len(data) > limits.max_file_bytes:
        _record_skipped(result, path, len(data), TOO_LARGE, limits)
        return True

    text = _decode_text(data)
    if text is None:
        _record_skipped(result, path, len(data), file_filter.BINARY, limits)
        return True

    text, redactions = redact_secrets(text)
    encoded = text.encode("utf-8")

    target = root / path
    if not target.resolve().is_relative_to(root):
        raise UnsafeArchive("The archive contains an unsafe file path, so it was not imported.")
    if target.exists():
        # Two entries with the same path (possible in a ZIP): keep the first.
        result.count_skipped(UNWRITABLE)
        return True
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)
    except OSError:
        # e.g. the archive has both a file "a" and a file "a/b".
        result.count_skipped(UNWRITABLE)
        return True

    result.redaction_count += redactions
    result.total_bytes += len(encoded)
    result.kept_count += 1
    result.files.append(
        FileRecord(
            path=path,
            size_bytes=len(encoded),
            language=detect_language(path),
            line_count=count_lines(text),
            content_hash=hashlib.sha256(encoded).hexdigest(),
        )
    )
    return True


def _decode_text(data: bytes) -> str | None:
    """Decode as UTF-8, or None if the content looks binary."""
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _record_skipped(
    result: ExtractionResult, path: str, size: int, reason: str, limits: ExtractionLimits
) -> None:
    result.count_skipped(reason)
    if result.listed_skipped < limits.max_listed_skipped:
        result.listed_skipped += 1
        result.files.append(
            FileRecord(
                path=path, size_bytes=size, language=detect_language(path), skipped_reason=reason
            )
        )
