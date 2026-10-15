"""Matching compétences (embeddings) + affectation optimale (algorithme hongrois)."""
import math
from difflib import SequenceMatcher

import numpy as np
from scipy.optimize import linear_sum_assignment

LOAD_WEIGHT = 0.35        # poids de la charge dans le coût (0 = on ignore la charge)
DEFAULT_CAPACITY = 35.0   # heures/semaine si la capacité du membre est inconnue

_MODEL = None
_MODEL_FAILED = False


def _get_model():
    """Charge le modèle d'embeddings une seule fois ; None si indisponible."""
    global _MODEL, _MODEL_FAILED
    if _MODEL is None and not _MODEL_FAILED:
        try:
            from sentence_transformers import SentenceTransformer
            _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _MODEL_FAILED = True
    return _MODEL


def backend_name():
    return "embeddings" if _get_model() is not None else "texte (repli)"


def similarity_matrix(required, owned):
    """Similarité [0, 1] : lignes = compétences requises, colonnes = possédées."""
    model = _get_model()
    if model is not None:
        a = model.encode(required, normalize_embeddings=True)
        b = model.encode(owned, normalize_embeddings=True)
        return np.clip(a @ b.T, 0, 1)
    return np.array([
        [SequenceMatcher(None, r.lower(), o.lower()).ratio() for o in owned]
        for r in required
    ])


def skill_score(required, member_skills):
    """Score [0, 1] d'un membre pour une tâche + compétences qui correspondent."""
    if not required:
        return 0.5, []          # tâche sans compétence précisée : neutre
    if not member_skills:
        return 0.0, []
    owned = list(member_skills)
    sim = similarity_matrix(required, owned)
    scores, matched = [], []
    for i in range(len(required)):
        j = int(sim[i].argmax())
        level_factor = 0.5 + 0.5 * member_skills[owned[j]] / 5   # niveau 1..5 -> 0.6..1.0
        scores.append(float(sim[i, j]) * level_factor)
        if sim[i, j] >= 0.6:
            matched.append(owned[j])
    return float(np.mean(scores)), matched


def assign(tasks, members):
    """
    tasks   : [{"ref", "title", "skills": [str], "hours": float}]
    members : [{"id", "skills": {nom: niveau}, "load": heures déjà planifiées, "capacity": h/semaine}]
    Retourne une suggestion par tâche (même ordre que `tasks`).
    """
    if not tasks or not members:
        return []
    n, m = len(tasks), len(members)
    avg_hours = (sum(t["hours"] for t in tasks) / n) or 1.0
    slots = math.ceil(n / m) + 1

    skill = np.zeros((n, m))
    matched = {}
    for i, t in enumerate(tasks):
        for j, mem in enumerate(members):
            skill[i, j], matched[i, j] = skill_score(t["skills"], mem["skills"])

    # Colonnes = (membre, rang). Le coût de charge croît avec le rang : le
    # problème d'affectation répartit donc le travail au lieu de tout empiler.
    cols = [(j, k) for j in range(m) for k in range(slots)]
    cost = np.zeros((n, len(cols)))
    for c, (j, k) in enumerate(cols):
        cap = members[j]["capacity"] or DEFAULT_CAPACITY
        base = (members[j]["load"] + k * avg_hours) / cap
        for i, t in enumerate(tasks):
            cost[i, c] = -skill[i, j] + LOAD_WEIGHT * (base + t["hours"] / cap)

    rows, picked = linear_sum_assignment(cost)

    load = {j: members[j]["load"] for j in range(m)}
    out = []
    for i, c in zip(rows, picked):
        j = cols[c][0]
        mem, t = members[j], tasks[i]
        before = load[j]
        load[j] += t["hours"]
        cap = mem["capacity"] or DEFAULT_CAPACITY
        skills_txt = ", ".join(matched[i, j]) or "aucune correspondance forte"
        out.append({
            "ref": t["ref"],
            "member_id": mem["id"],
            "score": round(float(skill[i, j]), 3),
            "matched_skills": matched[i, j],
            "workload_before": before,
            "workload_after": load[j],
            "rationale": f"Compétences : {skills_txt} · charge {before:.0f} h → {load[j]:.0f} h sur {cap:.0f} h.",
        })
    return out


def load_balance_index(loads):
    """Indice d'équilibrage : 1 = parfait, baisse avec la dispersion (1 - coef. de variation)."""
    loads = list(loads)
    if not loads or sum(loads) == 0:
        return 1.0
    mean = sum(loads) / len(loads)
    std = (sum((x - mean) ** 2 for x in loads) / len(loads)) ** 0.5
    return max(0.0, 1 - std / mean)