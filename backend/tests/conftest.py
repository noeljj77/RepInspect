import os
import shutil
import tempfile
from pathlib import Path

# Configure the app for tests before any app module is imported, because the
# settings and the database engine are created at import time.
ARTIFACT_ROOT = Path(tempfile.mkdtemp(prefix="repinspect-test-artifacts-"))
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-only-used-by-the-test-suite-0123456789"
os.environ["ARTIFACT_DIR"] = str(ARTIFACT_ROOT)
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://repinspect:repinspect@localhost:5433/repinspect_test",
)

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.ingestion import pipeline  # noqa: E402
from app.services.ingestion.github_client import GitHubClient  # noqa: E402
from app.worker.runner import get_job_runner  # noqa: E402
from tests.fakes import FakeGitHub, InlineRunner  # noqa: E402

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Build the schema from the real migrations, so they are tested on every run."""
    config = Config(str(ALEMBIC_INI))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield
    engine.dispose()
    shutil.rmtree(ARTIFACT_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_state():
    """Start every test with empty tables and no stored files."""
    yield
    with engine.begin() as connection:
        # Cascades through repositories, analyses and files.
        connection.execute(text("TRUNCATE TABLE users CASCADE"))
    for child in ARTIFACT_ROOT.iterdir():
        shutil.rmtree(child, ignore_errors=True)


@pytest.fixture
def app():
    application = create_app()
    # Run background jobs immediately instead of in a thread pool.
    application.dependency_overrides[get_job_runner] = lambda: InlineRunner()
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def other_client(app):
    """A second browser: separate cookie jar, same app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def github(monkeypatch) -> FakeGitHub:
    """Replace the network with an in-memory GitHub for the analysis pipeline."""
    fake = FakeGitHub()
    monkeypatch.setattr(
        pipeline,
        "create_github_client",
        lambda: GitHubClient.from_settings(transport=fake.transport()),
    )
    return fake
