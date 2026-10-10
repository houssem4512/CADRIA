# Contrat des agents & branchement du runtime

Ce document décrit la frontière entre la plateforme Cadria et le runtime d'agents
multi-agents. **Aucun agent n'est implémenté dans ce dépôt** : la plateforme définit
le contrat, orchestre, journalise et expose les résultats.

---

## État actuel

| Élément | État |
| ------- | ---- |
| Définitions d'agents (`AgentDefinition`) | ✅ En base, avec contrat d'entrée/sortie |
| Exécutions (`AgentRun`) | ✅ Créées, statuts, journalisation, audit |
| Propositions & validation humaine (`Proposal`) | ✅ Complètement fonctionnel |
| Suggestions d'assignation (`AssignmentSuggestion`) | ✅ Modèle + endpoints |
| **Inférence des agents** | ⛔ **Emplacement réservé** |
| **Écriture Jira/Trello** | ⛔ **Emplacement réservé** |

Quand un agent est lancé alors que le runtime n'est pas branché :

1. une `AgentRun` est créée avec le statut `SKIPPED` et l'étape
   *« En attente du runtime agent »* ;
2. `output_payload` contient `{ "_reserved": true, "_contract": <schéma attendu> }` ;
3. une entrée d'audit `AGENT_RUN` est écrite avec un `correlation_id` ;
4. une notification est envoyée à l'utilisateur ;
5. `AgentDefinition.total_runs` et `last_run_at` sont mis à jour.

**Rien n'est simulé** : aucun faux résultat, aucune tâche inventée.

---

## Les trois agents

### Agent 1 — Cadrage & décomposition (`SCOPING`)

Transforme une description en langage naturel en plan structuré.

- **Modèle suggéré** : Llama 3.2 (1B/3B), Phi-3.5-mini, Qwen2.5-3B — fine-tuning LoRA/QLoRA
- **Approche** : fine-tuning sur cahiers des charges → décompositions de tâches
- **RAG** : historique de projets passés pour ancrer les estimations
- **Validation humaine** : obligatoire

**Entrée**

```json
{
  "brief": "string — description libre du projet",
  "project_reference": "PRJ-0001",
  "methodology": "SCRUM",
  "constraints": { "budget": 320000, "deadline": "2026-06-30", "team_size": 6 },
  "team": [
    { "id": 3, "name": "Nour Chaabane", "role": "MEMBER",
      "capacity_hours": 35.0,
      "skills": [{ "name": "React", "level": 4 }] }
  ]
}
```

**Sortie attendue**

```json
{
  "lots": [
    { "name": "Refonte front-end", "description": "…",
      "estimate_hours": 420, "confidence": 0.82, "color": "#0EA5E9", "order": 1 }
  ],
  "tasks": [
    { "ref": "T-001", "lot": "Refonte front-end", "title": "Écran tableau de bord",
      "description": "…", "type": "FEATURE", "priority": "HIGHEST",
      "estimate_hours": 56, "story_points": 7,
      "skills": ["React", "TypeScript"],
      "acceptance_criteria": ["…"], "risk_score": 42, "sprint": "Sprint 2 · Socle" }
  ],
  "sprints": [
    { "name": "Sprint 1 · Fondations", "goal": "…", "capacity_hours": 210 }
  ],
  "risks": [
    { "category": "DELAY", "title": "Risque de dérive planning", "score": 58 }
  ],
  "assumptions": ["Équipe complète et disponible sur toute la durée"],
  "total_estimate_hours": 1320,
  "confidence": 0.86
}
```

`type` ∈ `FEATURE | BUG | TECH | SPIKE | DOC | TEST`
`priority` ∈ `LOWEST | LOW | MEDIUM | HIGH | HIGHEST`

### Agent 2 — Intégration Jira/Trello & assignation (`OPS`)

Traduit le JSON de l'Agent 1 en appels API et réalise la première assignation.

- **Modèle suggéré** : SLM tool-calling · LangGraph/CrewAI + `all-MiniLM-L6-v2`
- **Approche** : agent à function calling, exécutable en CPU
- **Validation humaine** : obligatoire

**Entrée**

```json
{
  "proposal_id": 12,
  "project_reference": "PRJ-0001",
  "provider": "JIRA",
  "dry_run": true,
  "sprints": [ … ],
  "tasks": [ … ],
  "assignments": [ { "task_ref": "T-001", "user_id": 3, "score": 0.91 } ]
}
```

**Sortie attendue**

```json
{
  "created": [
    { "external_id": "CAD-142", "external_url": "https://…", "entity": "issue" }
  ],
  "assignments": [ { "task_ref": "T-001", "user_id": 3, "applied": true } ],
  "api_calls": 27,
  "errors": []
}
```

**Contraintes** : idempotence des appels (éviter la duplication de tickets),
gestion du rate limiting, traçabilité de chaque écriture dans `AuditLog` avec
`action="AGENT_WRITE"` et `agent_key="OPS"`.

### Agent 3 — Analyse & suivi des risques (`RISK`)

Surveille en continu la santé du projet.

- **Modèle suggéré** : XGBoost/LightGBM (tabulaire) + DistilBERT/CamemBERT (NLP)
- **Approche** : entraînable en CPU local
- **Validation humaine** : non requise (lecture seule, produit des alertes)

**Entrée**

```json
{
  "project_reference": "PRJ-0001",
  "window_days": 30,
  "provider": "JIRA",
  "tasks": [
    { "id": 1, "title": "…", "status": "IN_PROGRESS",
      "estimate_hours": 56.0, "spent_hours": 41.0,
      "blocked": false, "due_date": "2026-05-12" }
  ],
  "comments": [ { "id": 7, "body": "Je suis bloqué en attente de…", "created_at": "…" } ]
}
```

**Sortie attendue**

```json
{
  "risk_score": 62,
  "alerts": [
    { "category": "DELAY", "severity": "CRITICAL", "title": "Dérive du lot « API publique »",
      "message": "…", "score": 78,
      "factors": [ { "label": "Écart estimé / réalisé", "weight": 0.42 } ],
      "recommendation": "Ré-estimer le reste à faire…" }
  ],
  "factors": ["Vélocité en baisse", "3 tâches bloquées"]
}
```

`category` ∈ `DELAY | QUALITY | LOAD | BLOCKER | SCOPE | BUDGET`
`severity` ∈ `INFO | WARNING | CRITICAL`

---

## Procédure de branchement

### 1. Implémenter `dispatch()`

`backend/orchestration/services.py` contient la fonction à remplir :

```python
def dispatch(run) -> AgentDispatchResult:
    """
    Envoie une exécution au runtime de l'agent et met à jour `run`.
    """
    raise NotImplementedError(...)
```

Le runtime doit :

1. lire `run.agent.key` et `run.input_payload` ;
2. appeler le service d'inférence (HTTP, file Celery, ou exécution locale) ;
3. mettre à jour `run` :

```python
run.status = AgentRun.Status.SUCCEEDED          # ou FAILED / AWAITING_VALIDATION
run.step = "Découpage terminé"
run.output_payload = {...}                      # conforme au schéma de sortie
run.tokens_in, run.tokens_out = 1200, 3400
run.latency_ms = 1840
run.started_at = started
run.finished_at = timezone.now()
run.save()
```

4. pour l'Agent 1, créer une `Proposal` liée (`Proposal.objects.create(run=run, …)`)
   au statut `PENDING` — elle apparaîtra dans l'onglet **Validation** ;
5. pour l'Agent 3, créer des `RiskAlert` et des `Notification` ;
6. écrire une entrée d'audit avec `agent_key` et `correlation_id`.

Des helpers sont déjà fournis :

```python
from orchestration.services import (
    build_scoping_payload, build_ops_payload, build_risk_payload,
)
```

### 2. Renseigner les endpoints

```python
AgentDefinition.objects.filter(key="SCOPING").update(
    runtime_endpoint="https://agents.local/scoping",
    state=AgentDefinition.State.BETA,
)
```

États disponibles : `RESERVED` (défaut) · `BETA` · `ENABLED` · `DISABLED`.
`is_available` est vrai pour `ENABLED` et `BETA`.

### 3. Activer le runtime

```bash
export AGENT_RUNTIME_ENABLED=True
export SCOPING_AGENT_URL=https://agents.local/scoping
export OPS_AGENT_URL=https://agents.local/ops
export RISK_AGENT_URL=https://agents.local/risk
export ORCHESTRATOR=LangGraph
```

Dès que `AGENT_RUNTIME_ENABLED=True` **et** que l'agent est disponible,
`POST /api/agents/runs/start/` appelle `dispatch()` au lieu de créer une exécution
réservée. Si `dispatch()` lève `NotImplementedError`, l'exécution retombe proprement
en `SKIPPED` avec le message d'erreur.

---

## Validation humaine — invariant

Quel que soit le runtime, **aucune écriture dans Jira ou Trello ne peut se faire
sans une validation explicite** via `POST /api/proposals/{id}/validate/` :

- l'endpoint matérialise les tâches dans Cadria ;
- applique les assignations que le chef de projet a acceptées ;
- si `push_to_external: true`, **journalise l'intention** (`AGENT_WRITE`) —
  l'appel effectif à l'API externe reste à implémenter dans l'Agent 2 ;
- écrit une notification et une entrée d'audit `VALIDATE` ou `REJECT`.

---

## Observabilité attendue

Le tableau de bord de supervision (`/api/agents/monitor/`) agrège déjà :

| Métrique | Source | Cible |
| -------- | ------ | ----- |
| Latence moyenne | `AgentRun.latency_ms` | < 3 000 ms |
| Taux d'erreur JSON | `FAILED / total` | < 2 % |
| Taux de succès | `SUCCEEDED / total` | > 95 % |
| Exécutions en attente de validation | `AWAITING_VALIDATION` | à traiter |

Côté `/api/analytics/insights/` :

- **Qualité de génération** : écart moyen estimé/réalisé sur les tâches créées par
  agent, taux d'acceptation des plans ;
- **Qualité d'assignation** : indice d'équilibrage de charge (Gini simplifié),
  utilisation moyenne, membres en surcharge, taux de suggestions acceptées ;
- **Qualité de prédiction** : alertes émises vs. traitées, risque moyen,
  projets en retard, signaux faibles détectés dans les commentaires.

---

## Pipeline & outillage (hors périmètre de ce dépôt)

- **Airflow** : ré-entraînement mensuel du modèle de génération (Agent 1) +
  collecte hebdomadaire Jira/Trello pour le modèle de risque (Agent 3).
- **Grafana** : latence, taux d'erreur de format JSON, taux de succès des appels API,
  équilibrage de charge, scores de risque avec alertes.
- **EvidentlyAI** : complété par des métriques custom (complétude, équilibrage,
  risque prédit vs. constaté).
