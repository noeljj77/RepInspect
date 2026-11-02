"""Detect the frameworks, libraries and tools a repository uses, with evidence.

A technology is only reported when something in the repository shows it: a declared
dependency, an import in the code, or a characteristic file. Each piece of evidence
carries the file and line, so every claim can be checked.
"""

import posixpath
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.services.analysis.dependencies import (
    BUILD as BUILD_SCOPE,
)
from app.services.analysis.dependencies import (
    DEV,
    MAVEN,
    NPM,
    PLUGIN,
    PYPI,
    Dependency,
    normalize_python_name,
)
from app.services.analysis.importance import is_test_file
from app.services.analysis.models import ImportRef

MAX_EVIDENCE = 4

# Categories, in the order the dashboard shows them.
BACKEND = "Backend framework"
FRONTEND = "Frontend framework"
DATABASE = "Database"
ORM = "ORM and migrations"
TESTING = "Testing"
STYLING = "Styling and UI"
STATE = "State and data fetching"
NETWORK = "HTTP and APIs"
AI = "AI and data"
AUTH = "Authentication and security"
TASKS = "Background jobs"
BUILD = "Build and tooling"
INFRA = "Infrastructure and CI"
CATEGORY_ORDER = [BACKEND, FRONTEND, DATABASE, ORM, AUTH, NETWORK, STATE, STYLING, AI, TASKS,
                  TESTING, BUILD, INFRA]  # fmt: skip


@dataclass
class Evidence:
    kind: str  # "dependency", "import" or "file"
    path: str
    line: int | None
    detail: str
    scope: str | None = None  # for dependencies: runtime, dev, optional...


@dataclass
class Technology:
    name: str
    category: str
    evidence: list[Evidence] = field(default_factory=list)
    # Only a development dependency, used only from tests (for example an Express server
    # a library starts to test its HTTP client). Not set for test and build tools, which
    # are development-only by nature.
    dev_only: bool = False


_DEV_SCOPES = frozenset({DEV, BUILD_SCOPE, PLUGIN})
# Categories of things that normally ship with the product, so "development only" is news.
_SHIPPED_CATEGORIES = frozenset(
    {BACKEND, FRONTEND, DATABASE, ORM, AUTH, NETWORK, STATE, STYLING, AI, TASKS}
)


@dataclass(frozen=True)
class Rule:
    name: str
    category: str
    pypi: tuple[str, ...] = ()
    npm: tuple[str, ...] = ()
    maven: tuple[str, ...] = ()
    py_imports: tuple[str, ...] = ()
    js_imports: tuple[str, ...] = ()
    java_imports: tuple[str, ...] = ()
    files: tuple[str, ...] = ()  # base file names, lowercase; a trailing "/" means a folder


def _r(name: str, category: str, **kwargs: tuple[str, ...]) -> Rule:
    return Rule(name, category, **kwargs)


# Patterns ending in "*" match any name starting with the text before it.
RULES: tuple[Rule, ...] = (
    # --- backend frameworks ---
    _r("FastAPI", BACKEND, pypi=("fastapi",), py_imports=("fastapi",)),
    _r("Flask", BACKEND, pypi=("flask",), py_imports=("flask",)),
    _r("Django", BACKEND, pypi=("django",), py_imports=("django",), files=("manage.py",)),
    _r("Starlette", BACKEND, pypi=("starlette",), py_imports=("starlette",)),
    _r("aiohttp", BACKEND, pypi=("aiohttp",), py_imports=("aiohttp",)),
    _r("Tornado", BACKEND, pypi=("tornado",), py_imports=("tornado",)),
    _r("Express", BACKEND, npm=("express",), js_imports=("express",)),
    _r("Koa", BACKEND, npm=("koa",), js_imports=("koa",)),
    _r("Fastify", BACKEND, npm=("fastify",), js_imports=("fastify",)),
    _r("NestJS", BACKEND, npm=("@nestjs/core",), js_imports=("@nestjs/core",)),
    _r(
        "Spring Boot",
        BACKEND,
        maven=("org.springframework.boot:*", "org.springframework.boot"),
        java_imports=("org.springframework.boot",),
    ),  # fmt: skip
    _r(
        "Spring Framework",
        BACKEND,
        maven=("org.springframework:*",),
        java_imports=("org.springframework.",),
    ),
    _r("Streamlit", BACKEND, pypi=("streamlit",), py_imports=("streamlit",)),
    # --- frontend frameworks ---
    _r("React", FRONTEND, npm=("react",), js_imports=("react",)),
    _r(
        "Next.js",
        FRONTEND,
        npm=("next",),
        js_imports=("next",),
        files=("next.config.js", "next.config.mjs", "next.config.ts"),
    ),
    _r("Vue", FRONTEND, npm=("vue",), js_imports=("vue",)),
    _r("Nuxt", FRONTEND, npm=("nuxt",), files=("nuxt.config.ts", "nuxt.config.js")),
    _r(
        "Angular",
        FRONTEND,
        npm=("@angular/core",),
        js_imports=("@angular/core",),
        files=("angular.json",),
    ),
    _r("Svelte", FRONTEND, npm=("svelte",), js_imports=("svelte",)),
    _r(
        "React Router",
        FRONTEND,
        npm=("react-router", "react-router-dom"),
        js_imports=("react-router", "react-router-dom"),
    ),
    # --- databases and drivers ---
    _r(
        "PostgreSQL",
        DATABASE,
        pypi=("psycopg", "psycopg2", "psycopg2-binary", "asyncpg", "pg8000"),
        npm=("pg", "postgres"),
        maven=("org.postgresql:postgresql",),
        py_imports=("psycopg", "psycopg2", "asyncpg"),
        js_imports=("pg",),
    ),  # fmt: skip
    _r(
        "MySQL",
        DATABASE,
        pypi=("pymysql", "mysqlclient", "mysql-connector-python", "aiomysql"),
        npm=("mysql", "mysql2"),
        maven=("mysql:mysql-connector-java", "com.mysql:*"),
    ),  # fmt: skip
    _r(
        "SQLite",
        DATABASE,
        npm=("sqlite3", "better-sqlite3"),
        py_imports=("sqlite3",),
        maven=("org.xerial:sqlite-jdbc",),
    ),
    _r(
        "MongoDB",
        DATABASE,
        pypi=("pymongo", "motor"),
        npm=("mongodb", "mongoose"),
        py_imports=("pymongo",),
        maven=("org.mongodb:*", "org.springframework.boot:spring-boot-starter-data-mongodb"),
    ),  # fmt: skip
    _r(
        "Redis",
        DATABASE,
        pypi=("redis", "aioredis"),
        npm=("redis", "ioredis"),
        py_imports=("redis",),
        maven=("redis.clients:jedis", "org.springframework.boot:spring-boot-starter-data-redis"),
    ),  # fmt: skip
    _r("H2", DATABASE, maven=("com.h2database:h2",)),
    # --- ORM and migrations ---
    _r("SQLAlchemy", ORM, pypi=("sqlalchemy",), py_imports=("sqlalchemy",)),
    _r("Alembic", ORM, pypi=("alembic",), py_imports=("alembic",), files=("alembic.ini",)),
    _r("SQLModel", ORM, pypi=("sqlmodel",), py_imports=("sqlmodel",)),
    _r("Peewee", ORM, pypi=("peewee",), py_imports=("peewee",)),
    _r("Prisma", ORM, npm=("prisma", "@prisma/client"), files=("schema.prisma",)),
    _r("TypeORM", ORM, npm=("typeorm",), js_imports=("typeorm",)),
    _r("Sequelize", ORM, npm=("sequelize",), js_imports=("sequelize",)),
    _r("Mongoose", ORM, npm=("mongoose",), js_imports=("mongoose",)),
    _r(
        "Hibernate / JPA",
        ORM,
        maven=(
            "org.hibernate*",
            "org.springframework.boot:spring-boot-starter-data-jpa",
            "jakarta.persistence:*",
            "javax.persistence:*",
        ),
        java_imports=("javax.persistence", "jakarta.persistence"),
    ),  # fmt: skip
    _r("Flyway", ORM, maven=("org.flywaydb:*",), files=("flyway.conf",)),
    _r("Liquibase", ORM, maven=("org.liquibase:*",)),
    # --- authentication and security ---
    _r(
        "JWT",
        AUTH,
        pypi=("pyjwt", "python-jose", "authlib"),
        npm=("jsonwebtoken", "jose"),
        maven=("io.jsonwebtoken:*",),
        py_imports=("jwt", "jose"),
    ),  # fmt: skip
    _r("Argon2", AUTH, pypi=("argon2-cffi",), py_imports=("argon2",), npm=("argon2",)),
    _r(
        "bcrypt",
        AUTH,
        pypi=("bcrypt", "passlib"),
        npm=("bcrypt", "bcryptjs"),
        py_imports=("bcrypt", "passlib"),
    ),
    _r("Passport", AUTH, npm=("passport",), js_imports=("passport",)),
    _r(
        "Spring Security",
        AUTH,
        maven=(
            "org.springframework.boot:spring-boot-starter-security",
            "org.springframework.security:*",
        ),
        java_imports=("org.springframework.security",),
    ),  # fmt: skip
    # --- HTTP, APIs ---
    _r("HTTPX", NETWORK, pypi=("httpx",), py_imports=("httpx",)),
    _r("Requests", NETWORK, pypi=("requests",), py_imports=("requests",)),
    _r("Axios", NETWORK, npm=("axios",), js_imports=("axios",)),
    _r(
        "GraphQL",
        NETWORK,
        pypi=("graphene", "strawberry-graphql", "ariadne"),
        npm=("graphql", "@apollo/client", "apollo-server"),
        js_imports=("graphql",),
    ),  # fmt: skip
    _r("Pydantic", NETWORK, pypi=("pydantic", "pydantic-settings"), py_imports=("pydantic",)),
    _r("Socket.IO", NETWORK, pypi=("python-socketio",), npm=("socket.io", "socket.io-client")),
    _r("Uvicorn", NETWORK, pypi=("uvicorn",), py_imports=("uvicorn",)),
    _r("Gunicorn", NETWORK, pypi=("gunicorn",)),
    # --- state and data fetching ---
    _r(
        "TanStack Query",
        STATE,
        npm=("@tanstack/react-query", "react-query"),
        js_imports=("@tanstack/react-query",),
    ),
    _r(
        "Redux",
        STATE,
        npm=("redux", "@reduxjs/toolkit", "react-redux"),
        js_imports=("redux", "@reduxjs/toolkit", "react-redux"),
    ),
    _r("Zustand", STATE, npm=("zustand",), js_imports=("zustand",)),
    _r("MobX", STATE, npm=("mobx",), js_imports=("mobx",)),
    _r("SWR", STATE, npm=("swr",), js_imports=("swr",)),
    # --- styling and UI ---
    _r(
        "Tailwind CSS",
        STYLING,
        npm=("tailwindcss",),
        files=("tailwind.config.js", "tailwind.config.ts"),
    ),
    _r("Bootstrap", STYLING, npm=("bootstrap",), js_imports=("bootstrap",)),
    _r("Material UI", STYLING, npm=("@mui/material",), js_imports=("@mui/material",)),
    _r("styled-components", STYLING, npm=("styled-components",), js_imports=("styled-components",)),
    _r("Sass", STYLING, npm=("sass", "node-sass")),
    _r("Recharts", STYLING, npm=("recharts",), js_imports=("recharts",)),
    _r("D3", STYLING, npm=("d3",), js_imports=("d3",)),
    _r("Lucide icons", STYLING, npm=("lucide-react", "lucide"), js_imports=("lucide-react",)),
    # --- AI and data ---
    _r("NumPy", AI, pypi=("numpy",), py_imports=("numpy",)),
    _r("pandas", AI, pypi=("pandas",), py_imports=("pandas",)),
    _r("scikit-learn", AI, pypi=("scikit-learn", "sklearn"), py_imports=("sklearn",)),
    _r("PyTorch", AI, pypi=("torch",), py_imports=("torch",)),
    _r("TensorFlow", AI, pypi=("tensorflow",), py_imports=("tensorflow",)),
    _r("Keras", AI, pypi=("keras",), py_imports=("keras",)),
    _r("Hugging Face Transformers", AI, pypi=("transformers",), py_imports=("transformers",)),
    _r(
        "Sentence Transformers",
        AI,
        pypi=("sentence-transformers",),
        py_imports=("sentence_transformers",),
    ),
    _r("FAISS", AI, pypi=("faiss-cpu", "faiss-gpu"), py_imports=("faiss",)),
    _r(
        "LangChain",
        AI,
        pypi=("langchain", "langchain-core"),
        npm=("langchain",),
        py_imports=("langchain",),
    ),
    _r(
        "OpenAI API",
        AI,
        pypi=("openai",),
        npm=("openai",),
        py_imports=("openai",),
        js_imports=("openai",),
    ),
    _r(
        "Anthropic API",
        AI,
        pypi=("anthropic",),
        npm=("@anthropic-ai/sdk",),
        py_imports=("anthropic",),
    ),
    # --- background jobs ---
    _r("Celery", TASKS, pypi=("celery",), py_imports=("celery",)),
    _r("RQ", TASKS, pypi=("rq",), py_imports=("rq",)),
    _r("Bull", TASKS, npm=("bull", "bullmq"), js_imports=("bull", "bullmq")),
    _r(
        "Apache Kafka",
        TASKS,
        pypi=("kafka-python", "confluent-kafka"),
        npm=("kafkajs",),
        maven=("org.apache.kafka:*",),
    ),
    # --- testing ---
    _r(
        "pytest",
        TESTING,
        pypi=("pytest",),
        py_imports=("pytest",),
        files=("pytest.ini", "conftest.py"),
    ),
    _r("unittest", TESTING, py_imports=("unittest",)),
    _r("Jest", TESTING, npm=("jest",), files=("jest.config.js", "jest.config.ts")),
    _r("Vitest", TESTING, npm=("vitest",), js_imports=("vitest",)),
    _r("Mocha", TESTING, npm=("mocha",)),
    _r("Cypress", TESTING, npm=("cypress",), files=("cypress.config.js", "cypress.config.ts")),
    _r(
        "Playwright",
        TESTING,
        npm=("@playwright/test", "playwright"),
        pypi=("playwright", "pytest-playwright"),
        files=("playwright.config.ts", "playwright.config.js"),
    ),  # fmt: skip
    _r("Testing Library", TESTING, npm=("@testing-library/*",)),
    _r("JUnit", TESTING, maven=("org.junit*", "junit:junit"), java_imports=("org.junit",)),
    _r("Mockito", TESTING, maven=("org.mockito:*",), java_imports=("org.mockito",)),
    # --- build and tooling ---
    _r("Vite", BUILD, npm=("vite",), files=("vite.config.ts", "vite.config.js")),
    _r("webpack", BUILD, npm=("webpack",), files=("webpack.config.js",)),
    _r("TypeScript", BUILD, npm=("typescript",), files=("tsconfig.json",)),
    _r(
        "ESLint",
        BUILD,
        npm=("eslint",),
        files=("eslint.config.js", ".eslintrc", ".eslintrc.json", ".eslintrc.js"),
    ),
    _r("Prettier", BUILD, npm=("prettier",), files=(".prettierrc",)),
    _r("Ruff", BUILD, pypi=("ruff",), files=("ruff.toml",)),
    _r("Black", BUILD, pypi=("black",)),
    _r("mypy", BUILD, pypi=("mypy",), files=("mypy.ini",)),
    _r("Poetry", BUILD, files=("poetry.lock",)),
    _r("Maven", BUILD, files=("pom.xml",)),
    _r("Gradle", BUILD, files=("build.gradle", "build.gradle.kts", "gradlew")),
    _r("Lombok", BUILD, maven=("org.projectlombok:lombok",), java_imports=("lombok",)),
    _r("Make", BUILD, files=("makefile",)),
    # --- infrastructure ---
    _r("Docker", INFRA, files=("dockerfile", ".dockerignore")),
    _r(
        "Docker Compose",
        INFRA,
        files=("docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"),
    ),
    _r("GitHub Actions", INFRA, files=(".github/workflows/",)),
    _r("GitLab CI", INFRA, files=(".gitlab-ci.yml",)),
    _r("Kubernetes", INFRA, files=("kustomization.yaml", "chart.yaml")),
    _r("Terraform", INFRA, files=("main.tf",)),
)


# Which Rule field lists imports for a language, and how its module names are separated.
_IMPORT_FIELDS = {
    "Python": ("py_imports", "."),
    "JavaScript": ("js_imports", "/"),
    "TypeScript": ("js_imports", "/"),
    "Java": ("java_imports", "."),
}


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    return any(name.startswith(p[:-1]) if p.endswith("*") else name == p for p in patterns)


def _import_matches(module: str, prefixes: tuple[str, ...], separator: str) -> bool:
    return any(
        module == p or module.startswith(p if p.endswith(".") else p + separator) for p in prefixes
    )


def _dependency_rule(rule: Rule, dep: Dependency) -> bool:
    if dep.ecosystem == PYPI:
        return normalize_python_name(dep.name) in {normalize_python_name(n) for n in rule.pypi}
    if dep.ecosystem == NPM:
        return _matches(dep.name.lower(), rule.npm)
    if dep.ecosystem == MAVEN:
        return _matches(dep.name.lower(), rule.maven)
    return False


def detect_technologies(
    dependencies: list[Dependency],
    imports: list[tuple[str, str | None, ImportRef]],
    paths: list[str],
) -> list[Technology]:
    """`imports` holds (file path, language, import) for imports of *external* modules only."""
    found: dict[str, Technology] = {}
    used_beyond_development: set[str] = set()  # runtime dependency, or imported outside tests

    def add(rule: Rule, evidence: Evidence) -> None:
        tech = found.setdefault(rule.name, Technology(rule.name, rule.category))
        if len(tech.evidence) < MAX_EVIDENCE and evidence not in tech.evidence:
            tech.evidence.append(evidence)

    for rule in RULES:
        for dep in dependencies:
            if _dependency_rule(rule, dep):
                version = f" {dep.version_spec}" if dep.version_spec else ""
                add(
                    rule,
                    Evidence(
                        "dependency", dep.source_file, dep.line, f"{dep.name}{version}", dep.scope
                    ),
                )
                if dep.scope not in _DEV_SCOPES:
                    used_beyond_development.add(rule.name)

    for path, language, ref in imports:
        if language not in _IMPORT_FIELDS:
            continue
        field_name, separator = _IMPORT_FIELDS[language]
        for rule in RULES:
            if _import_matches(ref.module, getattr(rule, field_name), separator):
                add(rule, Evidence("import", path, ref.line, f"import {ref.module}"))
                if not is_test_file(path):
                    used_beyond_development.add(rule.name)

    lowered = [p.lower() for p in paths]
    for rule in RULES:
        for pattern in rule.files:
            for original, path in zip(paths, lowered, strict=True):
                matched = (
                    pattern in path
                    if pattern.endswith("/")
                    else posixpath.basename(path) == pattern
                )
                if matched:
                    add(rule, Evidence("file", original, None, PurePosixPath(original).name))
                    break

    for tech in found.values():
        has_dependency = any(e.kind == "dependency" for e in tech.evidence)
        tech.dev_only = (
            has_dependency
            and tech.category in _SHIPPED_CATEGORIES
            and tech.name not in used_beyond_development
        )

    order = {category: index for index, category in enumerate(CATEGORY_ORDER)}
    return sorted(found.values(), key=lambda t: (order[t.category], -len(t.evidence), t.name))
