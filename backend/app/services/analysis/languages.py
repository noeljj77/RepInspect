"""Map file names to programming languages.

Kept as plain data so adding a language is a one-line change.
"""

from pathlib import PurePosixPath

EXTENSION_LANGUAGES = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".sh": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".gradle": "Gradle",
    ".properties": "Properties",
}

FILENAME_LANGUAGES = {
    "dockerfile": "Dockerfile",
    "makefile": "Makefile",
}

# Languages the static analysis engine can parse (Milestone 4 onwards).
SUPPORTED_ANALYSIS_LANGUAGES = frozenset({"Python", "JavaScript", "TypeScript", "Java"})


def detect_language(path: str) -> str | None:
    name = PurePosixPath(path).name.lower()
    if name in FILENAME_LANGUAGES:
        return FILENAME_LANGUAGES[name]
    return EXTENSION_LANGUAGES.get(PurePosixPath(name).suffix)
