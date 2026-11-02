from pathlib import Path

import pytest

from app.services.analysis import runner
from app.services.analysis.languages import detect_language
from app.services.analysis.runner import SourceFile, analyze_directory

REPO = {
    "README.md": "# Demo\n",
    "Dockerfile": "FROM python:3.11\n",
    "backend/pyproject.toml": (
        '[project]\nname = "demo"\ndependencies = ["fastapi>=0.100", "sqlalchemy"]\n'
        '[project.optional-dependencies]\ndev = ["pytest"]\n'
    ),
    "backend/app/__init__.py": "",
    "backend/app/main.py": (
        "from fastapi import FastAPI\nfrom app.api import routes\n\n"
        "app = FastAPI()\n\n\ndef create_app():\n    return app\n\n\n"
        'if __name__ == "__main__":\n    create_app()\n'
    ),
    "backend/app/api/__init__.py": "",
    "backend/app/api/routes.py": (
        "from fastapi import APIRouter\nfrom app.db.session import engine\n\n"
        "router = APIRouter()\n\n\n@router.get('/x')\ndef x():\n    return engine\n"
    ),
    "backend/app/db/session.py": "import sqlalchemy\n\nengine = sqlalchemy.create_engine('sqlite://')\n",
    "backend/tests/test_routes.py": "from app.api import routes\n\n\ndef test_x():\n    assert routes\n",
    "frontend/package.json": '{\n  "dependencies": {"react": "^19"},\n  "devDependencies": {"vite": "^8"}\n}\n',
    "frontend/src/main.tsx": "import React from 'react';\nimport App from './App';\nconsole.log(React, App);\n",
    "frontend/src/App.tsx": "import { api } from './api/client';\nexport default function App() { return api; }\n",
    "frontend/src/api/client.ts": "export const api = 1;\nexport function get() {}\n",
    "src/main/java/com/x/App.java": (
        "package com.x;\nimport com.x.util.Strings;\n@SpringBootApplication\npublic class App {\n"
        "  public static void main(String[] a) { Strings.go(); }\n}\n"
    ),
    "src/main/java/com/x/util/Strings.java": "package com.x.util;\npublic class Strings { public static void go() {} }\n",
    "notes.xyz": "unknown language\n",
}  # fmt: skip


def build(root: Path, files: dict[str, str]) -> list[SourceFile]:
    sources = []
    for path, text in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        sources.append(SourceFile(path, detect_language(path), len(text.encode()), lines))
    return sources


@pytest.fixture
def output(tmp_path):
    return analyze_directory(tmp_path, build(tmp_path, REPO))


def test_every_file_gets_a_result_and_parsers_only_run_where_they_exist(output):
    assert set(output.files) == set(REPO)
    assert output.files["backend/app/main.py"].analysis.has_main is True
    assert output.files["README.md"].analysis is None
    assert output.files["notes.xyz"].analysis is None


def test_symbols_are_extracted_across_languages(output):
    def names(path):
        return [s.qualified_name for s in output.files[path].analysis.symbols]

    assert names("backend/app/main.py") == ["create_app"]
    assert names("backend/app/api/routes.py") == ["x"]
    assert names("frontend/src/App.tsx") == ["App"]
    assert names("frontend/src/api/client.ts") == ["get"]
    assert names("src/main/java/com/x/App.java") == ["App", "App.main"]


def test_imports_resolve_to_files_in_the_repository(output):
    edges = {(i.path, i.ref.module): sorted(i.targets) for i in output.imports if i.targets}

    assert edges[("backend/app/main.py", "app.api")] == [
        "backend/app/api/__init__.py",
        "backend/app/api/routes.py",
    ]
    assert edges[("backend/app/api/routes.py", "app.db.session")] == ["backend/app/db/session.py"]
    assert edges[("frontend/src/main.tsx", "./App")] == ["frontend/src/App.tsx"]
    assert edges[("frontend/src/App.tsx", "./api/client")] == ["frontend/src/api/client.ts"]
    assert edges[("src/main/java/com/x/App.java", "com.x.util.Strings")] == [
        "src/main/java/com/x/util/Strings.java"
    ]


def test_libraries_are_not_treated_as_repository_files(output):
    unresolved = {i.ref.module for i in output.imports if not i.targets}

    assert {"fastapi", "sqlalchemy", "react"} <= unresolved


def test_dependencies_are_read_from_manifests(output):
    rows = {(d.ecosystem, d.name, d.scope) for d in output.dependencies}

    assert ("pypi", "fastapi", "runtime") in rows
    assert ("pypi", "pytest", "dev") in rows
    assert ("npm", "react", "runtime") in rows
    assert ("npm", "vite", "dev") in rows


def test_technologies_combine_dependencies_imports_and_files(output):
    found = {t.name: t for t in output.technologies}

    assert {"FastAPI", "SQLAlchemy", "React", "Vite", "Docker", "pytest"} <= set(found)
    kinds = {e.kind for e in found["FastAPI"].evidence}
    assert kinds == {"dependency", "import"}
    assert found["Docker"].evidence[0].path == "Dockerfile"


def test_important_files_rank_above_ordinary_ones(output):
    score = {p: r.importance_score for p, r in output.files.items()}

    assert score["README.md"] >= 30
    assert score["backend/pyproject.toml"] >= 30
    assert score["backend/app/main.py"] >= 30  # has a main guard
    assert score["src/main/java/com/x/App.java"] >= 30  # Spring Boot application class
    assert score["backend/app/api/routes.py"] > score["backend/app/db/session.py"] > 0
    assert score["backend/tests/test_routes.py"] < 30
    assert "Imported by 2 files" in output.files["backend/app/api/routes.py"].importance_reasons
    assert output.files["notes.xyz"].importance_score == 0


def test_statistics(output):
    stats = output.stats
    languages = {row["name"]: row for row in stats["languages"]}

    assert languages["Python"]["files"] == 6
    assert languages["Python"]["is_programming"] is True
    assert languages["Markdown"]["is_programming"] is False
    assert "notes.xyz" not in str(stats["languages"])  # unknown language: not counted
    assert stats["languages"][0]["lines"] >= stats["languages"][-1]["lines"]  # sorted by size

    totals = stats["totals"]
    assert totals["files"] == len(REPO)
    assert totals["symbols"] == sum(totals["symbols_by_kind"].values()) > 0
    assert totals["internal_imports"] >= 5
    assert totals["dependencies"] == len(output.dependencies)
    assert totals["test_files"] == 1
    assert totals["parse_errors"] == 0


def test_a_broken_file_is_flagged_but_does_not_stop_the_rest(tmp_path):
    files = {"ok.py": "def fine(): ...\n", "bad.py": "def broken(:\n", "bad.js": "function x( {\n"}

    output = analyze_directory(tmp_path, build(tmp_path, files))

    assert output.files["ok.py"].analysis.parse_error is False
    assert output.files["bad.py"].analysis.parse_error is True
    assert output.stats["totals"]["parse_errors"] == 2


def test_a_parser_crash_is_contained(tmp_path, monkeypatch):
    files = {"a.py": "x = 1\n", "b.py": "y = 2\n"}

    def flaky(language, path, text):
        if path == "a.py":
            raise RuntimeError("parser bug")
        return None

    monkeypatch.setattr(runner, "parse_file", flaky)

    output = analyze_directory(tmp_path, build(tmp_path, files))

    assert output.files["a.py"].analysis.parse_error is True
    assert set(output.files) == {"a.py", "b.py"}


def test_missing_files_are_skipped_quietly(tmp_path):
    sources = build(tmp_path, {"here.py": "x = 1\n"})
    sources.append(SourceFile("gone.py", "Python", 10, 1))

    output = analyze_directory(tmp_path, sources)

    assert output.files["gone.py"].analysis is None


def test_an_empty_repository_gives_empty_results(tmp_path):
    output = analyze_directory(tmp_path, [])

    assert output.files == {} and output.technologies == [] and output.dependencies == []
    assert output.stats["totals"]["files"] == 0
