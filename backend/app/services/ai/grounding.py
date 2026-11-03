"""Check what a model said against the real repository.

A model can produce fluent, confident text that is wrong. So nothing it says is trusted
just because it was said:

- A citation counts only if the file exists in the analyzed repository AND the text it
  quotes really appears there. The reported lines are always where the text really is,
  so wrong line numbers are corrected. If the quote is not found, the citation is thrown away.
- A finding is "verified" only if at least one citation survived and it does not mention
  files that do not exist.
- Technology and symbol names the model adds that were not in the facts it was given are
  dropped.

These checks run on every result before it is stored.
"""

import bisect
import re
from collections import defaultdict
from collections.abc import Callable, Iterable

from app.services.ai.schemas import (
    OVERVIEW_SECTIONS,
    Citation,
    Decision,
    FileExplanationContent,
    Finding,
    Improvement,
    KeySymbol,
    OverviewContent,
    OverviewSection,
    RawCitation,
    RawFileExplanation,
    RawFinding,
    RawOverview,
    RawReport,
    RawTechnologies,
    ReportContent,
    TechnologiesContent,
    TechnologyExplanation,
)

MAX_SUMMARY = 900
MAX_STATEMENT = 500
MAX_QUOTE_SHOWN = 300
MAX_QUOTE_CHECKED = 600
MIN_QUOTE_CHARS = 4
MAX_CITATIONS_PER_FINDING = 4
MAX_FINDINGS = 6
MAX_LIST_ITEMS = 5
MAX_ITEM_CHARS = 300

_LINE_NUMBER_PREFIX = re.compile(r"(?m)^\s*\d+\|\s?")
_WHITESPACE = re.compile(r"\s+")

_PATH_TOKEN = re.compile(r"(?<![\w/.:@-])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,8})(?![\w/])")
# Bare file names. "js", "html" and "css" are left out on purpose, so "Node.js" and
# "Next.js" are not mistaken for files.
_BARE_FILE = re.compile(
    r"(?<![\w/.:@-])([\w-]+(?:\.[\w-]+)*\.(?:py|ts|tsx|jsx|java|json|toml|yml|yaml|xml|gradle|"
    r"properties|sql|md|ini|cfg|lock|txt|kts))(?![\w/])"
)
_DOMAIN_TLDS = {"com", "org", "net", "io", "dev", "app", "co", "ai", "edu", "gov"}


def _normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", _LINE_NUMBER_PREFIX.sub("", text)).strip()


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class Grounding:
    """Knows which files exist and can read them, to confirm claims about them."""

    def __init__(self, paths: Iterable[str], reader: Callable[[str], str | None]):
        self.paths = set(paths)
        self._reader = reader
        self._lines: dict[str, list[str] | None] = {}
        self._flat: dict[str, tuple[str, list[int], list[int]] | None] = {}

        self._by_suffix: dict[str, list[str]] = defaultdict(list)
        for path in self.paths:
            parts = path.split("/")
            for start in range(len(parts)):
                self._by_suffix["/".join(parts[start:])].append(path)

    # --- files -----------------------------------------------------------------------

    def resolve_path(self, raw: str) -> str | None:
        """The stored path this refers to. "app/main.py" resolves to "backend/app/main.py"
        when that is the only match, and to nothing when it is ambiguous or unknown."""
        cleaned = raw.strip().strip("`'\"").replace("\\", "/")
        while cleaned.startswith("./"):
            cleaned = cleaned[2:]
        cleaned = cleaned.lstrip("/")
        if cleaned in self.paths:
            return cleaned
        matches = self._by_suffix.get(cleaned, [])
        return matches[0] if len(matches) == 1 else None

    def lines(self, path: str) -> list[str] | None:
        if path not in self._lines:
            text = self._reader(path)
            if text is None:
                self._lines[path] = None
            else:
                lines = text.split("\n")
                if len(lines) > 1 and lines[-1] == "":
                    lines.pop()  # a final newline does not start another line
                self._lines[path] = lines
        return self._lines[path]

    def _searchable(self, path: str) -> tuple[str, list[int], list[int]] | None:
        """The whole file as one whitespace-normalised string, with a map back to lines."""
        if path not in self._flat:
            lines = self.lines(path)
            if lines is None:
                self._flat[path] = None
            else:
                pieces: list[str] = []
                starts: list[int] = []
                line_numbers: list[int] = []
                position = 0
                for number, line in enumerate(lines, start=1):
                    normalized = _normalize(line)
                    if not normalized:
                        continue
                    starts.append(position)
                    line_numbers.append(number)
                    pieces.append(normalized)
                    position += len(normalized) + 1
                self._flat[path] = (" ".join(pieces), starts, line_numbers)
        return self._flat[path]

    # --- citations ---------------------------------------------------------------------

    def verify_citation(self, citation: RawCitation) -> Citation | None:
        path = self.resolve_path(citation.path)
        lines = self.lines(path) if path else None
        quote = _normalize(citation.quote)[:MAX_QUOTE_CHECKED]
        if path is None or lines is None or len(quote) < MIN_QUOTE_CHARS:
            return None

        total = len(lines)
        claimed = min(max(citation.start_line, 1), total)
        shown = _clip(_LINE_NUMBER_PREFIX.sub("", citation.quote), MAX_QUOTE_SHOWN)

        # Report where the quoted text really is, not where the model said it was. If it
        # appears in several places, the one nearest the claimed line wins. If it appears
        # nowhere in the file, the citation is thrown away.
        located = self._locate(path, quote, near=claimed)
        if located is None:
            return None
        return Citation(path=path, start_line=located[0], end_line=located[1], quote=shown)

    def _locate(self, path: str, quote: str, near: int) -> tuple[int, int] | None:
        flat = self._searchable(path)
        if flat is None:
            return None
        text, starts, line_numbers = flat
        best: tuple[int, int] | None = None
        index = text.find(quote)
        while index != -1:
            first = line_numbers[bisect.bisect_right(starts, index) - 1]
            last = line_numbers[bisect.bisect_right(starts, index + len(quote) - 1) - 1]
            if best is None or abs(first - near) < abs(best[0] - near):
                best = (first, last)
            index = text.find(quote, index + 1)
        return best

    # --- mentions of files in prose -------------------------------------------------------

    def ungrounded_paths(self, text: str) -> list[str]:
        """File names mentioned in the text that are not among the analyzed files."""
        found: list[str] = []
        for pattern in (_PATH_TOKEN, _BARE_FILE):
            for match in pattern.finditer(text):
                token = match.group(1)
                if token in found or self._is_domain(token) or self._exists(token):
                    continue
                found.append(token)
        # A bare name that is really the tail of a longer path was already judged as a path.
        return [t for t in found if not any(o != t and o.endswith("/" + t) for o in found)]

    def _exists(self, token: str) -> bool:
        return self.resolve_path(token) is not None or token in self._by_suffix

    @staticmethod
    def _is_domain(token: str) -> bool:
        first = token.split("/")[0]
        return "." in first and first.rsplit(".", 1)[-1].lower() in _DOMAIN_TLDS

    # --- findings ---------------------------------------------------------------------------

    def ground_finding(self, raw: RawFinding) -> tuple[Finding, int]:
        """Returns the checked finding and how many of its citations were dropped."""
        statement = _clip(raw.statement, MAX_STATEMENT)
        kept: list[Citation] = []
        for citation in raw.citations:
            verified = self.verify_citation(citation)
            if verified is not None and not any(_same_place(verified, k) for k in kept):
                kept.append(verified)
        kept = kept[:MAX_CITATIONS_PER_FINDING]
        dropped = len(raw.citations) - len(kept)

        unknown = self.ungrounded_paths(statement)
        return (
            Finding(
                statement=statement,
                citations=kept,
                verified=bool(kept) and not unknown,
                ungrounded_paths=unknown,
            ),
            max(dropped, 0),
        )


def _same_place(a: Citation, b: Citation) -> bool:
    return (a.path, a.start_line, a.end_line) == (b.path, b.start_line, b.end_line)


def _clean_list(items: list[str]) -> list[str]:
    cleaned = [_clip(item, MAX_ITEM_CHARS) for item in items if item.strip()]
    return cleaned[:MAX_LIST_ITEMS]


# --- whole results ----------------------------------------------------------------------------


def ground_overview(raw: RawOverview, grounding: Grounding) -> OverviewContent:
    by_key = {}
    for section in raw.sections:
        by_key.setdefault(section.key, section)  # if the model repeats a section, the first wins

    removed = 0
    sections: list[OverviewSection] = []
    for key, title in OVERVIEW_SECTIONS:
        section = by_key.get(key)
        if section is None:
            sections.append(
                OverviewSection(key=key, title=title, summary="", determined=False, findings=[])
            )
            continue

        findings = []
        for raw_finding in section.findings[:MAX_FINDINGS]:
            finding, dropped = grounding.ground_finding(raw_finding)
            removed += dropped
            if finding.statement:
                findings.append(finding)
        summary = _clip(section.summary, MAX_SUMMARY)
        sections.append(
            OverviewSection(
                key=key,
                title=title,
                summary=summary,
                determined=section.determined and bool(summary or findings),
                findings=findings,
                ungrounded_paths=grounding.ungrounded_paths(summary),
            )
        )
    return OverviewContent(sections=sections, removed_citations=removed)


def ground_technologies(raw: RawTechnologies, allowed_names: Iterable[str]) -> TechnologiesContent:
    """Keep explanations only for technologies that were actually detected."""
    canonical = {name.lower(): name for name in allowed_names}
    result: dict[str, TechnologyExplanation] = {}
    for item in raw.technologies:
        name = canonical.get(item.name.strip().lower())
        if name is None or name in result:
            continue  # invented, or repeated
        result[name] = TechnologyExplanation(
            name=name,
            what_it_is=_clip(item.what_it_is, MAX_SUMMARY),
            plausible_reason=_clip(item.plausible_reason, MAX_SUMMARY),
            advantages=_clean_list(item.advantages),
            alternatives=_clean_list(item.alternatives),
            trade_offs=_clean_list(item.trade_offs),
        )
    return TechnologiesContent(technologies=list(result.values()))


class SymbolRef:
    """A symbol that really exists in the file being explained."""

    def __init__(self, name: str, qualified_name: str, kind: str, start_line: int):
        self.name = name
        self.qualified_name = qualified_name
        self.kind = kind
        self.start_line = start_line


def ground_file_explanation(
    raw: RawFileExplanation, symbols: list[SymbolRef], grounding: Grounding
) -> FileExplanationContent:
    removed = 0
    findings = []
    for raw_finding in raw.findings[:MAX_FINDINGS]:
        finding, dropped = grounding.ground_finding(raw_finding)
        removed += dropped
        if finding.statement:
            findings.append(finding)

    lookup: dict[str, SymbolRef] = {}
    for symbol in symbols:
        lookup.setdefault(symbol.qualified_name, symbol)
        lookup.setdefault(symbol.name, symbol)
    key_symbols: list[KeySymbol] = []
    seen: set[str] = set()
    for item in raw.key_symbols:
        symbol = lookup.get(item.name.strip())
        if symbol is None or symbol.qualified_name in seen or not item.explanation.strip():
            continue  # invented, repeated or empty
        seen.add(symbol.qualified_name)
        key_symbols.append(
            KeySymbol(
                name=symbol.name,
                qualified_name=symbol.qualified_name,
                kind=symbol.kind,
                start_line=symbol.start_line,
                explanation=_clip(item.explanation, MAX_ITEM_CHARS),
            )
        )

    purpose = _clip(raw.purpose, MAX_SUMMARY)
    return FileExplanationContent(
        purpose=purpose,
        determined=raw.determined and bool(purpose),
        inputs_outputs=_clip(raw.inputs_outputs, MAX_SUMMARY),
        findings=findings,
        key_symbols=key_symbols[:12],
        ungrounded_paths=grounding.ungrounded_paths(f"{purpose} {raw.inputs_outputs}"),
        removed_citations=removed,
    )


def _ground_findings(
    raw: list[RawFinding], grounding: Grounding, limit: int = MAX_FINDINGS
) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    removed = 0
    for raw_finding in raw[:limit]:
        finding, dropped = grounding.ground_finding(raw_finding)
        removed += dropped
        if finding.statement:
            findings.append(finding)
    return findings, removed


def ground_report(raw: RawReport, grounding: Grounding) -> ReportContent:
    walkthrough, removed_walk = _ground_findings(raw.walkthrough, grounding, limit=8)
    highlights, removed_high = _ground_findings(raw.highlights, grounding)
    decisions: list[Decision] = []
    removed_dec = 0
    for item in raw.decisions[:MAX_FINDINGS]:
        finding, dropped = grounding.ground_finding(
            RawFinding(statement=item.decision, citations=item.citations)
        )
        removed_dec += dropped
        if finding.statement:
            decisions.append(
                Decision(
                    finding=finding,
                    alternatives=_clean_list(item.alternatives),
                    trade_offs=_clean_list(item.trade_offs),
                )
            )
    improvements = [
        Improvement(idea=_clip(i.idea, MAX_STATEMENT), reason=_clip(i.reason, MAX_STATEMENT))
        for i in raw.improvements[:MAX_LIST_ITEMS]
        if i.idea.strip()
    ]
    pitch, problem = _clip(raw.pitch, MAX_SUMMARY), _clip(raw.problem, MAX_SUMMARY)
    return ReportContent(
        pitch=pitch,
        problem=problem,
        walkthrough=walkthrough,
        decisions=decisions,
        highlights=highlights,
        improvements=improvements,
        ungrounded_paths=grounding.ungrounded_paths(f"{pitch} {problem}"),
        removed_citations=removed_walk + removed_high + removed_dec,
    )
