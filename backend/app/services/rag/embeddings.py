"""Turn text into vectors whose distance reflects meaning.

An embedding model maps a piece of text to a list of numbers (here 384 of them). Texts
about similar things end up close together, even when they share no words: "where is the
password checked" lands near `verify_password(...)`. Vectors are normalised to length 1,
so the dot product of two vectors is their cosine similarity.

The model runs locally (Sentence Transformers on the CPU), so indexing a repository costs
nothing and its code is not sent to another service to be embedded.
"""

import logging
import os
import threading
from functools import lru_cache
from typing import Protocol

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    model_name: str
    dimension: int

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """float32 array of shape (len(texts), dimension), each row of length 1."""
        ...

    def embed_query(self, text: str) -> np.ndarray:
        """float32 array of shape (dimension,), of length 1."""
        ...


class SentenceTransformerEmbedder:
    def __init__(
        self, model_name: str, query_prefix: str, batch_size: int, max_tokens: int, cache_dir: str
    ):
        # The model cache works without symlinks (it copies instead); the warning is noise.
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        # Imported here: loading PyTorch takes seconds and is only needed for indexing and chat.
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model %s", model_name)
        self.model_name = model_name
        self._query_prefix = query_prefix
        self._batch_size = batch_size
        try:
            # Use the cached copy without asking Hugging Face for updates: faster, and works
            # offline. Only the very first start downloads the model (about 130 MB).
            self._model = SentenceTransformer(
                model_name, device="cpu", cache_folder=cache_dir, local_files_only=True
            )
        except OSError:
            self._model = SentenceTransformer(model_name, device="cpu", cache_folder=cache_dir)
        self._model.max_seq_length = max_tokens
        get_dimension = (
            getattr(self._model, "get_embedding_dimension", None)
            or self._model.get_sentence_embedding_dimension
        )
        self.dimension = int(get_dimension())
        # The model object is shared between worker threads; encoding one batch at a time
        # keeps memory use predictable.
        self._lock = threading.Lock()

    def _encode(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            vectors = self._model.encode(
                texts,
                batch_size=self._batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        return np.asarray(vectors, dtype=np.float32)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([self._query_prefix + text])[0]


@lru_cache
def _shared_embedder() -> SentenceTransformerEmbedder:
    settings = get_settings()
    settings.model_cache_dir.mkdir(parents=True, exist_ok=True)
    return SentenceTransformerEmbedder(
        settings.embedding_model,
        settings.embedding_query_prefix,
        settings.embedding_batch_size,
        settings.embedding_max_tokens,
        str(settings.model_cache_dir),
    )


def get_embedder() -> Embedder:
    """The process-wide model, loaded on first use. Tests replace this with a fake."""
    return _shared_embedder()
