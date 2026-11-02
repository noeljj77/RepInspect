"""Store and search the vectors of one analysis with FAISS.

FAISS finds the stored vectors closest to a query vector. `IndexFlatIP` compares the query
with every vector (exact search, inner product). With vectors of length 1 the inner
product is the cosine similarity. A repository has at most tens of thousands of chunks,
which exact search handles in milliseconds; approximate indexes (IVF, HNSW) only pay off
at millions.

Vector number N belongs to the chunk with ordinal N (see models/search.py), so no
separate id map is needed.
"""

import json
import os
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass

import faiss
import numpy as np

from app.storage import artifacts

INDEX_FILE = "vectors.faiss"
META_FILE = "meta.json"
CACHE_SIZE = 8  # indexes kept in memory, most recently used first


class IndexMissing(Exception):
    """No index file for this analysis (never built, or removed)."""


@dataclass(frozen=True)
class StoredIndex:
    index: faiss.Index
    model: str
    dimension: int


def new_index(dimension: int) -> faiss.Index:
    return faiss.IndexFlatIP(dimension)


def save(analysis_id: uuid.UUID, index: faiss.Index, model: str) -> None:
    folder = artifacts.index_dir(analysis_id)
    folder.mkdir(parents=True, exist_ok=True)
    # serialize_index gives bytes, which Python writes itself. This avoids FAISS's own
    # file functions, which cannot open paths with non-ASCII characters on Windows.
    data = faiss.serialize_index(index).tobytes()
    partial = folder / (INDEX_FILE + ".partial")
    partial.write_bytes(data)
    os.replace(partial, folder / INDEX_FILE)  # atomic: readers never see half a file
    meta = {"model": model, "dimension": index.d, "count": index.ntotal}
    (folder / META_FILE).write_text(json.dumps(meta), encoding="utf-8")
    forget(analysis_id)


_cache: OrderedDict[uuid.UUID, StoredIndex] = OrderedDict()
_cache_lock = threading.Lock()


def forget(analysis_id: uuid.UUID) -> None:
    with _cache_lock:
        _cache.pop(analysis_id, None)


def load(analysis_id: uuid.UUID) -> StoredIndex:
    with _cache_lock:
        if analysis_id in _cache:
            _cache.move_to_end(analysis_id)
            return _cache[analysis_id]

    folder = artifacts.index_dir(analysis_id)
    try:
        data = (folder / INDEX_FILE).read_bytes()
        meta = json.loads((folder / META_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise IndexMissing(str(analysis_id)) from error
    stored = StoredIndex(
        faiss.deserialize_index(np.frombuffer(data, dtype=np.uint8)),
        meta["model"],
        int(meta["dimension"]),
    )
    with _cache_lock:
        _cache[analysis_id] = stored
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return stored


def search(stored: StoredIndex, query: np.ndarray, k: int) -> list[tuple[int, float]]:
    """The k closest vectors as (ordinal, cosine similarity), closest first."""
    if stored.index.ntotal == 0:
        return []
    scores, ids = stored.index.search(query.reshape(1, -1).astype(np.float32), k)
    return [(int(i), float(s)) for i, s in zip(ids[0], scores[0], strict=True) if i != -1]
