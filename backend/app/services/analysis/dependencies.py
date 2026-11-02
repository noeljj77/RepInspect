"""Read declared dependencies from package manifests.

Manifests are only parsed as data (TOML, JSON, XML, text). Nothing is installed or run.
`setup.py` is deliberately not read: its dependencies are code, and extracting them
would mean executing it.
"""

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import PurePosixPath

PYPI = "pypi"
NPM = "npm"
MAVEN = "maven"  # Maven and Gradle share coordinates (group:artifact)

RUNTIME = "runtime"
DEV = "dev"
OPTIONAL = "optional"
PEER = "peer"
BUILD = "build"
PLUGIN = "plugin"
MANAGED = "managed"  # versions declared for others to use, not a direct dependency

MAX_PER_FILE = 1000
MAX_TOTAL = 3000
_DEV_WORDS = ("dev", "test", "lint", "doc", "ci", "typing", "mypy", "format")


@dataclass
class Dependency:
    ecosystem: str
    name: str
    version_spec: str | None
    scope: str
    source_file: str
    line: int | None = None


def is_manifest(path: str) -> bool:
    pure = PurePosixPath(path)
    name = pure.name.lower()
    if name in ("pyproject.toml", "package.json", "pom.xml", "build.gradle", "build.gradle.kts"):
        return True
    return name.endswith(".txt") and (
        name.startswith("requirements") or "requirements" in pure.parts[:-1]
    )


def extract_dependencies(manifests: dict[str, str]) -> list[Dependency]:
    """`manifests` maps repository paths to file contents."""
    found: list[Dependency] = []
    for path in sorted(manifests):
        text = manifests[path]
        name = PurePosixPath(path).name.lower()
        try:
            if name == "pyproject.toml":
                found += _pyproject(path, text)
            elif name == "package.json":
                found += _package_json(path, text)
            elif name == "pom.xml":
                found += _pom(path, text)
            elif name.startswith("build.gradle"):
                found += _gradle(path, text)
            else:
                found += _requirements(path, text)
        except (ValueError, TypeError, AttributeError, KeyError, RecursionError, ET.ParseError):
            continue  # a malformed manifest should never fail the whole analysis
        if len(found) >= MAX_TOTAL:
            return found[:MAX_TOTAL]
    return found


# --- Python ---------------------------------------------------------------------------

_REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(.*)$")


def normalize_python_name(name: str) -> str:
    """PEP 503 normalisation, so "Flask_SQLAlchemy" and "flask-sqlalchemy" compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _split_requirement(spec: str) -> tuple[str, str | None] | None:
    """ "fastapi[all]>=0.1,<1 ; python_version>'3.8'" -> ("fastapi", ">=0.1,<1")."""
    match = _REQUIREMENT.match(spec.strip())
    if not match:
        return None
    rest = match.group(2).split(";")[0].split(" #")[0].strip()
    if rest.startswith("@"):  # name @ https://...  (the URL may hold credentials)
        rest = "direct URL"
    return match.group(1), rest or None


def _requirements(path: str, text: str) -> list[Dependency]:
    file_name = PurePosixPath(path).name.lower()
    scope = (
        DEV if any(word in file_name or word in path.lower() for word in _DEV_WORDS) else RUNTIME
    )
    found: list[Dependency] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", "-", ".", "/")) or "://" in line.split("@")[0]:
            continue
        parsed = _split_requirement(line)
        if parsed:
            found.append(Dependency(PYPI, parsed[0], parsed[1], scope, path, number))
    return found[:MAX_PER_FILE]


def _find_line(lines: list[str], name: str, used: set[tuple[int, str]]) -> int | None:
    """Best-effort line of a dependency in a file whose parser does not report lines.

    `used` remembers which (line, name) pairs were handed out, so the same package
    declared twice (say under runtime and dev) gets two different lines, while two
    packages sharing a line both get it.
    """
    pattern = re.compile(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", re.IGNORECASE)
    for index, line in enumerate(lines):
        if (index, name) not in used and pattern.search(line):
            used.add((index, name))
            return index + 1
    return None


def _pyproject(path: str, text: str) -> list[Dependency]:
    data = tomllib.loads(text)
    lines = text.splitlines()
    used: set[tuple[int, str]] = set()
    found: list[Dependency] = []

    def add_requirements(specs: object, scope: str) -> None:
        for spec in specs if isinstance(specs, list) else []:
            parsed = _split_requirement(spec) if isinstance(spec, str) else None
            if parsed:
                line = _find_line(lines, parsed[0], used)
                found.append(Dependency(PYPI, parsed[0], parsed[1], scope, path, line))

    def group_scope(group: str) -> str:
        return DEV if any(word in group.lower() for word in _DEV_WORDS) else OPTIONAL

    project = data.get("project", {})
    add_requirements(project.get("dependencies"), RUNTIME)
    for group, specs in (project.get("optional-dependencies") or {}).items():
        add_requirements(specs, group_scope(group))
    for specs in (data.get("dependency-groups") or {}).values():  # PEP 735
        add_requirements(specs, DEV)
    add_requirements(data.get("build-system", {}).get("requires"), BUILD)
    add_requirements(data.get("tool", {}).get("uv", {}).get("dev-dependencies"), DEV)

    poetry = data.get("tool", {}).get("poetry", {})
    poetry_tables = [(poetry.get("dependencies"), RUNTIME), (poetry.get("dev-dependencies"), DEV)]
    for group, table in (poetry.get("group") or {}).items():
        poetry_tables.append(
            (table.get("dependencies"), DEV if group_scope(group) == DEV else OPTIONAL)
        )
    for table, scope in poetry_tables:
        for name, spec in (table or {}).items():
            if name.lower() == "python":
                continue
            version = spec if isinstance(spec, str) else _poetry_version(spec)
            found.append(
                Dependency(PYPI, name, version, scope, path, _find_line(lines, name, used))
            )
    return found[:MAX_PER_FILE]


def _poetry_version(spec: object) -> str | None:
    if isinstance(spec, dict):
        return spec.get("version") or (
            "git" if "git" in spec else "path" if "path" in spec else None
        )
    return None


# --- JavaScript ------------------------------------------------------------------------

_NPM_SECTIONS = {
    "dependencies": RUNTIME,
    "devDependencies": DEV,
    "peerDependencies": PEER,
    "optionalDependencies": OPTIONAL,
}


def _package_json(path: str, text: str) -> list[Dependency]:
    data = json.loads(text)
    lines = text.splitlines()
    used: set[tuple[int, str]] = set()
    found: list[Dependency] = []
    for section, scope in _NPM_SECTIONS.items():
        table = data.get(section) if isinstance(data, dict) else None
        for name, version in (table or {}).items():
            if isinstance(version, str):
                found.append(
                    Dependency(
                        NPM, name, version, scope, path, _find_line(lines, f'"{name}"', used)
                    )
                )
    return found[:MAX_PER_FILE]


# --- Maven -----------------------------------------------------------------------------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _local(child.tag) == name and child.text:
            return child.text.strip()
    return None


def _pom(path: str, text: str) -> list[Dependency]:
    # A DOCTYPE or entity declaration is the only way an XML file can pull in external
    # files or expand entities, and a pom.xml has no legitimate use for either.
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        return []
    root = ET.fromstring(text)
    parents = {child: parent for parent in root.iter() for child in parent}
    lines = text.splitlines()
    used: set[tuple[int, str]] = set()
    found: list[Dependency] = []

    def lineage(element: ET.Element) -> set[str]:
        names: set[str] = set()
        while element in parents:
            element = parents[element]
            names.add(_local(element.tag))
        return names

    for element in root.iter():
        kind = _local(element.tag)
        if kind not in ("dependency", "parent"):
            continue
        ancestors = lineage(element)
        if "plugin" in ancestors or "plugins" in ancestors or "pluginManagement" in ancestors:
            continue
        group, artifact = _child_text(element, "groupId"), _child_text(element, "artifactId")
        if not artifact:
            continue
        scope = _child_text(element, "scope") or RUNTIME
        if kind == "parent" or "dependencyManagement" in ancestors:
            scope = MANAGED
        elif scope == "test":
            scope = DEV
        elif scope not in (RUNTIME, DEV):
            scope = RUNTIME  # compile, provided, system, import
        name = f"{group}:{artifact}" if group else artifact
        found.append(
            Dependency(
                MAVEN,
                name,
                _child_text(element, "version"),
                scope,
                path,
                _find_line(lines, f"<artifactId>{artifact}</artifactId>", used),
            )
        )
    return found[:MAX_PER_FILE]


# --- Gradle ----------------------------------------------------------------------------

_GRADLE_DEPENDENCY = re.compile(
    r"""\b(?P<conf>implementation|api|compileOnly|runtimeOnly|testImplementation|testRuntimeOnly|"""
    r"""testCompileOnly|annotationProcessor|kapt|developmentOnly|compile|testCompile|runtime|classpath)"""
    r"""\s*\(?\s*["'](?P<group>[^"':\s]+):(?P<artifact>[^"':\s]+)(?::(?P<version>[^"'\s)]+))?["']"""
)
_GRADLE_PLUGIN = re.compile(
    r"""\bid\s*\(?\s*["']([\w.\-]+)["']\s*\)?(?:\s*version\s*["']([^"']+)["'])?"""
)


def _gradle(path: str, text: str) -> list[Dependency]:
    found: list[Dependency] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("//"):
            continue
        if match := _GRADLE_DEPENDENCY.search(line):
            conf = match["conf"]
            scope = (
                DEV
                if conf.startswith("test")
                else (
                    BUILD
                    if conf in ("annotationProcessor", "kapt", "compileOnly", "classpath")
                    else RUNTIME
                )
            )
            name = f"{match['group']}:{match['artifact']}"
            found.append(Dependency(MAVEN, name, match["version"], scope, path, number))
        elif match := _GRADLE_PLUGIN.search(line):
            found.append(Dependency(MAVEN, match[1], match[2], PLUGIN, path, number))
    return found[:MAX_PER_FILE]
