"""Run the whole static analysis over a directory of imported files.

This is a pure function of the files on disk: no database, no network. The pipeline
calls it and stores the result, and tests call it on small fixture repositories.
"""

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from app.services.analysis import importance
from app.services.analysis.dependencies import Dependency, extract_dependencies, is_manifest
from app.services.analysis.models import FileAnalysis, ImportRef
from app.services.analysis.parsers import parse_file
from app.services.analysis.relationships import PathIndex, resolve_import
from app.services.analysis.technologies import Technology, detect_technologies

logger = logging.getLogger(__name__)

# Languages that describe data or documents rather than programs.
NON_PROGRAMMING = frozenset(
    {"JSON", "YAML", "TOML", "Markdown", "Text", "Properties", "reStructuredText", "XML", "Gradle"}
)


@dataclass
class SourceFile:
    """What the analysis needs to know about one stored file."""

    path: str
    language: str | None
    size_bytes: int
    line_count: int


@dataclass
class FileResult:
    analysis: FileAnalysis | None = None
    importance_score: int = 0
    importance_reasons: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    path: str
    ref: ImportRef
    targets: list[str]  # repository files this import resolves to; empty for libraries


@dataclass
class AnalysisOutput:
    files: dict[str, FileResult]
    imports: list[ImportResult]
    dependencies: list[Dependency]
    technologies: list[Technology]
    stats: dict


def analyze_directory(root: Path, files: list[SourceFile]) -> AnalysisOutput:
    languages = {f.path: f.language for f in files}
    results: dict[str, FileResult] = {f.path: FileResult() for f in files}
    manifests: dict[str, str] = {}

    for source_file in files:
        text = _read(root, source_file.path)
        if text is None:
            continue
        if is_manifest(source_file.path):
            manifests[source_file.path] = text
        try:
            results[source_file.path].analysis = parse_file(
                source_file.language, source_file.path, text
            )
        except Exception:
            # A parser bug on one odd file must not lose the rest of the analysis.
            logger.exception("Could not analyze %s", source_file.path)
            results[source_file.path].analysis = FileAnalysis(parse_error=True)

    index = PathIndex(languages)
    imports, imported_by = _resolve_all(results, languages, index)
    dependencies = extract_dependencies(manifests)

    external = [(i.path, languages[i.path], i.ref) for i in imports if not i.targets]
    technologies = detect_technologies(dependencies, external, list(languages))

    for path, result in results.items():
        result.importance_score, result.importance_reasons = importance.score_file(
            path, result.analysis, len(imported_by[path])
        )

    stats = _statistics(files, results, imports, dependencies)
    return AnalysisOutput(results, imports, dependencies, technologies, stats)


def _read(root: Path, path: str) -> str | None:
    try:
        return (root / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _resolve_all(
    results: dict[str, FileResult], languages: dict[str, str | None], index: PathIndex
) -> tuple[list[ImportResult], dict[str, set[str]]]:
    imports: list[ImportResult] = []
    imported_by: dict[str, set[str]] = defaultdict(set)
    for path, result in results.items():
        if result.analysis is None:
            continue
        for ref in result.analysis.imports:
            targets = resolve_import(path, languages[path], ref, index)
            imports.append(ImportResult(path, ref, targets))
            for target in targets:
                imported_by[target].add(path)
    return imports, imported_by


def _statistics(
    files: list[SourceFile],
    results: dict[str, FileResult],
    imports: list[ImportResult],
    dependencies: list[Dependency],
) -> dict:
    by_language: dict[str, dict] = {}
    for f in files:
        if f.language is None:
            continue
        row = by_language.setdefault(
            f.language,
            {
                "name": f.language,
                "files": 0,
                "lines": 0,
                "bytes": 0,
                "is_programming": f.language not in NON_PROGRAMMING,
            },  # fmt: skip
        )
        row["files"] += 1
        row["lines"] += f.line_count
        row["bytes"] += f.size_bytes

    kinds = Counter(
        symbol.kind for r in results.values() if r.analysis for symbol in r.analysis.symbols
    )
    programming_lines = sum(r["lines"] for r in by_language.values() if r["is_programming"])
    return {
        "languages": sorted(by_language.values(), key=lambda r: (-r["lines"], r["name"])),
        "totals": {
            "files": len(files),
            "code_lines": programming_lines,
            "symbols": sum(kinds.values()),
            "symbols_by_kind": dict(kinds),
            "imports": len(imports),
            "internal_imports": sum(1 for i in imports if i.targets),
            "dependencies": len(dependencies),
            "test_files": sum(1 for f in files if importance.is_test_file(f.path)),
            "parse_errors": sum(
                1 for r in results.values() if r.analysis and r.analysis.parse_error
            ),
        },
    }
