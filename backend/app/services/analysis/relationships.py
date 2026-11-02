"""Work out which imports point at other files in the same repository.

Resolution is by path conventions only; nothing is imported or run. It is a best effort:
an import that cannot be matched to a file is treated as external (a library) or as
something this analysis cannot see, such as same-package references in Java.
"""

import posixpath
from collections import defaultdict
from collections.abc import Iterable

from app.services.analysis.models import ImportRef

_ES_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json")
_ES_JS_TO_TS = {".js": (".ts", ".tsx"), ".jsx": (".tsx",), ".mjs": (".mts",), ".cjs": (".cts",)}


class PathIndex:
    """Lookup tables built once from every stored file path in the repository."""

    def __init__(self, paths: Iterable[str]):
        self.paths = set(paths)
        self.python: dict[str, list[str]] = defaultdict(list)
        self.java: dict[str, list[str]] = defaultdict(list)

        for path in self.paths:
            parts = path.split("/")
            if path.endswith(".py"):
                module_parts = parts[:-1] + [parts[-1][:-3]]
                if module_parts[-1] == "__init__":
                    module_parts = module_parts[:-1]
                # A file can be imported under any suffix of its dotted path, because
                # the directory the package is rooted at (src/, backend/...) varies.
                for start in range(len(module_parts)):
                    self.python[".".join(module_parts[start:])].append(path)
            elif path.endswith(".java"):
                for start in range(len(parts)):
                    self.java["/".join(parts[start:])].append(path)


def resolve_import(
    importing: str, language: str | None, ref: ImportRef, index: PathIndex
) -> list[str]:
    """Repository files this import refers to (usually zero or one)."""
    if language == "Python":
        targets = _python(importing, ref, index)
    elif language in ("JavaScript", "TypeScript"):
        targets = _ecmascript(importing, ref, index)
    elif language == "Java":
        targets = _java(importing, ref, index)
    else:
        targets = []
    return [t for t in dict.fromkeys(targets) if t != importing]


def _join(*parts: str) -> str:
    return "/".join(part for part in parts if part)


def _closest(importing: str, candidates: list[str]) -> str:
    """Of several files matching a module name, the one nearest the importing file.

    Ties go to the conventional source folder (src/main/...), then the shorter path.
    """
    here = importing.split("/")[:-1]

    def shared_directories(candidate: str) -> int:
        count = 0
        for a, b in zip(here, candidate.split("/")[:-1], strict=False):
            if a != b:
                break
            count += 1
        return count

    return max(
        candidates,
        key=lambda c: (shared_directories(c), "/src/main/" in f"/{c}", -len(c), c),
    )


def _python(importing: str, ref: ImportRef, index: PathIndex) -> list[str]:
    dots = len(ref.module) - len(ref.module.lstrip("."))
    name = ref.module[dots:]
    targets: list[str] = []

    if dots:  # relative import: start from the importing file's own package
        directory = importing.split("/")[:-1]
        climb = dots - 1  # one dot is the current package, each extra dot goes up one
        if climb > len(directory):
            return []  # would climb above the repository root
        directory = directory[: len(directory) - climb]
        base = _join(*directory, *(name.split(".") if name else []))

        candidates = [f"{base}.py"] if name else []
        candidates.append(_join(base, "__init__.py"))
        for imported in ref.names:  # "from . import sibling" names a module
            candidates += [f"{_join(base, imported)}.py", _join(base, imported, "__init__.py")]
        return [c for c in candidates if c in index.paths]

    if name in index.python:
        targets.append(_closest(importing, index.python[name]))
    for imported in ref.names:
        submodule = f"{name}.{imported}"
        if submodule in index.python:
            targets.append(_closest(importing, index.python[submodule]))
    return targets


def _ecmascript(importing: str, ref: ImportRef, index: PathIndex) -> list[str]:
    spec = ref.module
    if spec in (".", "..") or spec.startswith(("./", "../")):
        bases = [posixpath.normpath(posixpath.join(posixpath.dirname(importing), spec))]
    elif spec.startswith(("@/", "~/")):  # a common alias for the src folder
        bases = [f"src/{spec[2:]}", spec[2:]]
    else:
        return []  # a package from node_modules

    for base in bases:
        if base.startswith(".."):
            continue
        for candidate in _es_candidates(base):
            if candidate in index.paths:
                return [candidate]
    return []


def _es_candidates(base: str) -> list[str]:
    extension = posixpath.splitext(base)[1]
    candidates = [base] if extension in _ES_EXTENSIONS else []
    # TypeScript's ESM style writes "./util.js" for a file that is really util.ts.
    for js, replacements in _ES_JS_TO_TS.items():
        if base.endswith(js):
            candidates += [base[: -len(js)] + ts for ts in replacements]
    candidates += [base + ext for ext in _ES_EXTENSIONS]
    candidates += [f"{base}/index{ext}" for ext in _ES_EXTENSIONS]
    return candidates


def _java(importing: str, ref: ImportRef, index: PathIndex) -> list[str]:
    parts = ref.module.split(".")
    # Try the full name, then shorter ones: "a.b.Outer.Inner" lives in a/b/Outer.java.
    for length in range(len(parts), 1, -1):
        hits = index.java.get("/".join(parts[:length]) + ".java")
        if hits:
            return [_closest(importing, hits)]
    return []
