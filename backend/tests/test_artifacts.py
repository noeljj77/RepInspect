import uuid

import pytest

from app.storage import artifacts


@pytest.fixture
def analysis_id():
    value = uuid.uuid4()
    source = artifacts.source_dir(value)
    source.mkdir(parents=True)
    (source / "app.py").write_text("print(1)")
    (source / "pkg").mkdir()
    (source / "pkg" / "mod.py").write_text("x = 1")
    # A neighbour that must stay unreachable from inside the snapshot.
    (source.parent / "secret.txt").write_text("not part of the repository")
    return value


def test_reads_stored_files(analysis_id):
    assert artifacts.read_source_file(analysis_id, "app.py") == b"print(1)"
    assert artifacts.read_source_file(analysis_id, "pkg/mod.py") == b"x = 1"


@pytest.mark.parametrize(
    "path",
    ["../secret.txt", "pkg/../../secret.txt", "../../../../etc/passwd", "missing.py", "pkg", ""],
)
def test_paths_outside_the_snapshot_or_not_files_return_none(analysis_id, path):
    assert artifacts.read_source_file(analysis_id, path) is None


def test_publishing_replaces_staging_with_the_final_directory(analysis_id):
    other = uuid.uuid4()
    (artifacts.staging_dir(other) / "a").mkdir(parents=True)
    (artifacts.staging_dir(other) / "a" / "f.txt").write_text("hi")

    artifacts.publish_staging(other)

    assert not artifacts.staging_dir(other).exists()
    assert artifacts.read_source_file(other, "a/f.txt") == b"hi"


def test_remove_analysis_is_safe_to_repeat(analysis_id):
    artifacts.remove_analysis(analysis_id)
    artifacts.remove_analysis(analysis_id)

    assert not artifacts.source_dir(analysis_id).exists()
