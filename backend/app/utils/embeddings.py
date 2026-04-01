from __future__ import annotations

import numpy as np
from openai import OpenAI

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY from env
    return _client


def embed_text(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Return an embedding vector for the given text."""
    response = _get_client().embeddings.create(input=text, model=model)
    return response.data[0].embedding


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Return cosine similarity in [0, 1] between two embedding vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def similarity_to_score(similarity: float) -> float:
    """Convert cosine similarity [-1, 1] to a 0–100 score."""
    # Clamp to [0, 1] (embeddings for natural text are rarely negative)
    clamped = max(0.0, min(1.0, similarity))
    return round(clamped * 100, 2)
