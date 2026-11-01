"""
Moteurs des trois agents Cadria.

Les moteurs sont des fonctions pures : ils reçoivent la charge utile décrite
dans `orchestration.services` et renvoient une enveloppe normalisée
(`status`, `output`, `step`, `latency_ms`, `tokens_in`, `tokens_out`).
Aucun accès base de données ni appel réseau : le service `dispatch()` se charge
de la persistance, et `runtime_server` peut les exposer en HTTP.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from typing import Any


def execute(agent_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Exécute l'agent demandé et renvoie une enveloppe normalisée."""
    started = time.perf_counter()
    runner = {
        "SCOPING": run_scoping,
        "OPS": run_ops,
        "RISK": run_risk,
    }.get(agent_key)
    if runner is None:
        return _envelope("FAILED", {}, "Agent inconnu", started,
                         error=f"Aucun moteur pour l'agent « {agent_key} ».")

    try:
        result = runner(payload or {})
    except Exception as exc:  # noqa: BLE001 — le service convertit en échec propre
        return _envelope("FAILED", {}, "Échec du moteur", started,
                         error=f"{type(exc).__name__}: {exc}")

    status = result.pop("_status", "SUCCEEDED")
    step = result.pop("_step", "Terminé")
    error = result.pop("_error", None)
    return _envelope(status, result, step, started, error=error)


def _envelope(status: str, output: dict[str, Any], step: str, started: float,
              error: str | None = None) -> dict[str, Any]:
    latency = int((time.perf_counter() - started) * 1000)
    dumped = json.dumps(output, ensure_ascii=False, default=str)
    return {
        "status": status,
        "output": output,
        "step": step,
        "tokens_in": max(0, len(dumped) // 8),
        "tokens_out": max(0, len(dumped) // 4),
        "latency_ms": latency,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Agent 1 — Cadrage & décomposition
# ---------------------------------------------------------------------------
_LOT_CATALOG = [
    {
        "key": "governance",
        "name": "Cadrage & gouvernance",
        "description": "Cadrage du besoin, périmètre, backlog initial et gouvernance projet.",
        "color": "#2563EB",
        "base_hours": 90,
        "keywords": [],
        "skills": ["Gestion de projet"],
        "tasks": [
            ("Ateliers de cadrage et validation du périmètre", "SPIKE", 0.35),
            ("Backlog initial et critères d'acceptation", "DOC", 0.30),
            ("Plan de communication et gouvernance", "DOC", 0.35),
        ],
    },
    {
        "key": "ux",
        "name": "Conception UX & design system",
        "description": "Recherche utilisateur, parcours, maquettes et composants d'interface.",
        "color": "#0EA5E9",
        "base_hours": 160,
        "keywords": ["ux", "ui", "design", "maquette", "parcours", "ergonomie",
                     "accessib", "rgaa", "prototype", "wireframe"],
        "skills": ["UI Design", "UX Research"],
        "tasks": [
            ("Recherche utilisateurs et parcours cibles", "SPIKE", 0.30),
            ("Maquettes et prototype interactif", "FEATURE", 0.40),
            ("Design system et composants réutilisables", "FEATURE", 0.30),
        ],
    },
    {
        "key": "frontend",
        "name": "Front-end & interfaces",
        "description": "Socle applicatif, écrans métier et qualité d'interface.",
        "color": "#0284C7",
        "base_hours": 240,
        "keywords": ["front", "react", "interface", "écran", "ecran", "portail", "web",
                     "responsive", "composant", "vue", "angular", "tailwind"],
        "skills": ["React", "TypeScript", "UI Design"],
        "tasks": [
            ("Socle front-end et navigation", "TECH", 0.30),
            ("Écrans et parcours utilisateurs", "FEATURE", 0.45),
            ("Responsive et accessibilité", "TECH", 0.25),
        ],
    },
    {
        "key": "backend",
        "name": "Back-end & API",
        "description": "Modèle de données, logique métier et exposition des services.",
        "color": "#1D4ED8",
        "base_hours": 260,
        "keywords": ["api", "backend", "back-end", "rest", "endpoint", "service",
                     "serveur", "django", "node", "python", "graphql", "microservice"],
        "skills": ["Django", "REST API", "Python"],
        "tasks": [
            ("Conception du modèle de données et des contrats d'API", "SPIKE", 0.25),
            ("Implémentation des endpoints métier", "FEATURE", 0.50),
            ("Documentation OpenAPI et tests d'intégration", "DOC", 0.25),
        ],
    },
    {
        "key": "auth",
        "name": "Authentification & sécurité",
        "description": "Identité, permissions, conformité et durcissement.",
        "color": "#0369A1",
        "base_hours": 180,
        "keywords": ["sso", "authentification", "auth", "keycloak", "oidc", "sécurité",
                     "securite", "permission", "rgpd", "rôle", "role", "identité"],
        "skills": ["Docker", "Conformité RGPD"],
        "tasks": [
            ("Intégration du fournisseur d'identité", "FEATURE", 0.45),
            ("Matrice des rôles et permissions", "DOC", 0.25),
            ("Audit de sécurité et correctifs", "TECH", 0.30),
        ],
    },
    {
        "key": "integration",
        "name": "Intégrations & connecteurs",
        "description": "Interfaces avec les systèmes externes et supervision des flux.",
        "color": "#0E7490",
        "base_hours": 200,
        "keywords": ["intégration", "integration", "connecteur", "jira", "trello", "erp",
                     "sap", "webhook", "sync", "synchronisation", "interopérabilité"],
        "skills": ["REST API", "Python"],
        "tasks": [
            ("Cartographie des flux et formats d'échange", "SPIKE", 0.25),
            ("Développement des connecteurs", "FEATURE", 0.50),
            ("Idempotence, reprise et supervision", "TECH", 0.25),
        ],
    },
    {
        "key": "data",
        "name": "Données & reporting",
        "description": "Alimentation, qualité et restitution des données.",
        "color": "#0891B2",
        "base_hours": 180,
        "keywords": ["data", "donnée", "donnee", "reporting", "dashboard", "tableau de bord",
                     "sql", "etl", "pipeline", "analytique", "kpi", "indicateur"],
        "skills": ["Data engineering", "Python"],
        "tasks": [
            ("Modélisation et pipeline d'alimentation", "TECH", 0.40),
            ("Tableaux de bord et indicateurs", "FEATURE", 0.40),
            ("Contrôles qualité des données", "TEST", 0.20),
        ],
    },
    {
        "key": "mobile",
        "name": "Application mobile",
        "description": "Application iOS/Android, usages terrain et mode dégradé.",
        "color": "#7C3AED",
        "base_hours": 240,
        "keywords": ["mobile", "ios", "android", "react native", "offline", "hors ligne",
                     "terrain", "tablette"],
        "skills": ["React", "TypeScript"],
        "tasks": [
            ("Socle React Native et navigation", "TECH", 0.30),
            ("Formulaires et fonctionnalités métier", "FEATURE", 0.45),
            ("Mode hors ligne et synchronisation", "TECH", 0.25),
        ],
    },
    {
        "key": "devops",
        "name": "Infrastructure & DevOps",
        "description": "Cible d'hébergement, industrialisation et exploitation.",
        "color": "#1E40AF",
        "base_hours": 220,
        "keywords": ["cloud", "kubernetes", "docker", "ci/cd", "déploiement", "deploiement",
                     "infrastructure", "migration", "conteneur", "gitops", "terraform",
                     "on-premise", "observabilité"],
        "skills": ["Docker", "Kubernetes", "CI/CD"],
        "tasks": [
            ("Inventaire et cible d'architecture", "DOC", 0.25),
            ("Industrialisation des déploiements", "TECH", 0.45),
            ("Observabilité et plan de reprise", "TECH", 0.30),
        ],
    },
    {
        "key": "ai",
        "name": "IA & modèles",
        "description": "Corpus, entraînement, intégration et suivi des modèles.",
        "color": "#8B5CF6",
        "base_hours": 260,
        "keywords": ["ia", "ml", "llm", "rag", "modèle", "modele", "agent", "xgboost",
                     "nlp", "machine learning", "fine-tuning", "embedding", "camembert"],
        "skills": ["Machine Learning", "Python", "NLP"],
        "tasks": [
            ("Constitution du corpus et protocole d'évaluation", "SPIKE", 0.30),
            ("Entraînement et intégration du modèle", "FEATURE", 0.50),
            ("Monitoring et réentraînement", "TECH", 0.20),
        ],
    },
    {
        "key": "qa",
        "name": "Recette & qualité",
        "description": "Stratégie de test, automatisation et campagnes de recette.",
        "color": "#059669",
        "base_hours": 150,
        "keywords": ["test", "recette", "qualité", "qualite", "cypress", "e2e", "qa",
                     "non-régression", "couverture"],
        "skills": ["Recette fonctionnelle", "CI/CD"],
        "tasks": [
            ("Plan de recette et jeux de tests", "TEST", 0.35),
            ("Automatisation des tests", "TEST", 0.40),
            ("Campagne de recette et corrections", "TEST", 0.25),
        ],
    },
    {
        "key": "change",
        "name": "Conduite du changement",
        "description": "Formation, documentation et accompagnement des utilisateurs.",
        "color": "#D97706",
        "base_hours": 100,
        "keywords": ["formation", "conduite", "changement", "documentation", "support",
                     "adoption", "utilisateur"],
        "skills": ["Gestion de projet"],
        "tasks": [
            ("Plan de formation et documentation", "DOC", 0.50),
            ("Accompagnement des utilisateurs", "DOC", 0.30),
            ("Mesure de l'adoption", "TEST", 0.20),
        ],
    },
    {
        "key": "core",
        "name": "Réalisation & fonctionnalités",
        "description": "Développement du cœur fonctionnel décrit dans le brief.",
        "color": "#2563EB",
        "base_hours": 220,
        "keywords": [],
        "skills": ["Gestion de projet"],
        "tasks": [
            ("Analyse fonctionnelle détaillée", "SPIKE", 0.25),
            ("Développement des fonctionnalités", "FEATURE", 0.55),
            ("Tests unitaires et revue de code", "TEST", 0.20),
        ],
    },
    {
        "key": "deployment",
        "name": "Mise en production",
        "description": "Préparation du go-live, bascule et transfert aux équipes.",
        "color": "#0284C7",
        "base_hours": 80,
        "keywords": [],
        "skills": ["CI/CD"],
        "tasks": [
            ("Préparation du go-live et du rollback", "TECH", 0.40),
            ("Bascule et vérifications post-production", "TECH", 0.35),
            ("Rétrospective et transfert de connaissances", "DOC", 0.25),
        ],
    },
]

_SPRINT_SUFFIXES = [
    "Fondations", "Socle", "Accélération", "Durcissement",
    "Mise en production", "Stabilisation",
]

_WEAK_WORDS = ["bloqué", "bloque", "en attente", "régression", "regression", "impossible",
               "erreur", "retard", "panne", "urgent", "bug", "blocked", "waiting",
               "dépendance", "dependance"]

_SHORT_KEYWORDS = {"ia", "ml", "ux", "ui", "qa", "api", "rag", "sso", "erp", "sap", "kpi"}

_ACCEPTANCE_CRITERIA: dict[str, list[str]] = {
    "FEATURE": [
        "Le comportement correspond aux critères d'acceptation définis en atelier.",
        "Les tests unitaires et d'intégration couvrent les cas nominaux et limites.",
        "La fonctionnalité est démontrée et validée par le PO.",
    ],
    "TECH": [
        "La solution ne dégrade pas les métriques de performance existantes.",
        "Une revue de code a été effectuée par un pair.",
        "La documentation technique est à jour.",
    ],
    "SPIKE": [
        "Un rapport d'exploration est produit (choix technologique justifié).",
        "Les risques identifiés sont documentés et un plan d'action est proposé.",
        "La décision est partagée avec l'équipe lors d'une revue dédiée.",
    ],
    "DOC": [
        "La documentation est relue par au moins un pair.",
        "Les exemples sont vérifiés et fonctionnels.",
        "Le document est publié dans l'espace de connaissance du projet.",
    ],
    "TEST": [
        "Le plan de test est approuvé par le responsable qualité.",
        "Le taux de couverture cible est atteint.",
        "Les résultats sont archivés et les anomalies sont tracées.",
    ],
    "BUG": [
        "La correction est vérifiée en environnement de recette.",
        "Un test de non-régression couvre le scénario initial.",
        "L'anomalie est clôturée dans le système de suivi.",
    ],
}


def run_scoping(payload: dict[str, Any]) -> dict[str, Any]:
    brief = str(payload.get("brief") or "").strip()
    constraints = payload.get("constraints") or {}
    team = payload.get("team") or []
    methodology = str(payload.get("methodology") or "SCRUM").upper()

    text = _normalise(brief)
    selected = _select_lots(text)
    complexity = _complexity(text, selected)
    capacity = sum(float(m.get("capacity_hours") or 0) for m in team) or 35.0

    lots: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    ref = 1
    total = 0.0

    for order, lot in enumerate(selected):
        raw_share = float(lot["base_hours"]) * complexity
        task_rows = []
        allocated = 0.0
        for idx, (title, task_type, share) in enumerate(lot["tasks"]):
            hours = round(raw_share * share * 2) / 2
            if idx == len(lot["tasks"]) - 1:
                hours = max(0.5, round((raw_share - allocated) * 2) / 2)
            allocated += hours
            task_rows.append({
                "ref": f"T-{ref:03d}",
                "lot": lot["name"],
                "title": title,
                "description": f"{title}. Issu du cadrage de « {payload.get('project_reference', 'projet')} ».",
                "type": task_type,
                "priority": "HIGH" if idx == 0 else "MEDIUM",
                "estimate_hours": hours,
                "story_points": _story_points(hours, task_type),
                "skills": list(lot["skills"]),
                "acceptance_criteria": _ACCEPTANCE_CRITERIA.get(task_type, _ACCEPTANCE_CRITERIA["FEATURE"]),
                "risk_score": round(min(85, 12 + complexity * 18 + idx * 5), 1),
            })
            ref += 1

        lot_hours = round(sum(t["estimate_hours"] for t in task_rows), 1)
        total += lot_hours
        lots.append({
            "name": lot["name"],
            "description": lot["description"],
            "estimate_hours": lot_hours,
            "confidence": round(_lot_confidence(brief, team), 2),
            "color": lot["color"],
            "order": order,
        })
        tasks.extend(task_rows)

    sprints = _build_sprints(total, capacity, methodology)
    _assign_sprints(tasks, sprints, float(sprints[0]["capacity_hours"]) if sprints else capacity)

    risks = _scoping_risks(total, constraints, team, methodology)
    confidence = _global_confidence(brief, team, constraints)
    assumptions = _assumptions(team, constraints, methodology)

    return {
        "lots": lots,
        "tasks": tasks,
        "sprints": sprints,
        "risks": risks,
        "assumptions": assumptions,
        "total_estimate_hours": round(total, 1),
        "confidence": confidence,
        "_step": f"Découpage terminé — {len(lots)} lots, {len(tasks)} tâches, {len(sprints)} sprints",
    }


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _select_lots(text: str) -> list[dict[str, Any]]:
    selected = [lot for lot in _LOT_CATALOG if lot["key"] in ("governance", "deployment")]
    matched = []
    for lot in _LOT_CATALOG:
        if lot["key"] in ("governance", "deployment"):
            continue
        if any(_matches(text, keyword) for keyword in lot["keywords"]):
            matched.append(lot)

    if not matched:
        matched = [lot for lot in _LOT_CATALOG if lot["key"] == "core"]
    selected[1:1] = matched
    return selected


def _matches(text: str, keyword: str) -> bool:
    if keyword in _SHORT_KEYWORDS:
        pattern = rf"\b{re.escape(keyword)}\b" if keyword == "ia" else rf"\b{re.escape(keyword)}"
        return bool(re.search(pattern, text))
    if len(keyword) <= 4:
        return bool(re.search(rf"\b{re.escape(keyword)}", text))
    return keyword in text


def _complexity(text: str, lots: list[dict[str, Any]]) -> float:
    words = len(text.split())
    return round(min(1.45, 0.85 + words / 1800 + 0.04 * max(0, len(lots) - 3)), 2)


def _story_points(hours: float, task_type: str) -> float:
    divisor = 7 if task_type in ("FEATURE", "TECH") else 5
    return max(1.0, round(hours / divisor, 1))


def _lot_confidence(brief: str, team: list[dict[str, Any]]) -> float:
    score = 0.55 + min(len(brief) / 2500, 0.25) + (0.08 if team else 0)
    return min(0.92, score)


def _global_confidence(brief: str, team: list[dict[str, Any]],
                       constraints: dict[str, Any]) -> float:
    score = 0.52 + min(len(brief) / 2600, 0.24) + (0.08 if team else 0)
    score += 0.04 if constraints.get("budget") else 0
    score += 0.04 if constraints.get("deadline") else 0
    return round(min(0.94, score), 2)


def _build_sprints(total: float, capacity: float, methodology: str) -> list[dict[str, Any]]:
    sprint_capacity = max(60.0, capacity * 2)
    count = max(1, min(6, int(total / sprint_capacity) + (1 if total % sprint_capacity else 0)))
    if methodology == "KANBAN":
        count = max(1, min(3, count))
    sprints = []
    for i in range(count):
        suffix = _SPRINT_SUFFIXES[i % len(_SPRINT_SUFFIXES)]
        sprints.append({
            "name": f"Sprint {i + 1} · {suffix}",
            "goal": f"Livrer un incrément démontrable — {suffix.lower()}.",
            "capacity_hours": round(sprint_capacity, 1),
        })
    return sprints


def _assign_sprints(tasks: list[dict[str, Any]], sprints: list[dict[str, Any]],
                    capacity: float) -> None:
    if not sprints:
        return
    index = 0
    used = 0.0
    for task in tasks:
        hours = float(task["estimate_hours"])
        if index < len(sprints) - 1 and used + hours > capacity:
            index += 1
            used = 0.0
        task["sprint"] = sprints[index]["name"]
        used += hours


def _scoping_risks(total: float, constraints: dict[str, Any],
                   team: list[dict[str, Any]], methodology: str) -> list[dict[str, Any]]:
    risks = [{
        "category": "DELAY",
        "title": "Risque de dérive planning",
        "score": round(min(80, 30 + total / 40), 1),
        "severity": "WARNING" if total > 700 else "INFO",
    }]
    if not team:
        risks.append({
            "category": "LOAD",
            "title": "Équipe non renseignée",
            "score": 72,
            "severity": "CRITICAL",
        })
    elif total / max(1.0, sum(float(m.get("capacity_hours") or 0) for m in team)) > 12:
        risks.append({
            "category": "LOAD",
            "title": "Charge supérieure à la capacité de l'équipe",
            "score": 64,
            "severity": "WARNING",
        })

    budget = constraints.get("budget")
    if budget:
        estimated_cost = total * 55
        if estimated_cost > float(budget):
            risks.append({
                "category": "BUDGET",
                "title": "Enveloppe budgétaire insuffisante",
                "score": round(min(90, 45 + (estimated_cost / float(budget) - 1) * 50), 1),
                "severity": "CRITICAL",
            })

    deadline = constraints.get("deadline")
    if deadline:
        try:
            remaining = (date.fromisoformat(str(deadline)) - date.today()).days
        except ValueError:
            remaining = None
        if remaining is not None and remaining < 90 and total > 600:
            risks.append({
                "category": "DELAY",
                "title": "Échéance proche pour un périmètre large",
                "score": 74,
                "severity": "CRITICAL",
            })

    if methodology == "KANBAN":
        risks.append({
            "category": "SCOPE",
            "title": "Flux continu sans engagement de sprint",
            "score": 38,
            "severity": "INFO",
        })
    return risks


def _assumptions(team: list[dict[str, Any]], constraints: dict[str, Any],
                 methodology: str) -> list[str]:
    out = [
        f"Équipe disponible sur la durée du projet ({len(team)} membre(s))." if team
        else "L'équipe sera confirmée avant le démarrage effectif.",
        f"Estimation fondée sur une capacité hebdomadaire cumulée de "
        f"{sum(float(m.get('capacity_hours') or 0) for m in team) or 35:.0f} h.",
        f"Pilotage en méthodologie {methodology}.",
    ]
    if constraints.get("deadline"):
        out.append(f"Échéance cible : {constraints['deadline']}.")
    if constraints.get("budget"):
        out.append(f"Budget indicatif : {constraints['budget']}.")
    out.append("Les dépendances externes sont fournies dans les délais convenus.")
    return out


# ---------------------------------------------------------------------------
# Agent 2 — Intégration & assignation
# ---------------------------------------------------------------------------
def run_ops(payload: dict[str, Any]) -> dict[str, Any]:
    tasks = payload.get("tasks") or []
    team = payload.get("team") or []
    provider = str(payload.get("provider") or "JIRA").upper()
    dry_run = bool(payload.get("dry_run", True))

    if not tasks:
        return {
            "_status": "FAILED",
            "_step": "Préparation impossible",
            "_error": "Aucune tâche à intégrer : validez d'abord un plan de l'Agent 1.",
            "created": [],
            "assignments": [],
            "api_calls": 0,
            "errors": ["Plan vide."],
        }

    loads = {
        int(m["id"]): float(m.get("current_load_hours") or 0)
        for m in team if m.get("id") is not None
    }
    suggestions = []
    for task in tasks:
        candidate = _best_candidate(task, team, loads)
        if candidate:
            suggestions.append(candidate)
            loads[int(candidate["user_id"])] += float(task.get("estimate_hours") or 0)

    accepted = payload.get("assignments") or []
    applied = [
        {
            "task_ref": a.get("task_ref"),
            "user_id": a.get("user_id"),
            "applied": bool(a.get("task_ref")) and not dry_run,
        }
        for a in accepted
    ]

    errors = []
    if not dry_run:
        errors.append(
            f"Écriture {provider} non effectuée : aucun connecteur authentifié n'est configuré. "
            "Le plan reste validable dans Cadria."
        )

    return {
        "created": [],
        "planned": [t.get("ref") for t in tasks],
        "assignments": applied,
        "suggestions": suggestions,
        "api_calls": 0,
        "dry_run": dry_run,
        "provider": provider,
        "errors": errors,
        "_step": (
            f"Simulation terminée — {len(suggestions)} assignation(s) proposée(s)"
            if dry_run else
            "Préparation terminée — écriture externe en attente de validation"
        ),
    }


def _best_candidate(task: dict[str, Any], team: list[dict[str, Any]],
                    loads: dict[int, float]) -> dict[str, Any] | None:
    if not team:
        return None
    required = [str(s) for s in (task.get("skills") or [])]
    best = None
    for member in team:
        member_id = int(member.get("id"))
        capacity = float(member.get("capacity_hours") or 35) * 4
        before = loads.get(member_id, 0.0)
        after = before + float(task.get("estimate_hours") or 0)
        skill_levels = {
            str(s.get("name")): float(s.get("level") or 0)
            for s in (member.get("skills") or [])
        }
        if required:
            matched = [s for s in required if s in skill_levels]
            skill_score = sum(skill_levels[s] for s in matched) / (len(required) * 5)
        else:
            matched = []
            skill_score = 0.5
        load_ratio = after / max(1.0, capacity)
        load_score = max(0.0, 1.0 - min(load_ratio, 1.0))
        score = round(min(0.99, 0.7 * skill_score + 0.3 * load_score), 3)
        if best is None or score > best["match_score"]:
            best = {
                "task_ref": task.get("ref"),
                "task_title": task.get("title", ""),
                "user_id": member_id,
                "match_score": score,
                "rationale": (
                    f"{'Compétences ' + ', '.join(matched) if matched else 'Profil généraliste'} · "
                    f"charge après affectation {after:.0f} h "
                    f"({load_ratio * 100:.0f} % de la capacité sur 4 semaines)."
                ),
                "matched_skills": matched or required,
                "workload_before_hours": round(before, 1),
                "workload_after_hours": round(after, 1),
            }
    return best


# ---------------------------------------------------------------------------
# Agent 3 — Analyse & suivi des risques
# ---------------------------------------------------------------------------
def run_risk(payload: dict[str, Any]) -> dict[str, Any]:
    tasks = payload.get("tasks") or []
    comments = payload.get("comments") or []
    members = payload.get("members") or []
    today = date.today()

    blocked = [t for t in tasks if t.get("blocked") and t.get("status") != "DONE"]
    overdue = [_is_overdue(t, today) for t in tasks]
    overdue = [t for t in overdue if t]
    overrun = [t for t in tasks if _is_overrun(t)]
    high_risk = [t for t in tasks if float(t.get("risk_score") or 0) >= 60]
    weak_comments = [
        c for c in comments
        if c.get("weak_signal") or any(w in str(c.get("body") or "").lower() for w in _WEAK_WORDS)
    ]
    overloaded = [
        m for m in members
        if float(m.get("load_hours") or 0) > float(m.get("capacity_hours") or 35) * 4
    ]

    blocker_score = min(100.0, 35 + 15 * len(blocked))
    delay_score = min(100.0, 22 + 12 * len(overdue) + 8 * len(overrun))
    quality_score = min(100.0, 18 + 11 * len(weak_comments))
    load_score = min(100.0, 25 + 22 * len(overloaded))
    global_score = round(
        0.28 * blocker_score + 0.28 * delay_score + 0.16 * quality_score
        + 0.14 * load_score + 0.14 * min(100.0, len(high_risk) * 14),
        1,
    )

    alerts = []
    for task in blocked[:3]:
        score = min(100.0, 62 + 8 * len(blocked))
        alerts.append(_alert(
            "BLOCKER", score, f"Tâche bloquée · {task.get('title', 'sans titre')}",
            task.get("blocked_reason") or "Blocage remonté sans plan de déblocage associé.",
            [{"label": "Blocage actif", "weight": 0.6},
             {"label": "Impact sur le chemin critique", "weight": 0.4}],
            "Organiser une réunion de déblocage sous 24 h avec le référent métier.",
            task=task,
        ))
    for task in overdue[:3]:
        alerts.append(_alert(
            "DELAY", 68, f"Échéance dépassée · {task.get('title', 'sans titre')}",
            f"Échéance {task.get('due_date')} dépassée alors que la tâche est au statut "
            f"{task.get('status')}.",
            [{"label": "Date d'échéance dépassée", "weight": 0.55},
             {"label": "Reste à faire non nul", "weight": 0.45}],
            "Replanifier la tâche et arbitrer les dépendances du sprint.",
            task=task,
        ))
    for task in overrun[:2]:
        alerts.append(_alert(
            "DELAY", 58, f"Dérive d'estimation · {task.get('title', 'sans titre')}",
            f"{float(task.get('spent_hours') or 0):.1f} h réalisées pour "
            f"{float(task.get('estimate_hours') or 0):.1f} h estimées.",
            [{"label": "Écart estimé / réalisé", "weight": 0.6},
             {"label": "Estimation initiale dépassée", "weight": 0.4}],
            "Ré-estimer le reste à faire et suivre la consommation quotidienne.",
            task=task,
        ))
    if len(weak_comments) >= 2:
        alerts.append(_alert(
            "QUALITY", min(100.0, 40 + 8 * len(weak_comments)),
            "Signaux faibles détectés dans les commentaires",
            f"{len(weak_comments)} commentaire(s) mentionnent un blocage, une régression "
            "ou une dépendance non tenue.",
            [{"label": "Analyse lexicale des commentaires", "weight": 0.6},
             {"label": "Absence de plan d'action", "weight": 0.4}],
            "Revue de risques dédiée et plan d'action documenté pour chaque signal.",
        ))
    for member in overloaded[:2]:
        alerts.append(_alert(
            "LOAD", 66, f"Surcharge · {member.get('name', 'membre')}",
            f"Charge de {float(member.get('load_hours') or 0):.0f} h pour une capacité "
            f"de {float(member.get('capacity_hours') or 35) * 4:.0f} h sur 4 semaines.",
            [{"label": "Capacité dépassée", "weight": 0.7},
             {"label": "Tâches prioritaires en cours", "weight": 0.3}],
            "Redistribuer les tâches non critiques ou ajuster l'objectif du sprint.",
        ))

    budget = payload.get("budget")
    progress = float(payload.get("progress") or 0)
    spent_ratio = float(payload.get("budget_consumed") or 0)
    if budget and spent_ratio > progress + 15:
        alerts.append(_alert(
            "BUDGET", min(100.0, 45 + spent_ratio - progress),
            "Consommation budgétaire en avance sur l'avancement",
            f"{spent_ratio:.0f} % du budget consommé pour {progress:.0f} % d'avancement.",
            [{"label": "Écart budget / avancement", "weight": 0.6},
             {"label": "Charge réalisée en hausse", "weight": 0.4}],
            "Présenter un arbitrage au comité de pilotage : périmètre ou budget.",
        ))

    factors = []
    if blocked:
        factors.append(f"{len(blocked)} tâche(s) bloquée(s)")
    if overdue:
        factors.append(f"{len(overdue)} tâche(s) en retard")
    if overrun:
        factors.append(f"{len(overrun)} dérive(s) d'estimation")
    if weak_comments:
        factors.append(f"{len(weak_comments)} signal(aux) faible(s)")
    if overloaded:
        factors.append(f"{len(overloaded)} membre(s) en surcharge")
    if not factors:
        factors.append("Aucun signal critique détecté sur la fenêtre analysée")

    return {
        "risk_score": global_score,
        "alerts": alerts,
        "factors": factors,
        "window_days": int(payload.get("window_days") or 30),
        "_step": f"Analyse terminée — {len(alerts)} alerte(s), score {global_score:.0f}/100",
    }


def _is_overdue(task: dict[str, Any], today: date) -> dict[str, Any] | None:
    raw = task.get("due_date")
    if not raw or task.get("status") == "DONE":
        return None
    try:
        due = datetime.fromisoformat(str(raw)[:10]).date()
    except ValueError:
        return None
    return task if due < today else None


def _is_overrun(task: dict[str, Any]) -> bool:
    estimate = float(task.get("estimate_hours") or 0)
    spent = float(task.get("spent_hours") or 0)
    return estimate > 0 and spent > estimate * 1.15 and task.get("status") != "DONE"


def _alert(category: str, score: float, title: str, message: str,
           factors: list[dict[str, Any]], recommendation: str,
           task: dict[str, Any] | None = None) -> dict[str, Any]:
    severity = "CRITICAL" if score >= 70 else "WARNING" if score >= 40 else "INFO"
    alert = {
        "category": category,
        "severity": severity,
        "title": title,
        "message": message,
        "score": round(score, 1),
        "factors": factors,
        "recommendation": recommendation,
    }
    if task:
        alert["task_id"] = task.get("id")
        alert["task_title"] = task.get("title")
    return alert
