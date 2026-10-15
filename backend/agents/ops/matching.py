"""Matching compétences (embeddings) + affectation optimale (algorithme hongrois)."""
from difflib import SequenceMatcher

import numpy as np
from scipy.optimize import linear_sum_assignment

LOAD_WEIGHT = 0.8         # poids de la charge dans le coût (0 = on ignore la charge)
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


def _capacity(member):
    return member["capacity"] or DEFAULT_CAPACITY


def horizon_weeks(tasks, members):
    """Nb de semaines qu'il faut à l'équipe pour écouler charge existante + nouvelles tâches."""
    total_hours = sum(t["hours"] for t in tasks) + sum(m["load"] for m in members)
    total_capacity = sum(_capacity(m) for m in members) or DEFAULT_CAPACITY
    return max(1.0, total_hours / total_capacity)


def assign(tasks, members):
    """
    tasks   : [{"ref", "title", "skills": [str], "hours": float}]
    members : [{"id", "skills": {nom: niveau}, "load": heures déjà planifiées, "capacity": h/semaine}]
    Retourne une suggestion par tâche.
    """
    if not tasks or not members:
        return []
    n, m = len(tasks), len(members)
    avg_hours = (sum(t["hours"] for t in tasks) / n) or 1.0
    weeks = horizon_weeks(tasks, members)

    skill = np.zeros((n, m))
    matched = {}
    for i, t in enumerate(tasks):
        for j, mem in enumerate(members):
            skill[i, j], matched[i, j] = skill_score(t["skills"], mem["skills"])

    # Colonnes = (membre, rang). Le coût de charge est convexe (ratio²) : un membre
    # qui approche ou dépasse sa capacité sur l'horizon devient très coûteux.
    cols = [(j, k) for j in range(m) for k in range(n)]
    cost = np.zeros((n, len(cols)))
    for c, (j, k) in enumerate(cols):
        cap_h = _capacity(members[j]) * weeks
        for i, t in enumerate(tasks):
            ratio_after = (members[j]["load"] + k * avg_hours + t["hours"]) / cap_h
            cost[i, c] = -skill[i, j] + LOAD_WEIGHT * ratio_after ** 2

    rows, picked = linear_sum_assignment(cost)

    load = {j: members[j]["load"] for j in range(m)}
    out = []
    for i, c in zip(rows, picked):
        j = cols[c][0]
        mem, t = members[j], tasks[i]
        before = load[j]
        load[j] += t["hours"]
        skills_txt = ", ".join(matched[i, j]) or "aucune correspondance forte"
        out.append({
            "ref": t["ref"],
            "member_id": mem["id"],
            "score": round(float(skill[i, j]), 3),
            "matched_skills": matched[i, j],
            "workload_before": before,
            "workload_after": load[j],
            "rationale": f"Compétences : {skills_txt} · charge {before:.0f} h → {load[j]:.0f} h.",
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


def balance_report(tasks, members, results):
    """Indice d'équilibrage (sur le taux d'utilisation = charge / capacité) avant et après."""
    weeks = horizon_weeks(tasks, members)
    cap = {mem["id"]: _capacity(mem) * weeks for mem in members}
    before = {mem["id"]: mem["load"] for mem in members}
    after = dict(before)
    for r in results:
        after[r["member_id"]] = r["workload_after"]
    # On mesure l'équilibre entre les membres que l'agent peut réellement charger
    # (ceux déjà en surcharge sont exclus du calcul et signalés à part).
    eligible = [k for k in before if before[k] <= cap[k]] or list(before)
    util = lambda loads: [loads[k] / cap[k] for k in eligible]
    return {
        "before": load_balance_index(util(before)),
        "after": load_balance_index(util(after)),
        "horizon_weeks": weeks,
        "overloaded": [k for k in before if before[k] > cap[k]],
    }