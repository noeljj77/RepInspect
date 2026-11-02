"""The interface every language model provider implements.

Features (overview, technology and file explanations) depend only on this, so adding a
provider means writing one class and choosing it in settings.
"""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResult(Generic[T]):
    data: T
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    model: str

    def generate_structured(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[T],
        max_output_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResult[T]:
        """Ask the model for output that matches `schema`, parsed and validated.

        Raises an LLMError subclass for anything that goes wrong. Implementations retry
        temporary failures themselves, so callers see only the final outcome.
        """
        ...
