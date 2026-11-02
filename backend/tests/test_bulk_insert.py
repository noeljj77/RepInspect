import uuid

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import AnalysisFile, CodeSymbol, RepositoryAnalysis, SavedRepository, User
from app.services.ingestion.pipeline import _insert_all


def test_large_batches_with_mixed_null_and_text_values_are_stored_intact():
    with SessionLocal() as db:
        user = User(email="a@example.com", display_name="A", password_hash="x")
        db.add(user)
        db.flush()
        repository = SavedRepository(
            user_id=user.id, source_type="github", source_key="github:o/r", name="r"
        )
        db.add(repository)
        db.flush()
        analysis = RepositoryAnalysis(saved_repository_id=repository.id, version=1)
        db.add(analysis)
        db.flush()
        file_ids = [uuid.uuid4() for _ in range(30)]
        _insert_all(
            db,
            AnalysisFile,
            [
                {"id": file_id, "analysis_id": analysis.id, "path": f"f{i}.py", "size_bytes": 1}
                for i, file_id in enumerate(file_ids)
            ],
        )

        # More than one chunk, with the nullable columns alternating NULL and values:
        # the pattern that made row-by-row inserts slow.
        rows = [
            {
                "id": uuid.uuid4(),
                "analysis_id": analysis.id,
                "file_id": file_ids[i % len(file_ids)],
                "kind": "function",
                "name": f"n{i}",
                "qualified_name": f"n{i}",
                "start_line": i,
                "end_line": i + 1,
                "signature": "def f()",
                "doc": f"Doc {i}" if i % 2 else None,
                "decorators": [f"@d{i}"] if i % 3 == 0 else None,
            }
            for i in range(4500)
        ]
        _insert_all(db, CodeSymbol, rows)
        db.flush()

        assert db.scalar(select(func.count()).select_from(CodeSymbol)) == 4500
        stored = db.scalar(select(CodeSymbol).where(CodeSymbol.name == "n3"))
        assert (stored.doc, stored.decorators) == ("Doc 3", ["@d3"])
        other = db.scalar(select(CodeSymbol).where(CodeSymbol.name == "n4"))
        assert (other.doc, other.decorators) == (None, None)
        db.rollback()


def test_inserting_nothing_is_fine():
    with SessionLocal() as db:
        _insert_all(db, CodeSymbol, [])
