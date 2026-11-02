"""Assemble the material a model is allowed to use.

The model never sees a whole repository. It gets facts that static analysis already
established (technologies, dependencies, structure, routes, important files), plus
numbered excerpts of the most important files, all within a character budget.

Everything from the repository is untrusted: READMEs, comments and strings can contain
text that tries to give the model instructions. Two defences live here:
- every block is fenced with markers containing a random value chosen per request, which
  text inside a file cannot predict and so cannot spoof;
- the code itself is passed through unchanged, so quotes can later be checked against it.
"""

import re
import secrets
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models import (
    AnalysisFile,
    CodeImport,
    CodeSymbol,
    ProjectDependency,
    RepositoryAnalysis,
    SavedRepository,
)
from app.services.analysis.importance import IMPORTANT_THRESHOLD, is_test_file

Reader = Callable[[str], str | None]

EXCERPT_MAX_LINES = 160
EXCERPT_MAX_CHARS = 7000
README_MAX_LINES = 120
FILE_PACK_MAX_LINES = 700
FILE_PACK_MAX_CHARS = 28_000
LONG_LINE = 300
MAX_EXCERPTS = 12
MAX_IMPORTANT = 15
MAX_ROUTES = 60
MAX_RUNTIME_DEPENDENCIES = 40

_DEV_SCOPES = {"dev", "build", "plugin"}
_ROUTE_PATTERNS = [
    # FastAPI / Flask style: @router.get("/x"), @app.route("/x")
    re.compile(r"""^@[\w.]+\.(get|post|put|patch|delete|head|options|route|api_route|websocket)\(\s*(?:path\s*=\s*)?['"]([^'"]*)['"]"""),
    # Spring: @GetMapping("/x"), @RequestMapping("/x")
    re.compile(r"""^@(Get|Post|Put|Patch|Delete|Request)Mapping(?:\(\s*(?:value\s*=\s*|path\s*=\s*)?\{?\s*"([^"]*)")?"""),
    # NestJS: @Get('x')
    re.compile(r"""^@(Get|Post|Put|Patch|Delete|All)\(\s*['"]?([^'")]*)"""),
]  # fmt: skip


@dataclass
class SymbolFacts:
    kind: str
    qualified_name: str
    name: str
    start_line: int
    end_line: int
    signature: str
    decorators: list[str]


@dataclass
class FileFacts:
    path: str
    language: str | None
    line_count: int
    importance_score: int
    importance_reasons: list[str]
    symbols: list[SymbolFacts] = field(default_factory=list)
    internal_imports: list[str] = field(default_factory=list)
    external_imports: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)


@dataclass
class DependencyFacts:
    name: str
    version_spec: str | None
    scope: str
    source_file: str
    line: int | None


@dataclass
class RouteFacts:
    method: str
    route: str
    path: str
    line: int
    handler: str


@dataclass
class EvidenceFacts:
    repo_name: str
    description: str | None
    topics: list[str]
    default_branch: str | None
    languages: list[tuple[str, int]]  # programming languages by lines of code
    totals: dict
    technologies: list[dict]
    dependencies: list[DependencyFacts]
    files: dict[str, FileFacts]
    routes: list[RouteFacts]
    readme_path: str | None


# --- loading ----------------------------------------------------------------------------------


def load_facts(
    db: Session, repository: SavedRepository, analysis: RepositoryAnalysis
) -> EvidenceFacts:
    rows = db.scalars(
        select(AnalysisFile).where(
            AnalysisFile.analysis_id == analysis.id, AnalysisFile.skipped_reason.is_(None)
        )
    )
    by_id = {row.id: row for row in rows}
    files = {
        row.path: FileFacts(
            path=row.path,
            language=row.language,
            line_count=row.line_count or 0,
            importance_score=row.importance_score,
            importance_reasons=row.importance_reasons or [],
        )
        for row in by_id.values()
    }

    for symbol in db.scalars(select(CodeSymbol).where(CodeSymbol.analysis_id == analysis.id)):
        owner = by_id.get(symbol.file_id)
        if owner is not None:
            files[owner.path].symbols.append(
                SymbolFacts(
                    kind=symbol.kind,
                    qualified_name=symbol.qualified_name,
                    name=symbol.name,
                    start_line=symbol.start_line,
                    end_line=symbol.end_line,
                    signature=symbol.signature,
                    decorators=symbol.decorators or [],
                )
            )
    for facts in files.values():
        facts.symbols.sort(key=lambda s: s.start_line)

    target = aliased(AnalysisFile)
    imports = db.execute(
        select(CodeImport.file_id, CodeImport.module, target.path)
        .outerjoin(target, CodeImport.resolved_file_id == target.id)
        .where(CodeImport.analysis_id == analysis.id)
    )
    for file_id, module, resolved in imports:
        owner = by_id.get(file_id)
        if owner is None:
            continue
        facts = files[owner.path]
        if resolved:
            if resolved not in facts.internal_imports:
                facts.internal_imports.append(resolved)
            if resolved in files and owner.path not in files[resolved].imported_by:
                files[resolved].imported_by.append(owner.path)
        elif module not in facts.external_imports:
            facts.external_imports.append(module)

    dependencies = [
        DependencyFacts(d.name, d.version_spec, d.scope, d.source_file, d.line)
        for d in db.scalars(
            select(ProjectDependency).where(ProjectDependency.analysis_id == analysis.id)
        )
    ]
    meta = analysis.github_metadata or {}
    stats = analysis.code_stats or {}
    languages = [
        (row["name"], row["lines"])
        for row in stats.get("languages", [])
        if row.get("is_programming") and row.get("lines", 0) > 0
    ]
    return EvidenceFacts(
        repo_name=f"{repository.owner}/{repository.name}" if repository.owner else repository.name,
        description=meta.get("description"),
        topics=meta.get("topics") or [],
        default_branch=meta.get("default_branch"),
        languages=languages,
        totals=stats.get("totals", {}),
        technologies=analysis.technologies or [],
        dependencies=dependencies,
        files=files,
        routes=_routes(files),
        readme_path=analysis.readme_path,
    )


def _routes(files: dict[str, FileFacts]) -> list[RouteFacts]:
    """HTTP endpoints found from framework decorators. Express-style `app.get(...)` calls are
    not decorators, so they are not found here."""
    found: list[RouteFacts] = []
    for facts in files.values():
        for symbol in facts.symbols:
            for decorator in symbol.decorators:
                match = next(
                    (m for pattern in _ROUTE_PATTERNS if (m := pattern.match(decorator))), None
                )
                if match is None:
                    continue
                verb = match.group(1).upper()
                method = "ANY" if verb in ("ROUTE", "API_ROUTE", "REQUEST", "ALL") else verb
                found.append(
                    RouteFacts(
                        method,
                        match.group(2) or "/",
                        facts.path,
                        symbol.start_line,
                        symbol.qualified_name,
                    )
                )
                break
    found.sort(key=lambda r: (r.path, r.line))
    return found[:MAX_ROUTES]


# --- formatting --------------------------------------------------------------------------------


def new_boundary() -> str:
    return secrets.token_hex(6)


def numbered(lines: list[str], first: int = 1) -> str:
    """Prefix each line with its number, shortening absurdly long lines (minified code)."""
    out = []
    for offset, line in enumerate(lines):
        shown = line if len(line) <= LONG_LINE else line[:LONG_LINE] + " …"
        out.append(f"{first + offset}| {shown}")
    return "\n".join(out)


def _attr(value: str) -> str:
    return re.sub(r'["\n\r]', "'", value)


class Pack:
    """Builds the prompt text block by block, stopping when the character budget is used."""

    def __init__(self, boundary: str, budget: int):
        self.boundary = boundary
        self.budget = budget
        self._parts: list[str] = []
        self.included_files: list[str] = []

    def block(self, name: str, body: str, **attrs: str) -> bool:
        attributes = "".join(f' {key}="{_attr(str(value))}"' for key, value in attrs.items())
        begin = f"<<<{self.boundary}:BEGIN {name}{attributes}>>>"
        text = f"{begin}\n{body}\n<<<{self.boundary}:END {name}>>>\n"
        if len(text) > self.budget:
            return False
        self._parts.append(text)
        self.budget -= len(text)
        return True

    def text(self) -> str:
        return "\n".join(self._parts)


def _facts_block(facts: EvidenceFacts) -> str:
    lines = [f"repository: {facts.repo_name}"]
    if facts.description:
        lines.append(f"description: {facts.description}")
    if facts.topics:
        lines.append(f"topics: {', '.join(facts.topics)}")
    if facts.default_branch:
        lines.append(f"default branch: {facts.default_branch}")
    total = sum(count for _, count in facts.languages) or 1
    if facts.languages:
        shares = ", ".join(f"{name} {count / total:.0%}" for name, count in facts.languages[:6])
        lines.append(f"languages (by lines of code): {shares}")
    t = facts.totals
    if t:
        lines.append(
            f"size: {t.get('files', 0)} files, {t.get('code_lines', 0)} lines of code, "
            f"{t.get('symbols', 0)} functions/classes, "
            f"{t.get('dependencies', 0)} declared dependencies, {t.get('test_files', 0)} test files"
        )
    return "\n".join(lines)


def _technologies_block(facts: EvidenceFacts) -> str:
    lines = []
    for tech in facts.technologies:
        proofs = []
        for item in tech.get("evidence", []):
            where = f"{item['path']}:{item['line']}" if item.get("line") else item["path"]
            proofs.append(
                f"{item['kind']} {where}"
                + (f" ({item['detail']})" if item["kind"] != "file" else "")
            )
        flag = " [development only]" if tech.get("dev_only") else ""
        lines.append(f"- {tech['name']} [{tech['category']}]{flag}: " + "; ".join(proofs))
    return "\n".join(lines) or "(none detected)"


def _dependencies_block(facts: EvidenceFacts) -> str:
    runtime = [d for d in facts.dependencies if d.scope not in _DEV_SCOPES]
    dev = [d for d in facts.dependencies if d.scope in _DEV_SCOPES]
    lines = []
    for dep in runtime[:MAX_RUNTIME_DEPENDENCIES]:
        where = f"{dep.source_file}:{dep.line}" if dep.line else dep.source_file
        lines.append(f"- {dep.name} {dep.version_spec or ''} ({where})".replace("  ", " "))
    if len(runtime) > MAX_RUNTIME_DEPENDENCIES:
        lines.append(f"... and {len(runtime) - MAX_RUNTIME_DEPENDENCIES} more")
    if dev:
        names = ", ".join(sorted({d.name for d in dev})[:20])
        lines.append(f"development/build dependencies ({len(dev)}): {names}")
    return "\n".join(lines) or "(no dependencies declared)"


def _structure_block(facts: EvidenceFacts) -> str:
    counts: Counter[str] = Counter()
    languages: dict[str, Counter[str]] = defaultdict(Counter)
    for path, info in facts.files.items():
        parts = path.split("/")[:-1]
        for depth in (1, 2):
            if len(parts) >= depth:
                folder = "/".join(parts[:depth])
                counts[folder] += 1
                if info.language:
                    languages[folder][info.language] += 1
    root_files = [p for p in facts.files if "/" not in p]
    lines = [f"(repository root): {len(root_files)} files: " + ", ".join(sorted(root_files)[:25])]
    for folder in sorted(counts)[:60]:
        if counts[folder] < 2 and "/" in folder:
            continue
        top = ", ".join(f"{name} {n}" for name, n in languages[folder].most_common(3))
        lines.append(f"{folder}/: {counts[folder]} files" + (f" ({top})" if top else ""))
    return "\n".join(lines)


def _routes_block(facts: EvidenceFacts) -> str:
    return "\n".join(f"{r.method} {r.route} -> {r.path}:{r.line} {r.handler}" for r in facts.routes)


def _important_files(facts: EvidenceFacts) -> list[FileFacts]:
    ranked = [f for f in facts.files.values() if f.importance_score >= IMPORTANT_THRESHOLD]
    ranked.sort(key=lambda f: (-f.importance_score, f.path))
    return ranked[:MAX_IMPORTANT]


def _outline(info: FileFacts, limit: int = 14) -> str:
    lines = [
        f"{s.kind} {s.qualified_name} L{s.start_line}-{s.end_line}" for s in info.symbols[:limit]
    ]
    if len(info.symbols) > limit:
        lines.append(f"... {len(info.symbols) - limit} more")
    return "; ".join(lines)


def _important_block(facts: EvidenceFacts) -> str:
    blocks = []
    for info in _important_files(facts):
        language = info.language or "unknown language"
        reasons = ", ".join(info.importance_reasons)
        entry = f"- {info.path} ({language}, {info.line_count} lines): {reasons}"
        if info.symbols:
            entry += f"\n    defines: {_outline(info)}"
        if info.internal_imports:
            entry += f"\n    imports (repository files): {', '.join(info.internal_imports[:6])}"
        blocks.append(entry)
    return "\n".join(blocks) or "(none)"


# --- packs ----------------------------------------------------------------------------------------


def build_overview_pack(
    facts: EvidenceFacts, reader: Reader, boundary: str, budget_chars: int
) -> Pack:
    pack = Pack(boundary, budget_chars)
    pack.block("facts", _facts_block(facts))
    pack.block("technologies", _technologies_block(facts))
    pack.block("dependencies", _dependencies_block(facts))
    pack.block("structure", _structure_block(facts))
    if facts.routes:
        pack.block("routes", _routes_block(facts))
    pack.block("important_files", _important_block(facts))

    if facts.readme_path and (text := reader(facts.readme_path)):
        lines = text.split("\n")[:README_MAX_LINES]
        pack.block(
            "file",
            numbered(lines),
            path=facts.readme_path,
            first_line="1",
            last_line=str(len(lines)),
        )
        pack.included_files.append(facts.readme_path)

    excerpts = 0
    for info in _important_files(facts):
        if excerpts >= MAX_EXCERPTS or info.path == facts.readme_path or is_test_file(info.path):
            continue
        if _add_excerpt(pack, info, reader, EXCERPT_MAX_LINES, EXCERPT_MAX_CHARS):
            excerpts += 1
    return pack


def _add_excerpt(
    pack: Pack, info: FileFacts, reader: Reader, max_lines: int, max_chars: int
) -> bool:
    text = reader(info.path)
    if text is None:
        return False
    lines = text.split("\n")
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()
    kept: list[str] = []
    used = 0
    for line in lines[:max_lines]:
        used += len(line) + 8
        if used > max_chars:
            break
        kept.append(line)
    if not kept:
        return False
    ok = pack.block(
        "file",
        numbered(kept),
        path=info.path,
        first_line="1",
        last_line=str(len(kept)),
        total_lines=str(len(lines)),
    )
    if ok:
        pack.included_files.append(info.path)
    return ok


def build_technologies_pack(facts: EvidenceFacts, boundary: str, budget_chars: int) -> Pack:
    pack = Pack(boundary, budget_chars)
    pack.block("facts", _facts_block(facts))
    pack.block("technologies", _technologies_block(facts))
    pack.block("dependencies", _dependencies_block(facts))
    return pack


def build_file_pack(
    facts: EvidenceFacts, info: FileFacts, reader: Reader, boundary: str, budget_chars: int
) -> Pack:
    pack = Pack(boundary, budget_chars)
    header = [
        f"path: {info.path}",
        f"language: {info.language or 'unknown'}",
        f"lines: {info.line_count}",
    ]
    if info.importance_reasons:
        header.append("why it is notable: " + ", ".join(info.importance_reasons))
    pack.block("file_info", "\n".join(header))

    if info.symbols:
        rows = [
            f"{s.kind} {s.qualified_name} L{s.start_line}-{s.end_line}: {s.signature}"
            for s in info.symbols[:80]
        ]
        pack.block("outline", "\n".join(rows))
    relations = []
    if info.internal_imports:
        relations.append("imports these repository files: " + ", ".join(info.internal_imports[:15]))
    if info.external_imports:
        relations.append("imports these libraries: " + ", ".join(info.external_imports[:20]))
    if info.imported_by:
        relations.append("is imported by: " + ", ".join(info.imported_by[:15]))
    pack.block("relationships", "\n".join(relations) or "(no imports found)")

    _add_excerpt(pack, info, reader, FILE_PACK_MAX_LINES, FILE_PACK_MAX_CHARS)
    return pack
