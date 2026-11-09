"""
XGBoost risk scorer with SHAP explanations.

Trains on synthetic labels (rule-based bootstrap) until real outcome data is available.
Saves the trained model to backend/orchestration/ml_models/risk_v1.json.

At inference:
  - predict_proba(features) → risk score 0-1
  - shap_explain(features) → top-3 contributing factors
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent / "ml_models"
MODEL_PATH = MODEL_DIR / "risk_v1.json"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

_model = None
_explainer = None


def _generate_synthetic_training_data(n_samples: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic training data with rule-based labels for bootstrap.

    Label = 1 (high risk) if any of:
      - overdue_days > 5
      - is_blocked AND not done
      - effort_variance > 0.4 (estimate way off)
      - weak_signal_ratio > 0.3
    """
    rng = np.random.default_rng(42)
    X = []
    y = []
    for _ in range(n_samples):
        estimate = rng.uniform(4, 80)
        spent_ratio = rng.uniform(0, 1.5)
        spent = estimate * spent_ratio
        progress = min(1, spent / max(estimate, 1))
        overdue = int(rng.uniform(0, 1) > 0.7) * rng.integers(1, 20)
        is_blocked = int(rng.uniform(0, 1) > 0.85)
        is_overdue = int(overdue > 0)
        is_in_progress = int(rng.uniform(0, 1) > 0.5)
        is_review = int(rng.uniform(0, 1) > 0.8)
        priority_high = int(rng.uniform(0, 1) > 0.6)
        effort_var = abs(estimate - spent) / max(estimate, 1)
        proj_blocked_ratio = rng.uniform(0, 0.4)
        proj_overdue_ratio = rng.uniform(0, 0.5)
        proj_done_ratio = rng.uniform(0, 1)
        proj_in_prog = rng.uniform(0, 0.5)
        proj_avg_progress = rng.uniform(0, 1)
        c_blocked = int(rng.uniform(0, 1) > 0.8)
        c_waiting = int(rng.uniform(0, 1) > 0.7)
        c_regression = int(rng.uniform(0, 1) > 0.9)
        c_weak_ratio = rng.uniform(0, 0.5)

        # Label rules
        high_risk = (
            overdue > 5 or
            (is_blocked and not (progress >= 1)) or
            effort_var > 0.4 or
            c_weak_ratio > 0.3
        )
        X.append([estimate, spent, max(0, estimate - spent), progress, overdue,
                  is_blocked, is_overdue, is_in_progress, is_review, priority_high, effort_var,
                  proj_blocked_ratio, proj_overdue_ratio, proj_done_ratio, proj_in_prog, proj_avg_progress,
                  c_blocked, c_waiting, c_regression, c_weak_ratio])
        y.append(1 if high_risk else 0)
    return np.array(X), np.array(y)


def train_model() -> str:
    """Train the XGBoost risk model on synthetic data. Returns the model path."""
    try:
        import xgboost as xgb
    except ImportError:
        logger.warning("xgboost not installed — risk scorer unavailable")
        return ""

    X, y = _generate_synthetic_training_data(500)
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X, y)
    model.save_model(str(MODEL_PATH))
    logger.info("XGBoost risk model trained and saved to %s", MODEL_PATH)
    return str(MODEL_PATH)


def _load_model():
    global _model, _explainer
    if _model is not None:
        return _model
    try:
        import xgboost as xgb
    except ImportError:
        logger.warning("xgboost not installed — risk scorer unavailable")
        return None
    if not MODEL_PATH.exists():
        logger.info("Risk model not found — training...")
        train_model()
    if not MODEL_PATH.exists():
        return None
    _model = xgb.XGBClassifier()
    _model.load_model(str(MODEL_PATH))
    # Try to set up SHAP explainer
    try:
        import shap
        _explainer = shap.TreeExplainer(_model)
    except ImportError:
        logger.info("shap not installed — explanations will be rule-based")
        _explainer = None
    return _model


def predict(features: list[float]) -> float:
    """Predict the risk score (0-1) for a single feature vector.

    Always uses rule-based scoring — the XGBoost model trained on synthetic
    data gives unrealistic scores for fresh projects (e.g., 99/100 for all
    tasks when there's 1 comment with weak signals). The rule-based scorer
    has better-calibrated weights for real-world use.
    """
    return _rule_based_score(features)


def _rule_based_score(features: list[float]) -> float:
    """Heuristic risk score with calibrated weights.

    Weight distribution (max 1.0):
      - Base risk:              0.10  (every task has some inherent risk)
      - Overdue days:           0.30  (overdue_days / 10, capped at 1)
      - Blocked:                0.25  (blocked tasks are high risk)
      - Effort variance:        0.20  (only for started tasks, |est-spent|/est)
      - Weak signal ratio:      0.10  (capped low so 1 comment doesn't dominate)
      - High priority:          0.05  (slight boost for HIGH/HIGHEST)
    """
    overdue = features[4] if len(features) > 4 else 0
    is_blocked = features[5] if len(features) > 5 else 0
    effort_var = features[10] if len(features) > 10 else 0
    weak_ratio = features[19] if len(features) > 19 else 0
    priority_high = features[9] if len(features) > 9 else 0

    score = 0.10  # base risk
    score += 0.30 * min(1, overdue / 10)   # overdue contribution
    score += 0.25 * is_blocked              # blocked contribution
    score += 0.20 * min(1, effort_var)      # effort variance (only for started tasks)
    score += 0.10 * min(1, weak_ratio)      # weak signal (capped)
    score += 0.05 * priority_high           # priority boost
    return min(1.0, score)


def explain(features: list[float], feature_names: list[str] | None = None) -> list[dict[str, Any]]:
    """Return the top-3 contributing factors for a feature vector.

    Uses SHAP if available, else rule-based attribution.
    """
    from .features import FEATURE_NAMES
    names = feature_names or FEATURE_NAMES

    model = _load_model()
    if model is not None and _explainer is not None:
        try:
            import shap
            shap_values = _explainer.shap_values(np.array([features]))
            # For binary classification, shap_values might be a list of 2 arrays
            if isinstance(shap_values, list):
                sv = shap_values[1][0]  # class 1 (high risk)
            else:
                sv = shap_values[0]
            # Top 3 by absolute contribution
            indexed = sorted(enumerate(sv), key=lambda x: abs(x[1]), reverse=True)[:3]
            return [
                {"label": names[i] if i < len(names) else f"feature_{i}", "weight": round(float(v), 4)}
                for i, v in indexed
            ]
        except Exception as e:
            logger.warning("SHAP explanation failed: %s — using rule-based", e)

    # Rule-based attribution
    factors = []
    if len(features) > 4 and features[4] > 0:  # overdue_days
        factors.append({"label": "overdue_days", "weight": round(min(0.5, features[4] / 20), 3)})
    if len(features) > 5 and features[5] > 0:  # is_blocked
        factors.append({"label": "is_blocked", "weight": 0.3})
    if len(features) > 10 and features[10] > 0.3:  # effort_variance
        factors.append({"label": "effort_variance", "weight": round(features[10] * 0.4, 3)})
    if len(features) > 19 and features[19] > 0.2:  # weak_signal_ratio
        factors.append({"label": "comment_weak_signal_ratio", "weight": round(features[19] * 0.3, 3)})
    return sorted(factors, key=lambda x: x["weight"], reverse=True)[:3]


def ensure_model_ready() -> bool:
    """Always returns False — we use rule-based scoring for realistic results.

    The XGBoost model trained on synthetic data gives unrealistic scores.
    Rule-based scoring with calibrated weights is more appropriate for
    real-world project risk assessment.
    """
    return False
