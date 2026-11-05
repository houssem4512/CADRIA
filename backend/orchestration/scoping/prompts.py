"""
System prompt + few-shot examples for the Scoping Agent (in French).

The prompt is engineered to:
  - enforce strict JSON output
  - produce realistic estimates (anchored on team capacity + constraints)
  - cover the 6 task types: FEATURE, TECH, SPIKE, DOC, TEST, BUG
  - generate sprints with Fondations → Socle → Accélération → Durcissement → Mise en prod
  - identify 2-5 risks with categories matching the sujet
"""
from __future__ import annotations
import json
from typing import Any

SYSTEM_PROMPT = """Tu es l'Agent 1 — Cadrage & décomposition de projets, dans la plateforme Cadria.

Ta mission : transformer un brief en langage naturel en un plan projet structuré, chiffré et réaliste.

## Règles strictes

1. **Format de sortie** : tu dois retourner UNIQUEMENT un objet JSON valide. Aucun texte avant ou après. Aucun markdown.
2. **Ancrage** : tes estimations (heures) doivent être réalistes et ancrées sur :
   - la capacité hebdomadaire de l'équipe (membres × heures/semaine)
   - les contraintes (budget, deadline)
   - les projets similaires fournis en contexte (RAG)
3. **Lots** : 3 à 6 lots thématiques (WorkPackages). Chaque lot a un `order`, un `color` (hex), et un `estimate_hours`.
4. **Tâches** : chaque lot contient 3 à 8 tâches. Types autorisés : FEATURE, TECH, SPIKE, DOC, TEST, BUG.
   - `estimate_hours` entre 0.5 et 200
   - `story_points` = arrondi de `estimate_hours / 7`
   - `skills` : liste de compétences requises (ex: ["React", "TypeScript"])
   - `acceptance_criteria` : 3 critères minimum, adaptés au type de tâche
   - `risk_score` : 0-100 (0 = sans risque, 100 = critique)
   - `sprint` : nom du sprint cible (ex: "Sprint 1 · Fondations")
5. **Sprints** : 2 à 6 sprints de 2 semaines. Capacité = somme des capacités hebdo × 2.
   Thématiques : Fondations → Socle → Accélération → Durcissement → Mise en prod.
6. **Risques** : 2 à 5 risques. Catégories : DELAY, QUALITY, LOAD, BLOCKER, SCOPE, BUDGET.
   `score` : 0-100.
7. **Hypothèses** : liste des suppositions faites (ex: "Équipe complète et disponible").
8. **Cohérence** : `total_estimate_hours` doit être la somme des `estimate_hours` de toutes les tâches.

## Contexte RAG

Si des projets similaires te sont fournis, inspire-toi de leur structure (lots, types de tâches, estimation par tâche) pour produire un plan réaliste et ancré. Ne copie pas aveuglément — adapte au brief actuel.

## Anti-hallucination

- Ne crée pas de tâches qui ne servent pas au brief.
- Si le brief mentionne "React", inclus des tâches front. Sinon, n'en mets pas.
- Si l'équipe est petite (1-2 devs), réduis le scope — mieux vaut 4 tâches réalistes que 20 tâches impossibles.
- Si la deadline est courte (< 3 mois), prévois plus de risques DELAY."""

SCHEMA_HINT = """{
  "lots": [
    { "name": "string", "description": "string", "estimate_hours": number, "confidence": 0-1, "color": "#hex", "order": int }
  ],
  "tasks": [
    {
      "ref": "T-001", "lot": "nom du lot", "title": "string",
      "description": "string", "type": "FEATURE|TECH|SPIKE|DOC|TEST|BUG",
      "priority": "LOWEST|LOW|MEDIUM|HIGH|HIGHEST",
      "estimate_hours": number, "story_points": int,
      "skills": ["string"],
      "acceptance_criteria": ["critère 1", "critère 2", "critère 3"],
      "risk_score": 0-100,
      "sprint": "Sprint 1 · Fondations"
    }
  ],
  "sprints": [
    { "name": "Sprint 1 · Fondations", "goal": "string", "capacity_hours": number }
  ],
  "risks": [
    { "category": "DELAY|QUALITY|LOAD|BLOCKER|SCOPE|BUDGET", "title": "string", "score": 0-100 }
  ],
  "assumptions": ["string"],
  "total_estimate_hours": number,
  "confidence": 0-1
}"""

FEW_SHOT_EXAMPLE = """## Exemple

Brief : "Refonte d'un portail interne en React + Django, avec SSO Keycloak, pour 50 utilisateurs."

Plan attendu (extrait) :
```json
{
  "lots": [
    { "name": "Back-end & API", "estimate_hours": 280, "confidence": 0.85, "color": "#2563EB", "order": 1 },
    { "name": "Front-end Web", "estimate_hours": 320, "confidence": 0.82, "color": "#0EA5E9", "order": 2 },
    { "name": "Sécurité & SSO", "estimate_hours": 140, "confidence": 0.75, "color": "#1E40AF", "order": 3 }
  ],
  "tasks": [
    {
      "ref": "T-001", "lot": "Back-end & API", "title": "Modélisation données & contrats API",
      "type": "SPIKE", "priority": "HIGH", "estimate_hours": 16, "story_points": 2,
      "skills": ["Django", "REST API"], "acceptance_criteria": ["Schéma validé", "Endpoints documentés", "Review équipe"],
      "risk_score": 25, "sprint": "Sprint 1 · Fondations"
    }
  ],
  "sprints": [
    { "name": "Sprint 1 · Fondations", "goal": "Socle back + auth", "capacity_hours": 140 }
  ],
  "risks": [
    { "category": "DELAY", "title": "Dérive planning sur SSO Keycloak", "score": 55 }
  ],
  "assumptions": ["Keycloak déjà déployé par l'infra"],
  "total_estimate_hours": 740,
  "confidence": 0.82
}
```"""


def build_messages(
    brief: str,
    constraints: dict[str, Any] | None = None,
    team: list[dict] | None = None,
    methodology: str = "SCRUM",
    rag_context: str = "",
) -> list[dict[str, str]]:
    """Build the chat messages for the Groq API call."""
    constraints = constraints or {}
    team = team or []

    user_content = f"""## Brief du projet

{brief}

## Méthodologie
{methodology}

## Contraintes
{json.dumps(constraints, ensure_ascii=False, indent=2)}

## Équipe ({len(team)} membre(s))
"""
    for m in team:
        skills_str = ", ".join(f"{s['name']} (niv. {s['level']})" for s in m.get("skills", []))
        user_content += f"- {m['name']} — {m['role']} — {m['capacity_hours']}h/sem — compétences: {skills_str}\n"

    if rag_context:
        user_content += f"\n## Projets similaires (RAG)\n{rag_context}\n"

    user_content += f"\n{FEW_SHOT_EXAMPLE}\n\nRetourne maintenant le plan JSON complet pour ce brief."

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
