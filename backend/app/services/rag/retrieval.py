"""Find the chunks most likely to answer a question.

Three searches, each good at something different, are combined:

- by meaning (FAISS): finds `verify_password` for "where is the password checked",
  even though the words differ;
- by keywords (Postgres full-text search): reliable for rare, exact words such as an
  error message or a config key, where meaning-based search can be vague;
- by name: a file or function the question mentions literally (`pipeline.py`,
  `run_index_job`) is almost certainly what the person wants.

Their rankings are merged with reciprocal rank fusion: a chunk scores 1 / (60 + rank) in
each list it appears in, and the scores are added. Being near the top of any list helps,
and being found by several searches helps most. Ranks are combined, not raw scores,
because a cosine similarity and a text-search rank are not on the same scale.
"""

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import CodeChunk
from app.services.rag import embeddings, vector_store
from app.services.rag.chunking import split_identifier

CANDIDATES = 30  # taken from each search before merging
RRF_K = 60  # the usual constant: dampens the difference between rank 1 and rank 2
NAME_WEIGHT = 2.0  # an explicit mention counts double

_WORD = re.compile(r"[A-Za-z0-9]+")  # underscores split words, as in snake_case
_FILE_MENTION = re.compile(r"[\w./-]*\w\.[A-Za-z]{1,5}\b")
_IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\b")


@dataclass
class Retrieved:
    ordinal: int
    path: str
    start_line: int
    end_line: int
    symbol: str | None
    kind: str
    content: str
    score: float = 0.0
    # Which searches found it: "meaning", "keywords", "name". Shown to people.
    matched_by: list[str] = field(default_factory=list)


def keyword_query(question: str) -> str | None:
    """An OR query for to_tsquery: any of the words may match, more matches rank higher.

    plainto_tsquery would require every word, which almost never happens for a question
    written in plain language. Stop words ("the", "how") are dropped by Postgres itself.
    """
    terms: dict[str, None] = {}
    for word in _WORD.findall(question):
        for term in [word.lower(), *split_identifier(word)]:
            if len(term) > 1:
                terms.setdefault(term, None)
    return " | ".join(list(terms)[:24]) or None


def _looks_like_code_name(token: str) -> bool:
    return "_" in token or "." in token or (token != token.lower() and token != token.upper())


def _rrf(rankings: list[tuple[str, list[int], float]]) -> dict[int, tuple[float, list[str]]]:
    fused: dict[int, list] = defaultdict(lambda: [0.0, []])
    for label, ordinals, weight in rankings:
        for rank, ordinal in enumerate(ordinals, start=1):
            fused[ordinal][0] += weight / (RRF_K + rank)
            fused[ordinal][1].append(label)
    return {ordinal: (score, labels) for ordinal, (score, labels) in fused.items()}


class Retriever:
    def __init__(self, db: Session, analysis_id: uuid.UUID):
        self.db = db
        self.analysis_id = analysis_id

    def by_meaning(self, question: str) -> list[int]:
        stored = vector_store.load(self.analysis_id)
        embedder = embeddings.get_embedder()
        if stored.model != embedder.model_name:
            raise vector_store.IndexMissing("built with another embedding model")
        return [
            ordinal
            for ordinal, _ in vector_store.search(
                stored, embedder.embed_query(question), CANDIDATES
            )
        ]

    def by_keywords(self, question: str) -> list[int]:
        query_text = keyword_query(question)
        if query_text is None:
            return []
        query = func.to_tsquery("english", query_text)
        rank = func.ts_rank_cd(CodeChunk.search, query)
        return list(
            self.db.scalars(
                select(CodeChunk.ordinal)
                .where(CodeChunk.analysis_id == self.analysis_id, CodeChunk.search.op("@@")(query))
                .order_by(rank.desc(), CodeChunk.ordinal)
                .limit(CANDIDATES)
            )
        )

    def by_name(self, question: str) -> list[int]:
        files = {m.strip("./") for m in _FILE_MENTION.findall(question)}
        names = {
            token.rsplit(".", 1)[-1]
            for token in _IDENTIFIER.findall(question)
            if _looks_like_code_name(token) and token.strip(".") not in files
        }
        conditions = []
        for path in files:
            conditions += [CodeChunk.path == path, CodeChunk.path.endswith("/" + path)]
        for name in names:
            conditions += [CodeChunk.symbol == name, CodeChunk.symbol.endswith("." + name)]
        if not conditions:
            return []
        return list(
            self.db.scalars(
                select(CodeChunk.ordinal)
                .where(CodeChunk.analysis_id == self.analysis_id, or_(*conditions))
                .order_by(CodeChunk.path, CodeChunk.start_line)
                .limit(CANDIDATES)
            )
        )

    def retrieve(self, question: str, k: int, budget_chars: int) -> list[Retrieved]:
        fused = _rrf(
            [
                ("meaning", self.by_meaning(question), 1.0),
                ("keywords", self.by_keywords(question), 1.0),
                ("name", self.by_name(question), NAME_WEIGHT),
            ]
        )
        ranked = sorted(fused, key=lambda ordinal: (-fused[ordinal][0], ordinal))[: k * 3]
        rows = {
            row.ordinal: row
            for row in self.db.scalars(
                select(CodeChunk).where(
                    CodeChunk.analysis_id == self.analysis_id, CodeChunk.ordinal.in_(ranked)
                )
            )
        }

        chosen: list[Retrieved] = []
        used = 0
        for ordinal in ranked:
            row = rows.get(ordinal)
            if row is None or any(_mostly_same(row, other) for other in chosen):
                continue
            if used + len(row.content) > budget_chars:
                continue  # a smaller chunk further down may still fit
            score, labels = fused[ordinal]
            chosen.append(
                Retrieved(
                    ordinal=row.ordinal,
                    path=row.path,
                    start_line=row.start_line,
                    end_line=row.end_line,
                    symbol=row.symbol,
                    kind=row.kind,
                    content=row.content,
                    score=round(score, 5),
                    matched_by=labels,
                )
            )
            used += len(row.content)
            if len(chosen) >= k:
                break
        return chosen


def _mostly_same(row: CodeChunk, other: Retrieved) -> bool:
    """Overlapping windows of the same lines: showing both wastes the budget."""
    if row.path != other.path:
        return False
    overlap = min(row.end_line, other.end_line) - max(row.start_line, other.start_line) + 1
    shorter = min(row.end_line - row.start_line, other.end_line - other.start_line) + 1
    return overlap > 0 and overlap * 2 > shorter


def retrieve(
    db: Session, analysis_id: uuid.UUID, question: str, k: int, budget_chars: int
) -> list[Retrieved]:
    return Retriever(db, analysis_id).retrieve(question, k, budget_chars)
