# Architecture technique — Cadria

## Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend React 19 (Vite)                                        │
│  React Router · Tailwind CSS · Recharts · lucide-react           │
│  src/context/{Auth,Notification}Context.jsx  (providers globaux) │
└───────────────────────────┬──────────────────────────────────────┘
                            │  /api  (proxy Vite → :8000)
┌───────────────────────────▼──────────────────────────────────────┐
│  API Django 5 + DRF + SimpleJWT                                  │
│  accounts · projects · orchestration · notifications             │
│  analytics · audit                                               │
└───────────────────────────┬──────────────────────────────────────┘
                            │
              ┌─────────────▼─────────────┐
              │  SQLite (démo)            │
              │  PostgreSQL (production)  │
              └─────────────┬─────────────┘
                            │
              ┌─────────────▼─────────────┐
              │  Runtime multi-agents     │  ⚠️ emplacement réservé
              │  dispatch() à implémenter │
              └───────────────────────────┘
```

---

## Modèle de données

### `accounts`

| Modèle | Rôle |
| ------ | ---- |
| `User` | Utilisateur personnalisé. Login par **e-mail** (`username=None`). Champs : `role`, `status`, `job_title`, `company`, `avatar_color`, `weekly_capacity_hours`, `hourly_cost`, 6 flags de notification, `last_seen_at`. |
| `Skill` | Référentiel de compétences, catégorisé (`TECH`, `DATA`, `DESIGN`, `FUNC`, `MGMT`). |
| `UserSkill` | Liaison utilisateur ↔ compétence avec `level` 1–5. Alimente le matching de l'Agent 2. |
| `Team` | Équipe : nom, couleur, propriétaire, membres (M2M). |
| `PasswordResetCode` | Code à 6 chiffres, expiration 15 min, usage unique. |

**Rôles** : `ADMIN` · `PM` · `MEMBER` · `VIEWER`
**Statuts** : `ACTIVE` · `PENDING` · `SUSPENDED`

Propriétés calculées : `full_name`, `initials`, `is_admin`, `is_pm`.

### `projects`

| Modèle | Rôle |
| ------ | ---- |
| `Project` | Projet. `reference` (`PRJ-0001`) et `slug` générés automatiquement dans `save()`. |
| `WorkPackage` | Lot de travail issu du découpage (ordre, couleur, effort, confiance). |
| `Sprint` | Sprint : objectif, points engagés/livrés, capacité, score de risque. |
| `Task` | Tâche : type, priorité, statut, assigné, estimateur/réalisé, compétences requises, critères d'acceptation, score et facteurs de risque. |
| `RiskAlert` | Alerte produite par l'Agent 3, avec facteurs contributeurs et recommandation. |
| `Integration` | Configuration Jira / Trello / GitHub. |
| `Comment` | Commentaire, avec `weak_signal` et `sentiment` détectés automatiquement. |

**Statuts de tâche** : `TODO` · `IN_PROGRESS` · `REVIEW` · `BLOCKED` · `DONE`

Propriétés dérivées (utilisées par les dashboards) :
`Project.total_tasks`, `done_tasks`, `overdue_tasks`, `blocked_tasks`, `is_late`,
`budget_consumed` ; `Task.cost`, `effort_variance`, `is_overdue`.

`Task.save()` maintient `completed_at` : horodaté au passage en `DONE`, remis à
`None` si la tâche repart en arrière.

### `orchestration`

| Modèle | Rôle |
| ------ | ---- |
| `AgentDefinition` | Fiche d'agent : description, modèle et stack suggérés, capacités, **schémas d'entrée/sortie**, endpoint, compteurs d'observabilité. |
| `AgentRun` | Une exécution : statut, étape, progression, payloads d'entrée/sortie, tokens, latence, lien vers l'exécution parente. |
| `Proposal` | Plan proposé par l'Agent 1 : lots, tâches, sprints, risques, hypothèses, effort total, confiance, validation. |
| `AssignmentSuggestion` | Suggestion d'assignation : score de matching, justification, charge avant/après, décision. |

**Statuts d'exécution** : `QUEUED` · `RUNNING` · `AWAITING_VALIDATION` ·
`SUCCEEDED` · `FAILED` · `CANCELLED` · `SKIPPED` (réservé)
**Statuts de proposition** : `DRAFT` · `PENDING` · `APPROVED` · `REJECTED` · `APPLIED`

### `notifications`

| Modèle | Rôle |
| ------ | ---- |
| `Notification` | Notification personnelle (`user`) **ou** diffusion (`is_broadcast=True`, `user=None`, `target_role`). |
| `NotificationRead` | État de lecture individuel des diffusions (unique par notification × utilisateur). |
| `NotificationPreference` | Canaux (in-app, e-mail, Slack) et fréquence de synthèse. |

**Niveaux** : `INFO` · `SUCCESS` · `WARNING` · `ERROR` · `AGENT`
**Catégories** : `SYSTEM` · `AGENT` · `RISK` · `TASK` · `TEAM` · `VALIDATION` · `ACCOUNT` · `INTEGRATION`

### `audit`

`AuditLog` : acteur (utilisateur ou libellé système), action, sévérité, entité,
description, `changes` (diff), `metadata`, `agent_key`, `run`, `correlation_id`, IP.

C'est le modèle qui rend possible la traçabilité multi-agents : chaque exécution
porte un `correlation_id` propagé jusqu'aux écritures qu'elle déclenche.

---

## Décisions techniques

### 1. Pourquoi les agents sont des « emplacements réservés »

Le cahier des charges demande une architecture multi-agents avec modèles fine-tunés,
RAG et intégrations Jira/Trello. Implémenter une **fausse** génération de plan
aurait produit une démo trompeuse : des tâches inventées, des scores de risque
fabriqués, des assignations arbitraires.

La plateforme définit donc le **contrat** (schémas d'entrée/sortie stockés en base,
visibles dans l'UI), orchestre réellement (création d'exécutions, statuts,
journalisation, audit, notifications), et matérialise réellement les plans une fois
validés — mais ne simule aucune inférence. Brancher un agent revient à remplir une
seule fonction.

### 2. Login par e-mail plutôt que par nom d'utilisateur

Le `UserManager` personnalisé normalise l'e-mail en minuscules et l'utilise comme
identifiant unique (`USERNAME_FIELD = "email"`, `username = None`). Cela évite les
doublons `User@x.com` / `user@x.com` et simplifie l'administration.

### 3. Visibilité des projets

`_visible_projects(user)` filtre systématiquement sur
`owner=user OR members__contains=user`, sauf pour `ADMIN` et les superusers.
Un projet hors périmètre renvoie `404`, pas `403` — on ne révèle pas son existence.

### 4. Diffusions globales sans duplication

Une annonce admin est **une seule ligne** (`user=None`, `is_broadcast=True`) plutôt
qu'une ligne par destinataire. Le ciblage se fait par `target_role`, et l'état de
lecture est individuel via `NotificationRead`. Créer un compte ne duplique donc
rien, et une annonce touche automatiquement les nouveaux inscrits.

### 5. Routes littérales avant le routeur DRF

`DefaultRouter` génère `agents/<pk>/`, qui capture `agents/monitor/` si la route
littérale est déclarée après. Dans `orchestration/urls.py`, `notifications/urls.py`
et `audit/urls.py`, les routes littérales sont donc placées **avant** `router.urls`.

### 6. `Project.save()` : référence en deux passes

`reference` dépend de la clé primaire, donc le premier `save()` insère la ligne,
puis un second `save(update_fields=["reference"])` écrit `PRJ-0001`. Le `slug` est
dédupliqué avec un suffixe numérique en cas de collision.

### 7. Agrégation à la demande plutôt que champs dénormalisés

`POST /projects/{id}/recompute/` recalcule progression, charge, score de risque et
santé depuis les tâches et alertes réelles. Les champs stockés (`progress`,
`risk_score`, `health`) servent de cache pour les listes ; le recalcul explicite
garantit la cohérence sans déclencheurs en base.

---

## Frontend

### Organisation

```
src/
├── main.jsx                    # Providers : Router → Auth → Notification
├── App.jsx                     # Routes + lazy loading + gardes d'accès
├── lib/
│   ├── api.js                  # Instance axios, refresh JWT, cache, erreurs
│   ├── useApi.js               # useQuery, usePaged, useMutation, useDebounced
│   └── format.js               # Formateurs FR + dictionnaires de statuts/couleurs
├── context/
│   ├── AuthContext.jsx         # user, login, register, logout, isAdmin
│   └── NotificationContext.jsx # polling 45 s, badge, toasts
├── components/
│   ├── ui.jsx                  # Card, Badge, Button, Modal, Tabs, Table, …
│   ├── charts/index.jsx        # Wrappers Recharts (trend, bar, donut, radar)
│   ├── layout/AppLayout.jsx    # Sidebar, header, cloche, palette ⌘K
│   ├── Toast.jsx               # Pile de notifications flottantes
│   └── Logo.jsx                # Logo SVG (dégradé bleu, nœuds d'orchestration)
└── pages/
    ├── Home.jsx                # Site public
    ├── auth/{Login,Signup}.jsx
    ├── app/                    # Espace client (10 pages)
    └── admin/                  # Espace admin (7 pages)
```

### Rafraîchissement du JWT

`api.js` intercepte les `401`, appelle `/auth/refresh/` **une seule fois** même si
plusieurs requêtes échouent simultanément (promesse partagée), rejoue la requête
initiale, et émet `cadria:session-expired` si le refresh échoue — `AuthContext`
redirige alors vers `/login?expired=1`.

### Lazy loading

Chaque page est un `lazy()` distinct : le chunk `ProjectDetail` (65 ko) n'est chargé
que sur la page projet, `charts` (430 ko) seulement quand un graphique s'affiche.

### Garde d'accès

`RequireAuth` redirige vers `/login?next=…` ; `RequireAdmin` vérifie
`role === 'ADMIN' || is_superuser` et redirige sinon vers `/app`.

---

## Sécurité

| Mesure | Implémentation |
| ------ | -------------- |
| Mots de passe | Validateurs Django (longueur, complexité, similarité) |
| Rôle admin | Non attribuable à l'inscription (`RegisterSerializer.validate_role`) |
| Suspension | `is_active=False` + `status=SUSPENDED` bloque la connexion |
| Autorisations | `IsAdminRole` sur `/users/`, vérification dans les vues analytics et broadcast |
| Cloisonnement | Filtrage du queryset projet, `404` hors périmètre |
| Jetons | Access 8 h, refresh 7 j avec rotation et blacklist |
| Audit | Toute action sensible écrit une `AuditLog` (création, modification, suppression, permission, validation, agent) |
| CORS | `CORS_ALLOW_ALL_ORIGINS` en démo — à restreindre en production |

### À durcir avant mise en production

- `DEBUG=False`, `SECRET_KEY` via variable d'environnement, `ALLOWED_HOSTS` explicite
- `CORS_ALLOWED_ORIGINS` restreint aux domaines réels
- PostgreSQL avec sauvegardes
- HTTPS obligatoire, `SECURE_HSTS_SECONDS`, cookies `Secure`/`HttpOnly`
- Rate limiting sur `/auth/login/` et `/auth/password/reset/`
- Envoi réel des e-mails de réinitialisation (SMTP) — aujourd'hui le code est renvoyé dans la réponse

---

## Tests

```bash
cd backend && python3 manage.py test --parallel 1
```

58 tests d'intégration répartis en 8 classes :

| Classe | Couverture |
| ------ | ---------- |
| `AuthTests` | login, refresh, register (dont refus admin/doublon), reset par code |
| `PermissionsTests` | CRUD comptes admin-only, suspension, actions groupées, broadcast |
| `ProjectTests` | référence/slug, création détaillée, cloisonnement, recompute, kanban, move, variance, workload, signaux faibles |
| `AgentTests` | exécution réservée, agents/projets inconnus, monitor, validation approve/reject, matérialisation des tâches |
| `NotificationTests` | summary, mark read/all, star, archive, diffusions par rôle, lecture individuelle, préférences |
| `TeamTests` | création d'équipe, annuaire, compétences |
| `AuditTests` | cloisonnement non-admin, filtres, summary |
| `AnalyticsTests` | dashboards client/admin, insights qualité |

Les tests exercent les vraies vues via `APIClient` — aucune logique n'est
réimplémentée dans le jeu de tests.
