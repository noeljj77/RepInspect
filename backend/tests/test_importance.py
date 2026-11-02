import pytest

from app.services.analysis.importance import IMPORTANT_THRESHOLD, is_test_file, score_file
from app.services.analysis.models import FileAnalysis, Symbol


def symbol(name="f", decorators=()):
    return Symbol("function", name, name, 1, 2, f"def {name}()", decorators=list(decorators))


def score(path, analysis=None, imported_by=0):
    return score_file(path, analysis, imported_by)


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("README.md", "Project README"),
        ("pyproject.toml", "Dependency manifest"),
        ("backend/pyproject.toml", "Dependency manifest"),
        ("web/package.json", "Dependency manifest"),
        ("Dockerfile", "Configuration"),
        ("docker-compose.yml", "Configuration"),
        ("vite.config.ts", "Configuration"),
        ("backend/alembic.ini", "Configuration"),
        (".github/workflows/ci.yml", "CI workflow"),
        ("backend/app/main.py", "Likely entry point"),
        ("src/index.ts", "Likely entry point"),
        ("src/App.tsx", "Likely entry point"),
    ],
)
def test_well_known_files_score_high_with_a_reason(path, reason):
    points, reasons = score(path)

    assert reason in reasons
    assert points >= IMPORTANT_THRESHOLD


def test_ordinary_files_are_not_important():
    assert score("src/utils/format_dates.py") == (0, [])
    assert score("docs/guide.md") == (0, [])


def test_a_main_guard_marks_an_entry_point_anywhere():
    points, reasons = score("tools/seed.py", FileAnalysis(has_main=True))

    assert reasons == ["Application entry point"] and points == 45


def test_spring_boot_application_class():
    analysis = FileAnalysis(symbols=[symbol("Demo", ["@SpringBootApplication"])], has_main=True)

    assert score("src/main/java/Demo.java", analysis)[1] == ["Spring Boot application class"]


def test_files_imported_by_many_others_rank_higher():
    one = score("src/a.py", imported_by=1)
    many = score("src/a.py", imported_by=4)
    capped = score("src/a.py", imported_by=50)

    assert one == (6, ["Imported by 1 file"])
    assert many[0] == 24 and capped[0] == 30


def test_role_directories_and_large_definitions_add_to_the_score():
    analysis = FileAnalysis(symbols=[symbol(f"f{i}") for i in range(20)])

    points, reasons = score("backend/app/services/billing.py", analysis)

    assert reasons == ["Core module (services)", "Defines 20 functions and classes"]
    assert points == 10 + 5


def test_test_files_are_pushed_down():
    points, reasons = score("tests/test_main.py", FileAnalysis(has_main=True), imported_by=3)

    assert points < IMPORTANT_THRESHOLD
    assert reasons[-1] == "Test file"


@pytest.mark.parametrize(
    "path",
    ["tests/a.py", "src/__tests__/a.ts", "test_models.py", "models_test.py", "a.test.tsx",
     "b.spec.js", "UserServiceTest.java", "e2e/login.ts"],
)  # fmt: skip
def test_test_file_detection(path):
    assert is_test_file(path) is True


@pytest.mark.parametrize(
    "path", ["src/contest.py", "app/latest.py", "src/attestation.ts", "main.py"]
)
def test_non_test_files(path):
    assert is_test_file(path) is False
