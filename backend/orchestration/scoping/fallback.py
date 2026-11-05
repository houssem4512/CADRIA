"""
Deterministic fallback for the Scoping Agent.

Used when:
  - GROQ_API_KEY is not set
  - the Groq API call fails after retries
  - the LLM output fails Pydantic validation twice

Produces a valid plan based on keyword matching on the brief,
similar to Mohamedali's engines.py approach (Système Expert Déterministe).
The plan is simpler than the LLM's but guaranteed correct mathematically.
"""
from __future__ import annotations
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Domain catalog — keyword → (lot_name, color, base_hours, skills, task_templates)
_LOT_CATALOG: list[dict[str, Any]] = [
    {
        "keywords": ["api", "backend", "django", "rest", "endpoint", "python", "graphql", "server"],
        "lot": {"name": "Back-end & API", "color": "#2563EB", "base_hours": 240},
        "skills": ["Django", "REST API", "Python"],
        "tasks": [
            ("Modélisation données & contrats API", "SPIKE", "HIGH", 16),
            ("Endpoints métier CRUD", "FEATURE", "HIGHEST", 40),
            ("Authentification & permissions", "FEATURE", "HIGH", 24),
            ("Documentation OpenAPI", "DOC", "MEDIUM", 12),
            ("Tests d'intégration API", "TEST", "HIGH", 20),
        ],
    },
    {
        "keywords": ["react", "front", "frontend", "interface", "ecran", "écran", "portail", "web", "tailwind", "ui"],
        "lot": {"name": "Front-end Web", "color": "#0EA5E9", "base_hours": 280},
        "skills": ["React", "TypeScript", "UI Design"],
        "tasks": [
            ("Socle front & routing", "TECH", "HIGH", 20),
            ("Composants UI & design system", "FEATURE", "HIGH", 32),
            ("Écrans utilisateurs principaux", "FEATURE", "HIGHEST", 48),
            ("Intégration API & state management", "TECH", "HIGH", 24),
            ("Responsive & accessibilité", "TECH", "MEDIUM", 16),
        ],
    },
    {
        "keywords": ["sso", "keycloak", "auth", "authentification", "sécurité", "securite", "permission", "rgpd"],
        "lot": {"name": "Sécurité & SSO", "color": "#1E40AF", "base_hours": 120},
        "skills": ["Docker", "Conformité RGPD", "Keycloak"],
        "tasks": [
            ("Configuration fournisseur d'identité", "FEATURE", "HIGH", 24),
            ("Matrice rôles & permissions", "DOC", "HIGH", 16),
            ("Audit sécurité & durcissement", "TECH", "MEDIUM", 20),
        ],
    },
    {
        "keywords": ["mobile", "ios", "android", "react native", "offline", "terrain"],
        "lot": {"name": "Mobile", "color": "#0284C7", "base_hours": 200},
        "skills": ["React", "TypeScript", "React Native"],
        "tasks": [
            ("Socle React Native & navigation", "TECH", "HIGH", 24),
            ("Écrans métier mobiles", "FEATURE", "HIGH", 40),
            ("Mode offline & synchronisation", "TECH", "MEDIUM", 24),
        ],
    },
    {
        "keywords": ["test", "recette", "qualite", "qualité", "cypress", "e2e", "qa", "automation"],
        "lot": {"name": "QA & Recette", "color": "#0369A1", "base_hours": 100},
        "skills": ["Recette fonctionnelle", "CI/CD", "Cypress"],
        "tasks": [
            ("Plan de recette & scénarios", "TEST", "HIGH", 16),
            ("Automatisation tests E2E", "TEST", "HIGH", 24),
            ("Campagne de recette & corrections", "TEST", "MEDIUM", 20),
        ],
    },
    {
        "keywords": ["devops", "docker", "kubernetes", "ci", "cd", "deploy", "déploiement", "infra"],
        "lot": {"name": "DevOps & Déploiement", "color": "#1D4ED8", "base_hours": 80},
        "skills": ["Docker", "Kubernetes", "CI/CD"],
        "tasks": [
            ("Dockerisation & environnements", "TECH", "HIGH", 16),
            ("Pipeline CI/CD", "TECH", "HIGH", 16),
            ("Déploiement production & monitoring", "TECH", "MEDIUM", 16),
        ],
    },
]

# Always-added governance lot
_GOVERNANCE_LOT = {
    "lot": {"name": "Gouvernance & Pilotage", "color": "#38BDF8", "base_hours": 60},
    "skills": ["Gestion de projet"],
    "tasks": [
        ("Cadrage & ateliers besoin", "SPIKE", "HIGH", 16),
        ("Suivi & reporting", "DOC", "MEDIUM", 12),
        ("Recette finale & go-live", "TEST", "HIGH", 16),
    ],
}

_SPRINT_THEMES = ["Fondations", "Socle", "Accélération", "Durcissement", "Mise en prod"]


def _select_lots(brief: str) -> list[dict[str, Any]]:
    """Phase 1: lexical analysis — scan brief for domain keywords."""
    brief_lower = brief.lower()
    selected = []
    for entry in _LOT_CATALOG:
        if any(kw in brief_lower for kw in entry["keywords"]):
            selected.append(entry)
    # If nothing matched, pick the 2 most common (backend + frontend)
    if not selected:
        selected = [_LOT_CATALOG[0], _LOT_CATALOG[1]]
    # Always add governance
    selected.append(_GOVERNANCE_LOT)
    return selected


def _complexity_factor(brief: str) -> float:
    """Phase 2: sizing — base effort multiplier based on brief length."""
    n = len(brief)
    if n < 200:
        return 0.7
    if n < 500:
        return 1.0
    if n < 1000:
        return 1.3
    return 1.6


def _build_sprints(total_hours: float, team_capacity_weekly: float) -> list[dict]:
    """Phase 4: sprint planning — 2-week sprints, capacity = weekly × 2."""
    if team_capacity_weekly <= 0:
        team_capacity_weekly = 70  # default 2 devs × 35h
    sprint_capacity = team_capacity_weekly * 2
    n_sprints = max(2, min(5, int(total_hours / sprint_capacity) + 1))
    sprints = []
    for i in range(n_sprints):
        theme = _SPRINT_THEMES[i] if i < len(_SPRINT_THEMES) else f"Suivi {i + 1}"
        sprints.append({
            "name": f"Sprint {i + 1} · {theme}",
            "goal": f"Livraisons du sprint {i + 1}",
            "capacity_hours": round(sprint_capacity, 1),
        })
    return sprints


def _assign_sprints(tasks: list[dict], sprints: list[dict]) -> list[dict]:
    """Phase 5: bin-packing — fill sprints sequentially up to capacity."""
    if not sprints:
        return tasks
    capacities = [s["capacity_hours"] for s in sprints]
    remaining = list(capacities)
    current = 0
    for task in tasks:
        # Find next sprint with capacity
        while current < len(sprints) and remaining[current] < task["estimate_hours"]:
            current += 1
        if current >= len(sprints):
            current = len(sprints) - 1  # overflow into last sprint
        task["sprint"] = sprints[current]["name"]
        remaining[current] -= task["estimate_hours"]
    return tasks


def generate_plan(
    brief: str,
    constraints: dict | None = None,
    team: list[dict] | None = None,
    methodology: str = "SCRUM",
) -> dict[str, Any]:
    """
    Deterministic plan generator — fallback when LLM is unavailable.

    Returns a dict matching the ScopingOutput schema (unvalidated — caller validates).
    """
    constraints = constraints or {}
    team = team or []
    weekly_capacity = sum(float(m.get("capacity_hours", 35)) for m in team) or 70

    # Phase 1 + 2: select lots + complexity
    lots_data = _select_lots(brief)
    complexity = _complexity_factor(brief)

    lots = []
    tasks = []
    task_counter = 1
    for entry in lots_data:
        lot_info = entry["lot"]
        lot_hours = round(lot_info["base_hours"] * complexity, 1)
        lot = {
            "name": lot_info["name"],
            "description": f"Lot {lot_info['name']} — décomposition en tâches.",
            "estimate_hours": lot_hours,
            "confidence": 0.78,
            "color": lot_info["color"],
            "order": len(lots) + 1,
        }
        lots.append(lot)

        # Generate tasks for this lot
        for title, ttype, priority, base_hours in entry["tasks"]:
            hours = round(base_hours * complexity, 1)
            sp = max(1, round(hours / 7))
            tasks.append({
                "ref": f"T-{task_counter:03d}",
                "lot": lot_info["name"],
                "title": title,
                "description": f"{title} dans le lot {lot_info['name']}.",
                "type": ttype,
                "priority": priority,
                "estimate_hours": hours,
                "story_points": sp,
                "skills": entry["skills"],
                "acceptance_criteria": [
                    f"Livrable validé par le chef de projet",
                    f"Tests passés (unitaires + intégration)" if ttype != "SPIKE" else f"Note de synthèse rédigée",
                    f"Documentation à jour",
                ],
                "risk_score": 30 if ttype == "TECH" else 20 if ttype == "FEATURE" else 15,
                "sprint": "",  # assigned in phase 5
            })
            task_counter += 1

    # Phase 4: sprints
    total_hours = round(sum(t["estimate_hours"] for t in tasks), 1)
    sprints = _build_sprints(total_hours, weekly_capacity)

    # Phase 5: bin-packing
    tasks = _assign_sprints(tasks, sprints)

    # Risks
    risks = [
        {"category": "DELAY", "title": "Dérive planning sur lots critiques", "score": 45},
        {"category": "SCOPE", "title": "Scope creep potentiel", "score": 35},
    ]
    if constraints.get("budget") and total_hours * 50 > float(constraints["budget"]):
        risks.append({"category": "BUDGET", "title": "Dépassement budget probable", "score": 65})
    if len(team) < 3:
        risks.append({"category": "LOAD", "title": "Surcharge équipe (effectif réduit)", "score": 55})

    return {
        "lots": lots,
        "tasks": tasks,
        "sprints": sprints,
        "risks": risks,
        "assumptions": [
            "Équipe complète et disponible sur toute la durée du projet",
            "Outils et accès environnement de dev prêts",
        ],
        "total_estimate_hours": total_hours,
        "confidence": 0.78,
        "_engine": "deterministic-fallback",
    }
