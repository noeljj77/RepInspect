import pytest

from app.services.analysis.dependencies import (
    MAVEN,
    NPM,
    PYPI,
    extract_dependencies,
    is_manifest,
    normalize_python_name,
)


def found(manifests: dict[str, str]):
    return [(d.ecosystem, d.name, d.version_spec, d.scope, d.source_file, d.line)
            for d in extract_dependencies(manifests)]  # fmt: skip


@pytest.mark.parametrize(
    "path",
    [
        "pyproject.toml", "backend/pyproject.toml", "package.json", "web/package.json", "pom.xml",
        "build.gradle", "build.gradle.kts", "requirements.txt", "requirements-dev.txt",
        "requirements/base.txt", "docs/requirements.txt",
    ],
)  # fmt: skip
def test_manifest_detection(path):
    assert is_manifest(path) is True


@pytest.mark.parametrize(
    "path", ["notes.txt", "setup.py", "src/package.py", "package-lock.json", "README.md"]
)
def test_non_manifests(path):
    assert is_manifest(path) is False


class TestRequirementsTxt:
    TEXT = """# runtime
fastapi>=0.100,<1.0
uvicorn[standard]==0.30.0   # server
SQLAlchemy
python-dotenv ; python_version >= "3.8"
-r base.txt
-e git+https://github.com/x/y.git#egg=y
https://example.com/pkg.whl
./local/path
requests @ https://user:secret@example.com/requests.zip

"""

    def test_names_versions_and_lines(self):
        assert found({"requirements.txt": self.TEXT}) == [
            (PYPI, "fastapi", ">=0.100,<1.0", "runtime", "requirements.txt", 2),
            (PYPI, "uvicorn", "==0.30.0", "runtime", "requirements.txt", 3),
            (PYPI, "SQLAlchemy", None, "runtime", "requirements.txt", 4),
            (PYPI, "python-dotenv", None, "runtime", "requirements.txt", 5),
            (PYPI, "requests", "direct URL", "runtime", "requirements.txt", 10),
        ]

    def test_credentials_in_urls_are_never_kept(self):
        [*_, requests] = extract_dependencies({"requirements.txt": self.TEXT})

        assert "secret" not in str(requests)

    def test_dev_requirement_files_are_marked_dev(self):
        deps = extract_dependencies(
            {"requirements-dev.txt": "pytest\n", "dev/requirements.txt": "ruff\n"}
        )

        assert [d.scope for d in deps] == ["dev", "dev"]


class TestPyproject:
    TEXT = """[project]
name = "demo"
dependencies = [
  "fastapi>=0.100",
  "pydantic[email]>=2",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff"]
postgres = ["psycopg[binary]"]

[dependency-groups]
docs = ["mkdocs"]

[build-system]
requires = ["setuptools>=75"]

[tool.poetry.dependencies]
python = "^3.11"
httpx = { version = "^0.27", optional = true }
rich = "^13"
mylib = { path = "../mylib" }

[tool.poetry.group.test.dependencies]
coverage = "^7"
"""

    def test_all_sections_are_read(self):
        rows = {r[1]: r for r in found({"pyproject.toml": self.TEXT})}

        assert rows["fastapi"][2:4] == (">=0.100", "runtime")
        assert rows["pydantic"][2:4] == (">=2", "runtime")
        assert rows["pytest"][3] == "dev" and rows["ruff"][3] == "dev"
        assert rows["psycopg"][3] == "optional"
        assert rows["mkdocs"][3] == "dev"
        assert rows["setuptools"][3] == "build"
        assert rows["httpx"][2:4] == ("^0.27", "runtime")
        assert rows["rich"][2] == "^13"
        assert rows["mylib"][2] == "path"
        assert rows["coverage"][3] == "dev"
        assert "python" not in rows  # the interpreter is not a dependency

    def test_line_numbers_point_at_the_declaration(self):
        rows = {r[1]: r for r in found({"pyproject.toml": self.TEXT})}

        assert rows["fastapi"][5] == 4
        assert rows["pydantic"][5] == 5
        assert rows["pytest"][5] == 9

    def test_malformed_toml_is_ignored(self):
        assert found({"pyproject.toml": "[project\nnope"}) == []


class TestPackageJson:
    TEXT = """{
  "name": "web",
  "dependencies": { "react": "^19.0.0", "@tanstack/react-query": "^5" },
  "devDependencies": { "vite": "^8", "typescript": "~6.0" },
  "peerDependencies": { "react-dom": ">=19" },
  "optionalDependencies": { "fsevents": "*" }
}
"""

    def test_sections_and_scopes(self):
        assert found({"web/package.json": self.TEXT}) == [
            (NPM, "react", "^19.0.0", "runtime", "web/package.json", 3),
            (NPM, "@tanstack/react-query", "^5", "runtime", "web/package.json", 3),
            (NPM, "vite", "^8", "dev", "web/package.json", 4),
            (NPM, "typescript", "~6.0", "dev", "web/package.json", 4),
            (NPM, "react-dom", ">=19", "peer", "web/package.json", 5),
            (NPM, "fsevents", "*", "optional", "web/package.json", 6),
        ]

    @pytest.mark.parametrize(
        "text", ["not json", "[]", '{"dependencies": ["a"]}', '{"dependencies": {"a": 1}}']
    )
    def test_malformed_or_odd_files_are_ignored(self, text):
        assert found({"package.json": text}) == []


class TestMaven:
    POM = """<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.0</version>
  </parent>
  <dependencyManagement>
    <dependencies>
      <dependency><groupId>org.x</groupId><artifactId>bom</artifactId><version>1</version></dependency>
    </dependencies>
  </dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <version>5.10.0</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>jakarta.servlet</groupId>
      <artifactId>jakarta.servlet-api</artifactId>
      <scope>provided</scope>
    </dependency>
  </dependencies>
  <build><plugins><plugin>
    <artifactId>maven-compiler-plugin</artifactId>
    <dependencies><dependency><groupId>p</groupId><artifactId>plugin-only</artifactId></dependency></dependencies>
  </plugin></plugins></build>
</project>
"""

    def test_dependencies_parent_and_managed_versions(self):
        rows = {r[1]: r for r in found({"pom.xml": self.POM})}

        assert set(rows) == {
            "org.springframework.boot:spring-boot-starter-parent",
            "org.x:bom",
            "org.springframework.boot:spring-boot-starter-web",
            "org.junit.jupiter:junit-jupiter",
            "jakarta.servlet:jakarta.servlet-api",
        }
        assert rows["org.springframework.boot:spring-boot-starter-parent"][3] == "managed"
        assert rows["org.x:bom"][3] == "managed"
        assert rows["org.springframework.boot:spring-boot-starter-web"][3] == "runtime"
        assert rows["org.junit.jupiter:junit-jupiter"][2:4] == ("5.10.0", "dev")
        assert rows["jakarta.servlet:jakarta.servlet-api"][3] == "runtime"  # provided
        assert all(r[0] == MAVEN for r in rows.values())

    def test_line_numbers(self):
        rows = {r[1]: r for r in found({"pom.xml": self.POM})}

        assert rows["org.springframework.boot:spring-boot-starter-web"][5] == 16

    def test_documents_with_entity_declarations_are_not_parsed(self):
        evil = (
            '<?xml version="1.0"?><!DOCTYPE p [<!ENTITY x SYSTEM "file:///etc/passwd">]><project/>'
        )

        assert found({"pom.xml": evil}) == []

    def test_malformed_xml_is_ignored(self):
        assert found({"pom.xml": "<project><dependencies>"}) == []


class TestGradle:
    TEXT = """plugins {
    id 'java'
    id("org.springframework.boot") version "3.2.0"
}
dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation("com.google.guava:guava:33.0.0-jre")
    runtimeOnly "org.postgresql:postgresql:42.7.1"
    testImplementation 'org.junit.jupiter:junit-jupiter:5.10.0'
    annotationProcessor 'org.projectlombok:lombok:1.18.30'
    // implementation 'commented:out:1.0'
}
"""

    def test_dependencies_and_plugins(self):
        rows = {r[1]: r for r in found({"build.gradle": self.TEXT})}

        assert rows["org.springframework.boot:spring-boot-starter-web"][2:] == (
            None,
            "runtime",
            "build.gradle",
            6,
        )
        assert rows["com.google.guava:guava"][2:4] == ("33.0.0-jre", "runtime")
        assert rows["org.postgresql:postgresql"][2:4] == ("42.7.1", "runtime")
        assert rows["org.junit.jupiter:junit-jupiter"][3] == "dev"
        assert rows["org.projectlombok:lombok"][3] == "build"
        assert rows["org.springframework.boot"][2:4] == ("3.2.0", "plugin")
        assert rows["java"][3] == "plugin"
        assert "commented:out" not in " ".join(rows)

    def test_kotlin_dsl_files_are_read_too(self):
        text = 'dependencies {\n    implementation("io.ktor:ktor-server-core:2.3.0")\n}\n'

        assert found({"build.gradle.kts": text})[0][1:4] == (
            "io.ktor:ktor-server-core",
            "2.3.0",
            "runtime",
        )


def test_one_broken_manifest_does_not_hide_the_others():
    result = found({"package.json": "{broken", "requirements.txt": "flask\n"})

    assert result == [(PYPI, "flask", None, "runtime", "requirements.txt", 1)]


def test_python_name_normalisation():
    assert normalize_python_name("Flask_SQLAlchemy") == "flask-sqlalchemy"
    assert normalize_python_name("zope.interface") == "zope-interface"
