"""Source parsers. Each turns the text of one file into a FileAnalysis.

Parsing only reads text into a syntax tree. It never imports or runs the code.
To support another language, add a module here and register it in `parse_file`.
"""

from app.services.analysis.models import FileAnalysis
from app.services.analysis.parsers import python_ast, treesitter

TREESITTER_LANGUAGES = frozenset({"JavaScript", "TypeScript", "Java"})


def parse_file(language: str | None, path: str, source: str) -> FileAnalysis | None:
    """Analyze one file, or return None if its language has no parser."""
    if language == "Python":
        return python_ast.parse(source)
    if language in TREESITTER_LANGUAGES:
        return treesitter.parse(language, path, source)
    return None
