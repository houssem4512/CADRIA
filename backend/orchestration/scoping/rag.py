"""
Simple SQLite-based RAG for the Scoping Agent.

Stores embeddings of past project briefs + their validated proposals.
At inference time, embeds the new brief and retrieves the top-3 most similar.

Uses sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` (118MB, CPU-friendly).
Embeddings are stored as JSON arrays in a TextField — no pgvector, no Qdrant.
Cosine similarity computed in-memory with numpy.

Storage model: `orchestration.PastProject` (added in migration).
"""
from __future__ import annotations
import json
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded model (so Django doesn't crash on import if sentence-transformers missing)
_MODEL = None
_DIMENSION = 384  # paraphrase-multilingual-MiniLM-L12-v2 dimension


def _get_model(timeout_skip=True):
    """
    Load the sentence-transformers model.

    If timeout_skip=True and the model isn't already loaded, return None
    instead of loading (which takes 30+ seconds on first download).
    The caller should handle None by skipping RAG.
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    if timeout_skip:
        logger.info("RAG model not pre-loaded — skipping RAG (run 'python manage.py setup_agents' to pre-load)")
        return None
    # Force load (used by setup_agents command)
    try:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    except ImportError:
        logger.warning("sentence-transformers not installed — RAG disabled")
        return None
    except Exception as e:
        logger.warning("Failed to load sentence-transformers model: %s — RAG disabled", e)
        return None
    return _MODEL


def embed_text(text: str) -> list[float] | None:
    """Embed a text string. Returns None if sentence-transformers is unavailable."""
    model = _get_model()
    if model is None or not text:
        return None
    try:
        vec = model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    except Exception as e:
        logger.warning("Embedding failed: %s", e)
        return None


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors (already normalized)."""
    return float(np.dot(a, b))


def retrieve_similar(brief: str, top_k: int = 3) -> list[dict[str, Any]]:
    """
    Retrieve the top-k most similar past projects from the DB.

    Returns a list of dicts:
      [
        { "brief": "...", "plan_summary": "...", "similarity": 0.87, "lots": [...], "tasks": [...] },
        ...
      ]

    Returns an empty list if no past projects exist or RAG is disabled.
    """
    query_vec = embed_text(brief)
    if query_vec is None:
        return []

    query_arr = np.array(query_vec)

    # Lazy import to avoid Django import cycle
    from orchestration.models import PastProject

    past_projects = PastProject.objects.filter(embedding__isnull=False).exclude(embedding="")[:200]
    if not past_projects.exists():
        return []

    scored: list[tuple[float, PastProject]] = []
    for pp in past_projects:
        try:
            vec = np.array(json.loads(pp.embedding))
            if vec.shape[0] != query_arr.shape[0]:
                continue
            score = _cosine_sim(query_arr, vec)
            scored.append((score, pp))
        except (json.JSONDecodeError, ValueError):
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "brief": pp.brief[:500],
            "lots": pp.lots_payload[:3] if pp.lots_payload else [],
            "tasks_count": pp.tasks_count,
            "total_estimate_hours": float(pp.total_estimate_hours),
            "similarity": round(score, 3),
        }
        for score, pp in scored[:top_k]
    ]


def format_rag_context(similar: list[dict[str, Any]]) -> str:
    """Format the retrieved projects into a string for the LLM prompt."""
    if not similar:
        return ""
    lines = ["Voici 3 projets passés similaires (par similarité cosinus sur le brief) :"]
    for i, p in enumerate(similar, 1):
        lines.append(
            f"\n### Projet similaire #{i} (similarité {p['similarity']})\n"
            f"Brief: {p['brief']}\n"
            f"Lots: {', '.join(l.get('name', '?') for l in p['lots'])}\n"
            f"Tâches: {p['tasks_count']}, effort total: {p['total_estimate_hours']}h"
        )
    return "\n".join(lines)


def store_past_project(brief: str, proposal) -> None:
    """
    Store a validated proposal as a PastProject for future RAG queries.

    Called after a Proposal is APPROVED (in ValidateProposalView).
    """
    if not brief:
        return
    vec = embed_text(brief)
    embedding_str = json.dumps(vec) if vec else ""

    from orchestration.models import PastProject
    PastProject.objects.update_or_create(
        brief=brief[:1000],
        defaults={
            "proposal": proposal,
            "embedding": embedding_str,
            "lots_payload": proposal.lots_payload or [],
            "tasks_count": proposal.tasks_count,
            "total_estimate_hours": proposal.total_estimate_hours,
        },
    )