"""
Skill matching via sentence-transformers embeddings.

Embeds:
  - task description (the text to match against)
  - each team member's skill profile (concatenation of skill names + job title)

Cosine similarity gives the match score. Cached in-memory for the session.
Uses `paraphrase-multilingual-MiniLM-L12-v2` (French-friendly, 118MB, CPU).
"""
from __future__ import annotations
import logging
import functools
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _MODEL = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        except ImportError:
            logger.warning("sentence-transformers not installed — skill matching falls back to keyword overlap")
            return None
        except Exception as e:
            logger.warning("Failed to load sentence-transformers: %s", e)
            return None
    return _MODEL


def _embed(text: str) -> np.ndarray | None:
    model = _get_model()
    if model is None or not text:
        return None
    try:
        return model.encode(text, normalize_embeddings=True)
    except Exception as e:
        logger.warning("Embed failed: %s", e)
        return None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def _keyword_overlap(task_skills: list[str], member_skills: list[str]) -> float:
    """Fallback when embeddings are unavailable — Jaccard-like overlap."""
    if not task_skills:
        return 0.3  # neutral if no skills required
    task_set = {s.lower().strip() for s in task_skills if s}
    member_set = {s.lower().strip() for s in member_skills if s}
    if not member_set:
        return 0.0
    intersection = task_set & member_set
    union = task_set | member_set
    base = len(intersection) / len(union) if union else 0
    # Boost if all required skills covered
    if task_set and task_set.issubset(member_set):
        base = max(base, 0.85)
    return base


def score_match(task: dict, member: dict) -> tuple[float, list[str], str]:
    """
    Compute the skill match score between a task and a team member.

    Returns (score 0-1, matched_skills, rationale).
    """
    task_skills = task.get("skills", [])
    member_skills = [s.get("name", "") if isinstance(s, dict) else str(s) for s in member.get("skills", [])]

    # Try semantic matching
    task_text = task.get("title", "") + " " + task.get("description", "") + " " + " ".join(task_skills)
    member_text = member.get("name", "") + " " + member.get("job_title", "") + " " + " ".join(member_skills)

    task_vec = _embed(task_text)
    member_vec = _embed(member_text)

    if task_vec is not None and member_vec is not None:
        semantic_score = _cosine(task_vec, member_vec)
        # Blend with keyword overlap
        kw_score = _keyword_overlap(task_skills, member_skills)
        score = 0.7 * semantic_score + 0.3 * kw_score
    else:
        score = _keyword_overlap(task_skills, member_skills)

    matched = [s for s in task_skills if any(s.lower() in m.lower() for m in member_skills)]
    rationale = f"Score {score:.2f} — {len(matched)}/{len(task_skills)} skills matched"
    if not matched and task_skills:
        rationale += " (semantic similarity only)"
    return float(score), matched, rationale
