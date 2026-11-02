"""Answer a question: search, ask the model, check what it cited.

    question ─► retrieval ─► excerpts (fenced) ─► model ─► grounding ─► stored answer

Grounding reuses the checks from the AI explanations: a citation is kept only if its
quote really appears in the cited file, and its line numbers are replaced by where the
quote really is. The [n] markers in the answer are then renumbered to match the citations
that survived, and markers whose citation was dropped are removed.
"""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import get_settings
from app.services.ai.context import new_boundary
from app.services.ai.grounding import Grounding
from app.services.llm.base import LLMProvider
from app.services.rag import prompts
from app.services.rag.retrieval import Retrieved
from app.services.rag.schemas import ChatAnswer, RawChatAnswer, Source
from app.storage import artifacts

ANSWER_MAX_TOKENS = 2500
MAX_ANSWER_CHARS = 6000
MAX_CITATIONS = 12
_MARKER = re.compile(r"\s?\[(\d+(?:\s*,\s*\d+)*)\]")
# Markers are removed from earlier answers before they are sent back as conversation history.
_ANY_MARKER = re.compile(r"\s?\[\d+(?:\s*,\s*\d+)*\]")


@dataclass
class Answered:
    content: ChatAnswer
    model: str
    input_tokens: int | None
    output_tokens: int | None


def renumber_markers(text: str, mapping: dict[int, int]) -> str:
    """Rewrite [n] markers using `mapping` (old → new number); drop unknown numbers."""

    def replace(match: re.Match) -> str:
        numbers: list[int] = []
        for raw in match.group(1).split(","):
            new = mapping.get(int(raw))
            if new is not None and new not in numbers:
                numbers.append(new)
        if not numbers:
            return ""
        leading = " " if match.group(0).startswith((" ", "\n", "\t")) else ""
        return f"{leading}[{', '.join(str(n) for n in numbers)}]"

    return _MARKER.sub(replace, text)


def strip_markers(text: str) -> str:
    return _ANY_MARKER.sub("", text)


def ground_answer(raw: RawChatAnswer, grounding: Grounding, sources: list[Source]) -> ChatAnswer:
    kept = []
    mapping: dict[int, int] = {}
    for number, citation in enumerate(raw.citations, start=1):
        verified = grounding.verify_citation(citation)
        if verified is None:
            continue
        same = next(
            (
                i
                for i, k in enumerate(kept, start=1)
                if (k.path, k.start_line, k.end_line)
                == (verified.path, verified.start_line, verified.end_line)
            ),
            None,
        )
        if same is not None:
            mapping[number] = same
        elif len(kept) < MAX_CITATIONS:
            kept.append(verified)
            mapping[number] = len(kept)

    answer = renumber_markers(raw.answer.strip(), mapping)
    if len(answer) > MAX_ANSWER_CHARS:
        answer = answer[: MAX_ANSWER_CHARS - 1].rstrip() + "…"
    return ChatAnswer(
        answerable=raw.answerable,
        answer=answer,
        citations=kept,
        removed_citations=len(raw.citations) - len(mapping),
        ungrounded_paths=grounding.ungrounded_paths(answer),
        sources=sources,
    )


def answer_question(
    provider: LLMProvider,
    question: str,
    history: list[tuple[str, str]],
    excerpts: list[Retrieved],
    grounding: Grounding,
) -> Answered:
    boundary = new_boundary()
    pack = prompts.build_excerpts(boundary, excerpts, get_settings().rag_context_chars + 4_000)
    result = provider.generate_structured(
        system=prompts.SYSTEM_CHAT,
        prompt=prompts.chat_prompt(boundary, pack.text(), history, question),
        schema=RawChatAnswer,
        max_output_tokens=ANSWER_MAX_TOKENS,
    )
    sources = [
        Source(
            path=e.path,
            start_line=e.start_line,
            end_line=e.end_line,
            symbol=e.symbol,
            matched_by=e.matched_by,
        )
        for e in excerpts
    ]
    return Answered(
        ground_answer(result.data, grounding, sources),
        result.model,
        result.input_tokens,
        result.output_tokens,
    )


def file_reader(analysis_id: uuid.UUID) -> Callable[[str], str | None]:
    """Reads files of the stored snapshot, for checking quotes."""

    def read(path: str) -> str | None:
        data = artifacts.read_source_file(analysis_id, path)
        return data.decode("utf-8", errors="replace") if data is not None else None

    return read
