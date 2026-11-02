"""Split files into chunks: the units that are searched and shown to the model.

A good chunk is something a person would quote when answering a question: a whole
function, a class, a section of a README. So chunks follow the symbols found by static
analysis:

    file ─┬─ code between symbols (imports, constants)   → line windows
          ├─ a function or small class                   → one chunk
          └─ a class too big for one chunk               → its methods, one chunk each,
                                                            plus the code between them

Files without symbols (configuration, scripts in unsupported languages) are cut into
overlapping line windows, and Markdown is cut at its headings. Every chunk keeps its
exact line range, so an answer can point at the lines it used.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

MAX_LINES = 60  # a chunk longer than this is split
MAX_CHARS = 2400  # about 600 tokens, a little over what the embedding model reads
WINDOW_LINES = 40  # size of line windows for code without symbols
OVERLAP_LINES = 8  # windows overlap so a statement cut at the edge is still found whole
MIN_CONTENT_CHARS = 20  # gaps with less than this (ignoring spaces) are not worth a chunk
MAX_LINE_CHARS = 1000  # minified lines are clipped

# Generated or data files: large, repetitive, and never what a question is about.
SKIPPED_NAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "pipfile.lock",
    "cargo.lock",
    "composer.lock",
    "gemfile.lock",
    "go.sum",
}
SKIPPED_SUFFIXES = {".svg", ".map", ".csv", ".tsv", ".lock", ".min.js", ".min.css"}
MAX_INDEXED_BYTES = 300_000
MAX_DATA_FILE_BYTES = 50_000  # JSON/YAML larger than this is data, not configuration
DOC_SUFFIXES = {".md", ".markdown", ".rst", ".txt"}
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")


@dataclass(frozen=True)
class Span:
    """A symbol's place in a file, as found by static analysis."""

    name: str  # qualified name, e.g. "UserService.create"
    kind: str
    start: int
    end: int


@dataclass(frozen=True)
class Chunk:
    path: str
    start_line: int
    end_line: int
    symbol: str | None  # the function, class or heading this chunk belongs to
    kind: str  # a symbol kind, "code" or "doc"
    text: str


def should_index(path: str, size_bytes: int) -> bool:
    name = PurePosixPath(path).name.lower()
    if name in SKIPPED_NAMES or any(name.endswith(s) for s in SKIPPED_SUFFIXES):
        return False
    if size_bytes > MAX_INDEXED_BYTES:
        return False
    is_data = name.endswith((".json", ".yaml", ".yml", ".xml"))
    return not (is_data and size_bytes > MAX_DATA_FILE_BYTES)


def split_lines(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").split("\n")
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()  # a final newline does not start another line
    return [line if len(line) <= MAX_LINE_CHARS else line[:MAX_LINE_CHARS] for line in lines]


def _looks_minified(lines: list[str]) -> bool:
    long_lines = sum(1 for line in lines if len(line) >= MAX_LINE_CHARS)
    return long_lines > 0 and long_lines * 4 >= len(lines)


def chunk_file(path: str, text: str, symbols: Iterable[Span] = ()) -> list[Chunk]:
    lines = split_lines(text)
    if not lines or _looks_minified(lines):
        return []
    total = len(lines)
    if PurePosixPath(path).suffix.lower() in DOC_SUFFIXES:
        return (
            _markdown(path, lines)
            if path.lower().endswith((".md", ".markdown"))
            else (_windows(path, lines, 1, total, None, "doc"))
        )

    spans = sorted(
        {
            Span(s.name, s.kind, max(1, s.start), min(total, s.end))
            for s in symbols
            if s.start <= total and s.end >= s.start
        },
        key=lambda s: (s.start, -s.end),
    )
    return _cover(path, lines, 1, total, spans, parent=None)


# --- building blocks ------------------------------------------------------------------------


def _text(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start - 1 : end])


def _meaningful(lines: list[str], start: int, end: int) -> bool:
    return sum(len(line.strip()) for line in lines[start - 1 : end]) >= MIN_CONTENT_CHARS


def _fits(lines: list[str], start: int, end: int) -> bool:
    return end - start + 1 <= MAX_LINES and len(_text(lines, start, end)) <= MAX_CHARS


def _windows(
    path: str, lines: list[str], start: int, end: int, symbol: str | None, kind: str
) -> list[Chunk]:
    """Overlapping windows over a range, each within the line and character limits."""
    if not _meaningful(lines, start, end):
        return []
    if _fits(lines, start, end):
        return [Chunk(path, start, end, symbol, kind, _text(lines, start, end))]

    chunks: list[Chunk] = []
    first = start
    while first <= end:
        last, used = first, len(lines[first - 1])
        while last < end and last - first + 1 < WINDOW_LINES:
            used += len(lines[last]) + 1
            if used > MAX_CHARS:
                break
            last += 1
        if _meaningful(lines, first, last):
            chunks.append(Chunk(path, first, last, symbol, kind, _text(lines, first, last)))
        if last >= end:
            break
        first = max(last - OVERLAP_LINES + 1, first + 1)
    return chunks


def _outermost(spans: list[Span]) -> list[Span]:
    """Symbols not inside another one (spans are sorted by start, longest first)."""
    top: list[Span] = []
    for span in spans:
        if not top or span.start > top[-1].end:
            top.append(span)
    return top


def _cover(
    path: str, lines: list[str], start: int, end: int, spans: list[Span], parent: Span | None
) -> list[Chunk]:
    """Chunks for every meaningful line in [start, end], following the symbols in it."""
    chunks: list[Chunk] = []
    gap_symbol = parent.name if parent else None
    gap_kind = parent.kind if parent else "code"
    cursor = start
    for span in _outermost(spans):
        if span.start > cursor:
            chunks += _windows(path, lines, cursor, span.start - 1, gap_symbol, gap_kind)
        chunks += _symbol(path, lines, span, spans)
        cursor = span.end + 1
    if cursor <= end:
        chunks += _windows(path, lines, cursor, end, gap_symbol, gap_kind)
    return chunks


def _symbol(path: str, lines: list[str], span: Span, spans: list[Span]) -> list[Chunk]:
    if _fits(lines, span.start, span.end):
        return [
            Chunk(
                path, span.start, span.end, span.name, span.kind, _text(lines, span.start, span.end)
            )
        ]
    inner = [
        Span(s.name, s.kind, max(s.start, span.start), min(s.end, span.end))
        for s in spans
        if s != span and span.start <= s.start <= span.end
    ]
    if inner:
        return _cover(path, lines, span.start, span.end, inner, parent=span)
    return _windows(path, lines, span.start, span.end, span.name, span.kind)


def _markdown(path: str, lines: list[str]) -> list[Chunk]:
    """One chunk (or a few windows) per section, named after its heading."""
    starts = [(1, None)]
    in_fence = False
    for number, line in enumerate(lines, start=1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence  # a "#" inside a code block is not a heading
        match = None if in_fence else _HEADING.match(line)
        if match and number > 1:
            starts.append((number, match.group(1)))
        elif match:
            starts[0] = (1, match.group(1))

    chunks: list[Chunk] = []
    for index, (first, heading) in enumerate(starts):
        last = starts[index + 1][0] - 1 if index + 1 < len(starts) else len(lines)
        chunks += _windows(path, lines, first, last, heading, "doc")
    return chunks


# --- text used for searching --------------------------------------------------------------------

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_WORD_PART = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
MAX_KEYWORDS = 400


def split_identifier(identifier: str) -> list[str]:
    """getUserById → [get, user, by, id]; HTTPServer → [http, server]."""
    return [part.lower() for part in _WORD_PART.findall(identifier)]


def keywords(chunk: Chunk) -> str:
    """Extra words for keyword search: identifiers split into their parts, and path parts.

    Postgres full-text search already splits snake_case, but not camelCase, so without
    this a question about "user service" would not find `UserService`.
    """
    seen: dict[str, None] = {}
    sources = [chunk.path.replace("/", " ").replace(".", " "), chunk.symbol or "", chunk.text]
    for source in sources:
        for identifier in _IDENTIFIER.findall(source):
            parts = split_identifier(identifier)
            if len(parts) > 1:
                for part in parts:
                    if len(part) > 1:
                        seen.setdefault(part, None)
            if len(seen) >= MAX_KEYWORDS:
                return " ".join(seen)
    return " ".join(seen)


def embedding_text(chunk: Chunk) -> str:
    """What the embedding model reads: where the chunk is, then the code itself."""
    header = f"File: {chunk.path}\n"
    if chunk.symbol:
        header += f"Symbol: {chunk.symbol}\n"
    return header + chunk.text
