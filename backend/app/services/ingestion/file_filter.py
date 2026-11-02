"""Decide which files are never worth keeping, based on their path alone.

Content-based checks (binary data, size) happen in the extractor, which reads the file.
"""

from pathlib import PurePosixPath

# Whole directories that are build output, dependencies, caches or secrets stores.
# Files inside them are counted but never listed or stored.
IGNORED_DIRECTORIES = frozenset(
    {
        ".git", ".svn", ".hg", ".idea", ".vscode", ".aws", ".ssh", ".gnupg",
        "node_modules", "bower_components", "vendor", "__pycache__", "site-packages",
        ".venv", "venv", "virtualenv", ".tox", ".nox",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache", ".gradle", ".terraform",
        "dist", "build", "target", "out", ".next", ".nuxt", ".svelte-kit", "coverage",
        "__MACOSX",
    }
)  # fmt: skip

# File names that commonly hold credentials.
SENSITIVE_NAMES = frozenset(
    {
        ".npmrc", ".pypirc", ".netrc", ".htpasswd", ".git-credentials", "credentials",
        "credentials.json", "secrets.json", "secrets.yml", "secrets.yaml",
        "terraform.tfvars", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    }
)  # fmt: skip
SENSITIVE_EXTENSIONS = frozenset(
    {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx", ".tfstate", ".secret"}
)
# These start with ".env" but are meant to be committed as templates.
ENV_TEMPLATE_SUFFIXES = frozenset({"example", "sample", "template", "dist", "defaults"})

BINARY_EXTENSIONS = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg", ".tiff", ".psd",
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war", ".ear",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".mp3", ".mp4", ".mov", ".avi", ".wav", ".ogg", ".webm", ".flac",
        ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".o", ".a", ".pyc", ".pyo", ".wasm",
        ".sqlite", ".sqlite3", ".db", ".pt", ".pth", ".h5", ".onnx", ".pkl", ".pickle",
        ".npy", ".npz", ".ds_store",
    }
)  # fmt: skip

LOCKFILES = frozenset(
    {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "pipfile.lock",
        "composer.lock", "cargo.lock", "gemfile.lock", "go.sum", "gradle.lockfile",
    }
)  # fmt: skip

# Reasons returned by skip_reason(), also stored on analysis files.
SENSITIVE = "sensitive"
BINARY = "binary"
LOCKFILE = "lockfile"
GENERATED = "generated"


def in_ignored_directory(path: str) -> bool:
    directories = PurePosixPath(path).parts[:-1]
    return any(part in IGNORED_DIRECTORIES for part in directories)


def skip_reason(path: str) -> str | None:
    """Why a file should be left out judging by its path, or None to keep looking."""
    name = PurePosixPath(path).name.lower()
    suffix = PurePosixPath(name).suffix

    if name == ".env" or (
        name.startswith(".env.") and name.rsplit(".", 1)[-1] not in ENV_TEMPLATE_SUFFIXES
    ):
        return SENSITIVE
    if name in SENSITIVE_NAMES or suffix in SENSITIVE_EXTENSIONS:
        return SENSITIVE
    # Besides the well-known names, every package manager has its own *.lock file
    # (uv.lock, pdm.lock, Podfile.lock, deno.lock...).
    if name in LOCKFILES or name.endswith(".lock"):
        return LOCKFILE
    if name.endswith((".min.js", ".min.css")) or suffix == ".map":
        return GENERATED
    if suffix in BINARY_EXTENSIONS:
        return BINARY
    return None
