from app.services.analysis.dependencies import MAVEN, NPM, PYPI, Dependency
from app.services.analysis.models import ImportRef
from app.services.analysis.technologies import detect_technologies


def dep(ecosystem, name, version=None, file="manifest", line=1):
    return Dependency(ecosystem, name, version, "runtime", file, line)


def detect(dependencies=(), imports=(), paths=()):
    return {t.name: t for t in detect_technologies(list(dependencies), list(imports), list(paths))}


def test_dependency_evidence_carries_file_line_and_version():
    found = detect([dep(PYPI, "fastapi", ">=0.100", "backend/pyproject.toml", 7)])

    [evidence] = found["FastAPI"].evidence
    assert (evidence.kind, evidence.path, evidence.line) == (
        "dependency",
        "backend/pyproject.toml",
        7,
    )
    assert evidence.detail == "fastapi >=0.100"
    assert found["FastAPI"].category == "Backend framework"


def test_python_names_match_regardless_of_case_and_separators():
    assert "SQLAlchemy" in detect([dep(PYPI, "sqlalchemy")])
    assert "Sentence Transformers" in detect([dep(PYPI, "Sentence_Transformers")])
    assert "PostgreSQL" in detect([dep(PYPI, "psycopg2-binary")])


def test_npm_scoped_and_wildcard_patterns():
    found = detect(
        [dep(NPM, "@testing-library/react"), dep(NPM, "@tanstack/react-query"), dep(NPM, "react")]
    )

    assert {"Testing Library", "TanStack Query", "React"} <= set(found)


def test_maven_group_wildcards_and_gradle_plugins():
    found = detect(
        [
            dep(MAVEN, "org.springframework.boot:spring-boot-starter-web"),
            dep(MAVEN, "org.springframework.boot", file="build.gradle"),
            dep(MAVEN, "org.hibernate.orm:hibernate-core"),
            dep(MAVEN, "org.junit.jupiter:junit-jupiter"),
        ]
    )

    assert {"Spring Boot", "Hibernate / JPA", "JUnit"} <= set(found)
    assert len(found["Spring Boot"].evidence) == 2


def test_imports_are_evidence_when_nothing_is_declared():
    found = detect(imports=[("app/db.py", "Python", ImportRef("sqlite3", 3))])

    [evidence] = found["SQLite"].evidence
    assert (evidence.kind, evidence.path, evidence.line, evidence.detail) == (
        "import", "app/db.py", 3, "import sqlite3",
    )  # fmt: skip


def test_import_matching_respects_module_boundaries():
    found = detect(
        imports=[
            ("a.py", "Python", ImportRef("fastapi.routing", 1)),
            ("b.py", "Python", ImportRef("fastapi_utils", 1)),
            ("c.js", "JavaScript", ImportRef("react-dom/client", 1)),
            ("d.js", "JavaScript", ImportRef("reactive-thing", 1)),
        ]
    )

    assert [e.path for e in found["FastAPI"].evidence] == ["a.py"]
    # "react-dom/client" and "reactive-thing" are different packages from "react".
    assert "React" not in found


def test_java_imports():
    found = detect(
        imports=[("A.java", "Java", ImportRef("org.springframework.boot.SpringApplication", 2))]
    )

    assert "Spring Boot" in found


def test_characteristic_files():
    found = detect(
        paths=[
            "Dockerfile", "docker-compose.yml", ".github/workflows/ci.yml", "web/vite.config.ts",
            "backend/alembic.ini", "pom.xml",
        ]
    )  # fmt: skip

    assert {"Docker", "Docker Compose", "GitHub Actions", "Vite", "Alembic", "Maven"} <= set(found)
    assert found["Vite"].evidence[0].kind == "file"
    assert found["Vite"].evidence[0].path == "web/vite.config.ts"


def test_nothing_is_reported_without_evidence():
    assert (
        detect(
            [dep(PYPI, "some-unknown-package")], [("a.py", "Python", ImportRef("os", 1))], ["a.py"]
        )
        == {}
    )


def test_evidence_is_capped_and_deduplicated():
    imports = [(f"f{i}.py", "Python", ImportRef("flask", 1)) for i in range(20)]
    found = detect([dep(PYPI, "flask")], imports)

    assert len(found["Flask"].evidence) == 4
    assert found["Flask"].evidence[0].kind == "dependency"  # declared dependencies come first


def test_results_are_grouped_by_category_then_evidence():
    found = detect_technologies(
        [dep(PYPI, "pytest"), dep(PYPI, "fastapi"), dep(PYPI, "sqlalchemy")], [], []
    )

    assert [t.category for t in found] == ["Backend framework", "ORM and migrations", "Testing"]


class TestDevOnly:
    """A framework that is only a development dependency and only used from tests."""

    def dev_dep(self, name="express", ecosystem=NPM):
        return Dependency(ecosystem, name, "^5", "dev", "package.json", 9)

    def test_a_dev_dependency_used_only_in_tests_is_flagged(self):
        found = detect(
            [self.dev_dep()], [("test/server.ts", "TypeScript", ImportRef("express", 3))]
        )

        assert found["Express"].dev_only is True

    def test_dependency_evidence_records_its_scope(self):
        found = detect([self.dev_dep()])

        assert found["Express"].evidence[0].scope == "dev"
        assert detect([dep(NPM, "express")])["Express"].evidence[0].scope == "runtime"

    def test_a_dev_dependency_imported_by_real_code_is_not_flagged(self):
        found = detect([self.dev_dep()], [("src/server.ts", "TypeScript", ImportRef("express", 1))])

        assert found["Express"].dev_only is False

    def test_a_runtime_dependency_is_not_flagged(self):
        found = detect(
            [dep(NPM, "express")], [("test/a.ts", "TypeScript", ImportRef("express", 1))]
        )

        assert found["Express"].dev_only is False

    def test_a_dev_declaration_next_to_a_runtime_one_is_not_flagged(self):
        found = detect([self.dev_dep(), dep(NPM, "express", file="web/package.json")])

        assert found["Express"].dev_only is False

    def test_test_and_build_tools_are_not_flagged_as_they_are_development_tools_anyway(self):
        found = detect([self.dev_dep("vitest"), self.dev_dep("vite"), self.dev_dep("typescript")])

        assert [found[name].dev_only for name in ("Vitest", "Vite", "TypeScript")] == [False] * 3

    def test_something_only_seen_in_imports_or_files_is_not_flagged(self):
        found = detect(
            imports=[("test/a.py", "Python", ImportRef("sqlite3", 1))], paths=["alembic.ini"]
        )

        assert found["SQLite"].dev_only is False and found["Alembic"].dev_only is False

    def test_maven_test_scope_counts_as_development(self):
        pom = Dependency(MAVEN, "org.postgresql:postgresql", None, "dev", "pom.xml", 5)

        assert detect([pom])["PostgreSQL"].dev_only is True
