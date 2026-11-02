"""Rank files by how useful they are for understanding a repository.

Scores are the sum of simple, explainable signals (entry points, configuration, how many
files import it, ...). Every signal adds a human-readable reason, so the dashboard can
say *why* a file is listed, and none of it depends on an AI.
"""

import re
from pathlib import PurePosixPath

from app.services.analysis.dependencies import is_manifest
from app.services.analysis.models import FileAnalysis

IMPORTANT_THRESHOLD = 30

_TEST_DIRECTORIES = {"test", "tests", "__tests__", "spec", "specs", "e2e", "testing"}
_TEST_FILE = re.compile(
    r"(^test_.*\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$|tests?\.java$)", re.I
)

_CONFIG_FILES = {
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml",
    "alembic.ini", "tsconfig.json", "makefile", "application.properties", "application.yml",
    "application.yaml", "settings.py", "config.py", ".env.example", "next.config.js",
    "next.config.mjs", "next.config.ts", "webpack.config.js", "tailwind.config.js",
    "tailwind.config.ts", "pytest.ini", "tox.ini", "setup.cfg",
}  # fmt: skip
_CONFIG_PATTERN = re.compile(
    r"^(vite|vitest|jest|eslint|rollup|playwright|cypress)\.config\.[cm]?[jt]s$"
)

_PYTHON_ENTRY_NAMES = {"main.py", "app.py", "__main__.py", "manage.py", "wsgi.py", "asgi.py",
                       "server.py", "run.py", "cli.py"}  # fmt: skip
_ES_ENTRY_STEMS = {"index", "main", "app", "server"}
_ES_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
_ROLE_DIRECTORIES = {
    "routes", "api", "controllers", "controller", "models", "schemas", "services",
    "views", "handlers", "middleware", "db", "database", "repositories",
}  # fmt: skip


def is_test_file(path: str) -> bool:
    pure = PurePosixPath(path)
    return bool(_TEST_FILE.search(pure.name)) or any(
        p.lower() in _TEST_DIRECTORIES for p in pure.parts[:-1]
    )


def score_file(path: str, analysis: FileAnalysis | None, imported_by: int) -> tuple[int, list[str]]:
    pure = PurePosixPath(path)
    name = pure.name.lower()
    depth = len(pure.parts) - 1
    score = 0
    reasons: list[str] = []

    def add(points: int, reason: str) -> None:
        nonlocal score
        score += points
        reasons.append(reason)

    if depth == 0 and name.startswith("readme"):
        add(50, "Project README")
    if is_manifest(path) and depth <= 1:
        add(45, "Dependency manifest")

    if (name in _CONFIG_FILES or _CONFIG_PATTERN.match(name)) and depth <= 2:
        add(30, "Configuration")
    elif ".github/workflows/" in path and name.endswith((".yml", ".yaml")):
        add(30, "CI workflow")

    if analysis is not None and any(
        d.startswith("@SpringBootApplication") for s in analysis.symbols for d in s.decorators
    ):
        add(50, "Spring Boot application class")
    elif analysis is not None and analysis.has_main:
        add(45, "Application entry point")
    elif (name in _PYTHON_ENTRY_NAMES and depth <= 3) or (
        pure.suffix.lower() in _ES_EXTENSIONS
        and pure.stem.lower() in _ES_ENTRY_STEMS
        and depth <= 2
    ):
        add(35, "Likely entry point")

    role = next((p for p in pure.parts[:-1] if p.lower() in _ROLE_DIRECTORIES), None)
    if role:
        add(10, f"Core module ({role})")

    if imported_by:
        noun = "file" if imported_by == 1 else "files"
        add(min(30, 6 * imported_by), f"Imported by {imported_by} {noun}")

    if analysis is not None and len(analysis.symbols) >= 10:
        add(
            min(15, len(analysis.symbols) // 4),
            f"Defines {len(analysis.symbols)} functions and classes",
        )

    if is_test_file(path):
        score = max(0, score - 40)
        reasons.append("Test file")
    return score, reasons
