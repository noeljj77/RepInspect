"""The three AI features. Each one: build the evidence, ask the model, check the answer.

    facts from static analysis ─► evidence pack ─► model (structured JSON) ─► grounding ─► stored

The model's output is never stored directly. It passes through grounding first, so only
checked content reaches a person.
"""

from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from app.core.config import get_settings
from app.services.ai import context, prompts
from app.services.ai.grounding import (
    Grounding,
    SymbolRef,
    ground_file_explanation,
    ground_overview,
    ground_report,
    ground_technologies,
)
from app.services.ai.schemas import (
    RawFileExplanation,
    RawOverview,
    RawReport,
    RawTechnologies,
)
from app.services.llm.base import LLMProvider
from app.services.llm.errors import LLMBadResponse
from app.storage import artifacts

OVERVIEW_MAX_TOKENS = 6000
TECHNOLOGIES_MAX_TOKENS = 5000
FILE_MAX_TOKENS = 3000
REPORT_MAX_TOKENS = 6000


@dataclass
class Generated:
    content: BaseModel
    model: str
    input_tokens: int | None
    output_tokens: int | None


def source_reader(analysis_id: UUID):
    def read(path: str) -> str | None:
        data = artifacts.read_source_file(analysis_id, path)
        return data.decode("utf-8", errors="replace") if data is not None else None

    return read


def generate_overview(
    provider: LLMProvider, facts: context.EvidenceFacts, analysis_id: UUID
) -> Generated:
    reader = source_reader(analysis_id)
    boundary = context.new_boundary()
    pack = context.build_overview_pack(facts, reader, boundary, get_settings().ai_context_chars)
    result = provider.generate_structured(
        system=prompts.SYSTEM_OVERVIEW,
        prompt=prompts.overview_prompt(boundary, pack.text()),
        schema=RawOverview,
        max_output_tokens=OVERVIEW_MAX_TOKENS,
    )
    content = ground_overview(result.data, Grounding(facts.files, reader))
    return Generated(content, result.model, result.input_tokens, result.output_tokens)


def generate_technologies(provider: LLMProvider, facts: context.EvidenceFacts) -> Generated:
    names = [tech["name"] for tech in facts.technologies]
    if not names:
        raise LLMBadResponse("No technologies were detected, so there is nothing to explain.")
    boundary = context.new_boundary()
    pack = context.build_technologies_pack(facts, boundary, get_settings().ai_context_chars)
    result = provider.generate_structured(
        system=prompts.SYSTEM_TECHNOLOGIES,
        prompt=prompts.technologies_prompt(boundary, pack.text()),
        schema=RawTechnologies,
        max_output_tokens=TECHNOLOGIES_MAX_TOKENS,
    )
    content = ground_technologies(result.data, names)
    return Generated(content, result.model, result.input_tokens, result.output_tokens)


def generate_file_explanation(
    provider: LLMProvider, facts: context.EvidenceFacts, analysis_id: UUID, path: str
) -> Generated:
    info = facts.files[path]
    reader = source_reader(analysis_id)
    boundary = context.new_boundary()
    pack = context.build_file_pack(facts, info, reader, boundary, get_settings().ai_context_chars)
    result = provider.generate_structured(
        system=prompts.SYSTEM_FILE,
        prompt=prompts.file_prompt(boundary, pack.text()),
        schema=RawFileExplanation,
        max_output_tokens=FILE_MAX_TOKENS,
    )
    symbols = [SymbolRef(s.name, s.qualified_name, s.kind, s.start_line) for s in info.symbols]
    content = ground_file_explanation(result.data, symbols, Grounding(facts.files, reader))
    return Generated(content, result.model, result.input_tokens, result.output_tokens)


def generate_report(
    provider: LLMProvider, facts: context.EvidenceFacts, analysis_id: UUID
) -> Generated:
    """Interview notes, from the same evidence as the overview."""
    reader = source_reader(analysis_id)
    boundary = context.new_boundary()
    pack = context.build_overview_pack(facts, reader, boundary, get_settings().ai_context_chars)
    result = provider.generate_structured(
        system=prompts.SYSTEM_REPORT,
        prompt=prompts.report_prompt(boundary, pack.text()),
        schema=RawReport,
        max_output_tokens=REPORT_MAX_TOKENS,
    )
    content = ground_report(result.data, Grounding(facts.files, reader))
    return Generated(content, result.model, result.input_tokens, result.output_tokens)
