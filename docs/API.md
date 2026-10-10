# Référence API — Cadria

Base URL de développement : `http://localhost:8000/api/`
(préfixée par `/api` côté front via le proxy Vite).

Toutes les réponses sont en JSON. L'authentification se fait par jeton JWT :

```
Authorization: Bearer <access_token>
```

## Authentification

| Méthode | Endpoint | Accès | Description |
| ------- | -------- | ----- | ----------- |
| `POST` | `/auth/register/` | Public | Création de compte. Le rôle `ADMIN` est refusé. |
| `POST` | `/auth/login/` | Public | Connexion → `{ user, access, refresh }` |
| `POST` | `/auth/logout/` | Authentifié | Révocation du refresh token |
| `POST` | `/auth/refresh/` | Public | `{ refresh }` → `{ access, refresh }` |
| `POST` | `/auth/password/change/` | Authentifié | `{ old_password, new_password }` |
| `POST` | `/auth/password/reset/` | Public | Demande de code (6 chiffres, 15 min) |
| `POST` | `/auth/password/reset/confirm/` | Public | `{ email, code, new_password }` |

> En démonstration, aucun serveur SMTP n'est configuré : le code est renvoyé dans la
> réponse sous la clé `demo_code`.

**Exemple — connexion**

```http
POST /api/auth/login/
Content-Type: application/json

{ "email": "pm@cadria.io", "password": "Cadria@2026" }
```

```json
{
  "user": { "id": 2, "email": "pm@cadria.io", "role": "PM", "full_name": "Yassine Trabelsi" },
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi..."
}
```

Durée de vie : access **8 h**, refresh **7 jours** (rotation activée).

---

## Utilisateur courant

| Méthode | Endpoint | Description |
| ------- | -------- | ----------- |
| `GET` | `/me/` | Profil complet (compétences, préférences, charge) |
| `PATCH` | `/me/` | Mise à jour du profil |
| `GET` | `/me/skills/` | Liste des compétences |
| `PUT` | `/me/skills/` | Remplacement de la liste : `[{"skill": 3, "level": 4}]` |
| `GET` | `/members/` | Annuaire des membres actifs (paginé) |

---

## Projets

| Méthode | Endpoint | Description |
| ------- | -------- | ----------- |
| `GET` | `/projects/` | Liste paginée. Filtres : `status`, `health`, `mine`, `search`, `ordering` |
| `POST` | `/projects/` | Création → renvoie la représentation **détaillée** (référence incluse) |
| `GET` | `/projects/{id}/` | Détail : lots, sprints, tâches, risques, membres, commentaires, exécutions |
| `PATCH`/`PUT` | `/projects/{id}/` | Modification |
| `DELETE` | `/projects/{id}/` | Suppression (cascade sur lots, sprints, tâches) |
| `GET` | `/projects/{id}/board/` | Kanban : tâches groupées par statut |
| `GET` | `/projects/{id}/workload/` | Charge par membre (utilisé par l'Agent 2) |
| `POST` | `/projects/{id}/recompute/` | Recalcul progression, charge, score de risque, santé |
| `POST` | `/projects/{id}/sync/` | Demande de synchronisation Jira/Trello (Agent 2) |

**Visibilité** : un utilisateur ne voit que les projets dont il est propriétaire ou
membre. Les rôles `ADMIN` et les superusers voient tout.

**Exemple — création**

```http
POST /api/projects/
{
  "name": "Refonte du portail client",
  "summary": "Nouveau portail self-service",
  "brief": "Description en langage naturel du projet…",
  "methodology": "SCRUM",
  "start_date": "2026-01-05",
  "target_end_date": "2026-06-30",
  "budget": 320000,
  "member_ids": [3, 4, 5],
  "tags": ["front", "api"]
}
```

Réponse `201` :

```json
{
  "id": 5, "reference": "PRJ-0005", "slug": "refonte-du-portail-client",
  "status": "DRAFT", "health": "GREEN", "progress": 0, "risk_score": "0.00",
  "work_packages": [], "sprints": [], "recent_tasks": [], "risk_alerts": [],
  "health_indicators": { "overdue_tasks": 0, "blocked_tasks": 0, "effort_variance_pct": 0.0 }
}
```

---

## Tâches, lots, sprints

| Méthode | Endpoint | Description |
| ------- | -------- | ----------- |
| `GET` | `/tasks/` | Filtres : `project`, `assignee`, `mine`, `status`, `sprint`, `at_risk`, `search` |
| `POST` | `/tasks/` | Création (notification envoyée à l'assigné) |
| `PATCH` | `/tasks/{id}/` | Modification (journalisée si changement de statut) |
| `POST` | `/tasks/{id}/move/` | Déplacement kanban : `{ "status": "IN_PROGRESS" }` |
| `POST` | `/tasks/bulk_status/` | `{ "ids": [1,2], "status": "DONE" }` |
| `CRUD` | `/work-packages/` | Lots de travail (filtre `project`) |
| `CRUD` | `/sprints/` | Sprints (filtre `project`) |

Statuts : `TODO` · `IN_PROGRESS` · `REVIEW` · `BLOCKED` · `DONE`
Priorités : `LOWEST` · `LOW` · `MEDIUM` · `HIGH` · `HIGHEST`

---

## Risques & commentaires

| Méthode | Endpoint | Description |
| ------- | -------- | ----------- |
| `GET` | `/risks/` | Filtres : `project`, `severity`, `open` |
| `POST` | `/risks/{id}/acknowledge/` | Accusé de réception d'une alerte |
| `CRUD` | `/comments/` | Commentaires (détection automatique de signaux faibles) |

Les mots « bloqué », « en attente », « régression », « impossible », « depend »
positionnent `weak_signal: true` et `sentiment: "NEGATIVE"` — ce sont les signaux
faibles que l'Agent 3 exploitera.

---

## Agents & orchestration

| Méthode | Endpoint | Description |
| ------- | -------- | ----------- |
| `GET` | `/agents/` | Définitions des 3 agents (contrat, capacités, statistiques) |
| `POST` | `/agents/runs/start/` | Déclencher un agent |
| `GET` | `/agents/monitor/` | Supervision : totaux, par agent, série temporelle |
| `GET` | `/agent-runs/` | Journal des exécutions (filtres `project`, `agent`, `status`) |
| `GET` | `/proposals/` | Propositions (filtres `project`, `status`, `pending=true`) |
| `POST` | `/proposals/{id}/validate/` | **Validation humaine** |
| `GET` | `/assignments/` | Suggestions d'assignation (filtre `proposal`) |
| `POST` | `/assignments/{id}/decide/` | `{ "accepted": true }` |

**Déclencher un agent**

```http
POST /api/agents/runs/start/
{ "project": 1, "agent": "SCOPING", "input": { "brief": "…" } }
```

Tant que le runtime n'est pas branché, la réponse est `202` avec :

```json
{
  "detail": "« Agent 1 — Cadrage & décomposition » est un emplacement réservé…",
  "run": { "id": 41, "status": "SKIPPED", "step": "En attente du runtime agent" },
  "reserved": true
}
```

L'exécution est journalisée dans `/api/audit/` avec `action: "AGENT_RUN"` et un
`correlation_id`, et une notification est créée pour l'utilisateur.

**Validation humaine**

```http
POST /api/proposals/12/validate/
{
  "decision": "APPROVE",
  "create_tasks": true,
  "push_to_external": false,
  "assignments": { "34": true, "35": false },
  "reason": ""
}
```

- `APPROVE` → crée les tâches dans Cadria, applique les assignations acceptées,
  passe la proposition en `APPROVED`, journalise (et journalise l'intention de
  poussée externe si `push_to_external: true`).
- `REJECT` → enregistre `rejection_reason`, ne crée rien.

---

## Notifications

| Méthode | Endpoint | Description |
| ------- | -------- | ----------- |
| `GET` | `/notifications/` | Filtres : `category`, `level`, `unread`, `archived`, `search` |
| `GET` | `/notifications/summary/` | Compteurs par niveau et catégorie |
| `POST` | `/notifications/{id}/mark_read/` | Marquer comme lu |
| `POST` | `/notifications/{id}/mark_unread/` | Marquer comme non lu |
| `POST` | `/notifications/mark_all_read/` | Tout marquer comme lu |
| `POST` | `/notifications/{id}/toggle_star/` | Suivre / ne plus suivre |
| `POST` | `/notifications/{id}/archive/` | Archiver / restaurer |
| `DELETE` | `/notifications/{id}/` | Supprimer |
| `POST` | `/notifications/broadcast/` | **Admin** — diffusion ciblée |
| `GET`/`PATCH` | `/notifications/preferences/` | Canaux et fréquence de synthèse |

**Diffusion**

```http
POST /api/notifications/broadcast/
{
  "title": "Maintenance planifiée",
  "message": "Indisponibilité samedi 02h-04h.",
  "level": "WARNING",
  "category": "SYSTEM",
  "target_role": "ALL",
  "targets": [],
  "link": "/app/dashboard"
}
```

`target_role` ∈ `ALL` · `ADMIN` · `PM` · `MEMBER` · `VIEWER`.
Si `targets` est non vide, la sélection nominative prime sur le rôle.

Les diffusions ont `user: null` et `is_broadcast: true` ; l'état de lecture est
individuel (table `NotificationRead`), donc un utilisateur peut la marquer comme lue
sans affecter les autres.

---

## Équipes & compétences

| Méthode | Endpoint | Description |
| ------- | -------- | ----------- |
| `CRUD` | `/teams/` | Équipes (membres, couleur, propriétaire) |
| `CRUD` | `/skills/` | Référentiel de compétences (écriture réservée aux admins) |

---

## Administration

Toutes ces routes exigent le rôle `ADMIN` (ou superuser).

| Méthode | Endpoint | Description |
| ------- | -------- | ----------- |
| `GET` | `/users/` | Comptes. Filtres : `role`, `status`, `active`, `search` |
| `POST` | `/users/` | Création (mot de passe optionnel, défaut `Cadria@2026`) |
| `GET` | `/users/{id}/` | Détail complet |
| `PATCH` | `/users/{id}/` | Modification |
| `DELETE` | `/users/{id}/` | Suppression |
| `POST` | `/users/{id}/toggle_active/` | Activer / suspendre |
| `POST` | `/users/{id}/reset_password/` | Réinitialisation (renvoie le nouveau mot de passe) |
| `POST` | `/users/bulk_action/` | `{ ids, action }` — `activate` · `suspend` · `delete` · `role` |
| `GET` | `/analytics/admin/` | KPI, croissance, répartitions, activité |
| `GET` | `/analytics/insights/` | Qualité de génération / assignation / prédiction |

---

## Journal d'audit

| Méthode | Endpoint | Description |
| ------- | -------- | ----------- |
| `GET` | `/audit/` | Entrées. Filtres : `action`, `severity`, `entity_type`, `entity_id`, `agent`, `actor`, `days`, `search`, `scope=all` |
| `GET` | `/audit/summary/` | Agrégats par action, sévérité, agent + série temporelle |

Un utilisateur non administrateur ne voit que ses propres actions, sauf s'il passe
`scope=all` — dans ce cas le backend restreint quand même au périmètre autorisé.

Chaque entrée porte : acteur, action, sévérité, entité, description, `changes` (diff),
`metadata`, `agent_key`, `run` (exécution liée), `correlation_id`, IP.

---

## Pagination

Réponses paginées (DRF `PageNumberPagination`, 25 par défaut) :

```json
{ "count": 142, "next": "…?page=2", "previous": null, "results": [ … ] }
```

Passer `?page_size=100` pour augmenter la taille de page.

## Codes d'erreur

| Code | Signification |
| ---- | ------------- |
| `400` | Validation (les champs fautifs sont renvoyés en clés de l'objet) |
| `401` | Non authentifié ou jeton expiré |
| `403` | Rôle insuffisant |
| `404` | Ressource inexistante **ou hors périmètre de visibilité** |
| `202` | Lancement d'agent accepté (exécution réservée) |
