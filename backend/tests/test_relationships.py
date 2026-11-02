import pytest

from app.services.analysis.models import ImportRef
from app.services.analysis.relationships import PathIndex, resolve_import


def resolve(importing, language, module, paths, names=()):
    return resolve_import(importing, language, ImportRef(module, 1, list(names)), PathIndex(paths))


class TestPython:
    PATHS = [
        "backend/app/main.py",
        "backend/app/__init__.py",
        "backend/app/api/__init__.py",
        "backend/app/api/deps.py",
        "backend/app/api/routes/auth.py",
        "backend/app/core/config.py",
        "backend/tests/test_auth.py",
        "tools/app/other.py",
        "script.py",
    ]

    def test_absolute_import_with_the_source_root_unknown(self):
        assert resolve("backend/app/main.py", "Python", "app.core.config", self.PATHS) == [
            "backend/app/core/config.py"
        ]

    def test_importing_a_package_resolves_to_its_init(self):
        assert resolve("backend/app/main.py", "Python", "app.api", self.PATHS) == [
            "backend/app/api/__init__.py"
        ]

    def test_from_import_of_submodules_links_each_module(self):
        result = resolve(
            "backend/app/main.py", "Python", "app.api", self.PATHS, ["deps", "missing"]
        )

        assert result == ["backend/app/api/__init__.py", "backend/app/api/deps.py"]

    def test_ambiguous_names_pick_the_closest_file(self):
        paths = ["a/app/util.py", "b/app/util.py", "b/app/run.py"]

        assert resolve("b/app/run.py", "Python", "app.util", paths) == ["b/app/util.py"]

    def test_relative_imports(self):
        importing = "backend/app/api/routes/auth.py"

        assert resolve(importing, "Python", "..deps", self.PATHS) == ["backend/app/api/deps.py"]
        assert resolve(importing, "Python", "...core.config", self.PATHS) == [
            "backend/app/core/config.py"
        ]
        assert resolve(importing, "Python", "..", self.PATHS, ["deps"]) == [
            "backend/app/api/__init__.py",
            "backend/app/api/deps.py",
        ]

    def test_relative_import_of_siblings(self):
        assert resolve("backend/app/api/deps.py", "Python", ".", self.PATHS, ["routes"]) == [
            "backend/app/api/__init__.py"
        ]

    def test_relative_import_cannot_climb_above_the_root(self):
        assert resolve("script.py", "Python", "..x", self.PATHS) == []

    @pytest.mark.parametrize("module", ["os", "sys", "requests", "fastapi.routing", "app.missing"])
    def test_external_or_unknown_modules_are_unresolved(self, module):
        assert resolve("backend/app/main.py", "Python", module, self.PATHS) == []

    def test_a_file_never_links_to_itself(self):
        assert resolve("backend/app/main.py", "Python", "app.main", self.PATHS) == []


class TestEcmaScript:
    PATHS = [
        "src/App.tsx",
        "src/api/client.ts",
        "src/api/index.ts",
        "src/components/Button/index.tsx",
        "src/components/Button/Button.test.tsx",
        "src/util.js",
        "src/data.json",
        "src/esm.ts",
    ]

    @pytest.mark.parametrize(
        ("module", "expected"),
        [
            ("./api/client", "src/api/client.ts"),
            ("./api", "src/api/index.ts"),
            ("./components/Button", "src/components/Button/index.tsx"),
            ("./util", "src/util.js"),
            ("./util.js", "src/util.js"),
            ("./data.json", "src/data.json"),
            ("./esm.js", "src/esm.ts"),  # TypeScript ESM spells the output extension
            ("@/api/client", "src/api/client.ts"),
        ],
    )
    def test_resolves_relative_and_alias_paths(self, module, expected):
        assert resolve("src/App.tsx", "TypeScript", module, self.PATHS) == [expected]

    def test_parent_directory_paths(self):
        assert resolve("src/api/client.ts", "TypeScript", "../util", self.PATHS) == ["src/util.js"]
        assert resolve("src/api/client.ts", "TypeScript", "./", self.PATHS) == ["src/api/index.ts"]

    @pytest.mark.parametrize(
        "module", ["react", "@tanstack/react-query", "./missing", "../../../outside"]
    )
    def test_packages_and_missing_files_are_unresolved(self, module):
        assert resolve("src/App.tsx", "TypeScript", module, self.PATHS) == []


class TestJava:
    PATHS = [
        "src/main/java/com/example/demo/Demo.java",
        "src/main/java/com/example/util/Strings.java",
        "src/main/java/com/example/util/Outer.java",
        "other/com/example/util/Strings.java",
    ]

    def test_class_imports(self):
        assert resolve("A.java", "Java", "com.example.util.Strings", self.PATHS) == [
            "src/main/java/com/example/util/Strings.java"
        ]

    def test_nested_class_imports_resolve_to_the_outer_file(self):
        assert resolve("A.java", "Java", "com.example.util.Outer.Inner", self.PATHS) == [
            "src/main/java/com/example/util/Outer.java"
        ]

    def test_static_imports_use_the_class(self):
        assert resolve("A.java", "Java", "com.example.util.Strings", self.PATHS, ["join"]) == [
            "src/main/java/com/example/util/Strings.java"
        ]

    @pytest.mark.parametrize("module", ["java.util.List", "org.junit.Assert", "com.example.util"])
    def test_library_classes_and_wildcard_packages_are_unresolved(self, module):
        assert resolve("A.java", "Java", module, self.PATHS, ["*"]) == []


def test_other_languages_have_no_resolution():
    assert resolve("a.rb", "Ruby", "json", ["json.rb"]) == []
    assert resolve("a", None, "x", ["x.py"]) == []
