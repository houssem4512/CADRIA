"""
NLP module for the Risk Agent — weak signal detection in comments.

For v1, uses keyword-based detection (deterministic, no GPU required).
For v2 (future), can be upgraded to CamemBERT fine-tuned for multi-label
classification.

Updates Comment.weak_signal and Comment.sentiment fields in the DB.
"""
from __future__ import annotations
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Multi-language keyword dictionaries (French + English)
SIGNAL_PATTERNS = {
    "blocked": [
        r"\bbloqué\b", r"\bbloque\b", r"\bblocked\b", r"\bblocker\b",
        r"\bimpossible\b", r"\bne peut pas\b", r"\bcan'?t\b",
    ],
    "waiting": [
        r"\ben attente\b", r"\bwaiting\b", r"\battendre?\b",
        r"\bpending\b", r"\battente de\b",
    ],
    "regression": [
        r"\brégression\b", r"\bregression\b", r"\bcassé\b",
        r"\bbroken\b", r"\bbug critique\b", r"\bnouvelle fois\b",
    ],
    "scope_creep": [
        r"\bhors périmètre\b", r"\bscope creep\b", r"\bnouveau besoin\b",
        r"\badditional\b", r"\bplus que prévu\b",
    ],
}

# Compile patterns once
_COMPILED: dict[str, list[re.Pattern]] = {
    signal: [re.compile(p, re.IGNORECASE) for p in patterns]
    for signal, patterns in SIGNAL_PATTERNS.items()
}

# Sentiment lexicon (simplified)
POSITIVE_WORDS = {"bien", "good", "ok", "fait", "done", "résolu", "fixed", "parfait", "validé"}
NEGATIVE_WORDS = {"problème", "problem", "bug", "erreur", "error", "retard", "late", "critique", "critical"}


def detect_signals(text: str) -> dict[str, Any]:
    """
    Detect weak signals in a comment text.

    Returns:
        {
            "has_signal": bool,
            "signals": ["blocked", "waiting", ...],
            "sentiment": "positive" | "negative" | "neutral",
            "matched_patterns": {"blocked": ["bloqué"], ...},
        }
    """
    if not text:
        return {"has_signal": False, "signals": [], "sentiment": "neutral", "matched_patterns": {}}

    text_lower = text.lower()
    matched: dict[str, list[str]] = {}
    signals: list[str] = []

    for signal, patterns in _COMPILED.items():
        for p in patterns:
            m = p.search(text_lower)
            if m:
                matched.setdefault(signal, []).append(m.group(0))
                if signal not in signals:
                    signals.append(signal)

    # Sentiment analysis (very simple)
    pos_count = sum(1 for w in POSITIVE_WORDS if w in text_lower)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in text_lower)
    if pos_count > neg_count:
        sentiment = "positive"
    elif neg_count > pos_count:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return {
        "has_signal": len(signals) > 0,
        "signals": signals,
        "sentiment": sentiment,
        "matched_patterns": matched,
    }


def analyze_comments(comments_qs) -> dict[str, Any]:
    """
    Analyze a queryset of comments. Updates each comment's weak_signal
    and sentiment fields. Returns aggregate stats.

    Args:
        comments_qs: QuerySet of projects.Comment

    Returns:
        {
            "total": int,
            "with_signals": int,
            "by_signal": {"blocked": N, "waiting": N, ...},
            "negative_count": int,
            "positive_count": int,
        }
    """
    total = 0
    with_signals = 0
    by_signal: dict[str, int] = {k: 0 for k in SIGNAL_PATTERNS}
    neg_count = 0
    pos_count = 0

    for comment in comments_qs[:200]:
        total += 1
        result = detect_signals(comment.body or "")
        # Update the Comment record
        if comment.weak_signal != result["has_signal"] or comment.sentiment != result["sentiment"]:
            comment.weak_signal = result["has_signal"]
            comment.sentiment = result["sentiment"]
            comment.save(update_fields=["weak_signal", "sentiment"])
        if result["has_signal"]:
            with_signals += 1
            for s in result["signals"]:
                by_signal[s] = by_signal.get(s, 0) + 1
        if result["sentiment"] == "negative":
            neg_count += 1
        elif result["sentiment"] == "positive":
            pos_count += 1

    return {
        "total": total,
        "with_signals": with_signals,
        "by_signal": by_signal,
        "negative_count": neg_count,
        "positive_count": pos_count,
    }
