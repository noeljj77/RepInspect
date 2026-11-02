"""Build the search index of one analysis.

    stored files + symbols ─► chunks ─► code_chunks rows (keyword search in Postgres)
                                    └─► embeddings ─► FAISS file (search by meaning)

Runs right after an import finishes, in the same background job, and can be started
again from the API (for imports made before chat existed, or after a failure). The
analysis is already usable while this runs; only chat waits for it.
"""

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AnalysisFile, CodeChunk, CodeSymbol, IndexStatus, SearchIndex
from app.services.rag import embeddings, vector_store
from app.services.rag.chunking import (
    Chunk,
    Span,
    chunk_file,
    embedding_text,
    keywords,
    should_index,
)
from app.storage import artifacts

logger = logging.getLogger(__name__)

EMBED_BATCH = 256  # chunks embedded between progress updates
GENERIC_FAILURE = "The search index could not be built. Try again in a moment."


class NothingToIndex(Exception):
    pass


def request_index(db: Session, analysis_id: uuid.UUID) -> SearchIndex:
    """Create (or reset) the index record as pending. The caller starts the job."""
    record = db.get(SearchIndex, analysis_id)
    if record is None:
        record = SearchIndex(analysis_id=analysis_id)
        db.add(record)
    record.status = IndexStatus.PENDING
    record.chunk_count = 0
    record.chunks_embedded = 0
    record.truncated = False
    record.error_code = None
    record.error_message = None
    record.completed_at = None
    db.commit()
    return record


def run_index_job(analysis_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        record = db.get(SearchIndex, analysis_id)
        if record is None or record.status != IndexStatus.PENDING:
            return
        try:
            _build(db, record)
        except NothingToIndex:
            _fail(
                db,
                analysis_id,
                "nothing_to_index",
                "This repository has no files that can be searched.",
            )
        except Exception:
            logger.exception("Indexing %s failed", analysis_id)
            _fail(db, analysis_id, "index_error", GENERIC_FAILURE)


def collect_chunks(
    db: Session, analysis_id: uuid.UUID
) -> tuple[list[tuple[uuid.UUID, Chunk]], bool]:
    """Chunks for every searchable file, most important files first. Returns the chunks
    and whether the per-analysis limit cut the list short."""
    limit = get_settings().max_chunks_per_analysis
    files = db.execute(
        select(AnalysisFile.id, AnalysisFile.path, AnalysisFile.size_bytes)
        .where(AnalysisFile.analysis_id == analysis_id, AnalysisFile.skipped_reason.is_(None))
        .order_by(AnalysisFile.importance_score.desc(), AnalysisFile.path)
    ).all()
    spans: dict[uuid.UUID, list[Span]] = defaultdict(list)
    for file_id, name, kind, start, end in db.execute(
        select(
            CodeSymbol.file_id,
            CodeSymbol.qualified_name,
            CodeSymbol.kind,
            CodeSymbol.start_line,
            CodeSymbol.end_line,
        ).where(CodeSymbol.analysis_id == analysis_id)
    ):
        spans[file_id].append(Span(name, kind, start, end))

    chunks: list[tuple[uuid.UUID, Chunk]] = []
    for file_id, path, size in files:
        if not should_index(path, size):
            continue
        data = artifacts.read_source_file(analysis_id, path)
        if data is None or b"\x00" in data:
            continue
        for chunk in chunk_file(path, data.decode("utf-8", errors="replace"), spans[file_id]):
            if len(chunks) >= limit:
                return chunks, True
            chunks.append((file_id, chunk))
    return chunks, False


def _build(db: Session, record: SearchIndex) -> None:
    analysis_id = record.analysis_id
    record.status = IndexStatus.BUILDING
    db.commit()

    chunks, truncated = collect_chunks(db, analysis_id)
    if not chunks:
        raise NothingToIndex

    db.execute(delete(CodeChunk).where(CodeChunk.analysis_id == analysis_id))
    db.execute(
        insert(CodeChunk),
        [
            {
                "id": uuid.uuid4(),
                "analysis_id": analysis_id,
                "file_id": file_id,
                "ordinal": ordinal,
                "path": chunk.path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "symbol": chunk.symbol,
                "kind": chunk.kind,
                "content": chunk.text,
                "keywords": keywords(chunk),
            }
            for ordinal, (file_id, chunk) in enumerate(chunks)
        ],
    )
    record.chunk_count = len(chunks)
    record.truncated = truncated
    db.commit()

    embedder = embeddings.get_embedder()
    index = vector_store.new_index(embedder.dimension)
    texts = [embedding_text(chunk) for _, chunk in chunks]
    for start in range(0, len(texts), EMBED_BATCH):
        index.add(embedder.embed_documents(texts[start : start + EMBED_BATCH]))
        record.chunks_embedded = index.ntotal
        db.commit()  # lets the page show progress

    vector_store.save(analysis_id, index, embedder.model_name)
    record.model = embedder.model_name
    record.dimension = embedder.dimension
    record.status = IndexStatus.READY
    record.completed_at = datetime.now(UTC)
    db.commit()
    logger.info("Indexed %s: %d chunks with %s", analysis_id, len(chunks), embedder.model_name)


def _fail(db: Session, analysis_id: uuid.UUID, code: str, message: str) -> None:
    db.rollback()
    record = db.get(SearchIndex, analysis_id)
    if record is not None:
        record.status = IndexStatus.FAILED
        record.error_code = code
        record.error_message = message
        record.completed_at = datetime.now(UTC)
        db.commit()


def mark_interrupted(db: Session) -> int:
    """Fail indexes whose job died with a previous server process."""
    result = db.execute(
        update(SearchIndex)
        .where(SearchIndex.status.in_([IndexStatus.PENDING, IndexStatus.BUILDING]))
        .values(
            status=IndexStatus.FAILED.value,
            error_code="interrupted",
            error_message="The server restarted while the search index was being built. Try again.",
            completed_at=datetime.now(UTC),
        )
    )
    db.commit()
    return result.rowcount or 0
