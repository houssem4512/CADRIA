# Cadria

**Copilote de cadrage, de découpage et de pilotage de projets** — plateforme web
multi-agents avec validation humaine obligatoire avant toute écriture externe.

Un chef de projet saisit une description en langage naturel ; le système propose une
architecture, découpe le travail en lots et tâches, estime l'effort, identifie les risques,
crée les sprints et tickets dans Jira/Trello, puis surveille en continu la santé du projet.

> **React 19 + Vite + Tailwind** · **Django 5 + DRF + JWT** · architecture multi-agents

---

## 📂 Structure du projet

```
cadria/
├── backend/                    # API Django REST
│   ├── accounts/               # Comptes, rôles, équipes, compétences, auth JWT
│   ├── projects/               # Projets, lots, sprints, tâches, risques, commentaires
│   ├── orchestration/          # Agents, exécutions, propositions, assignations
│   │   └── services.py         # ⚠️ Contrat du runtime — à implémenter
│   ├── notifications/          # Notifications in-app, diffusions, préférences
│   ├── analytics/              # Dashboards client & admin, insights qualité
│   ├── audit/                  # Journal d'audit & traçabilité multi-agents
│   ├── config/                 # settings, urls, wsgi/asgi
│   └── manage.py
├── frontend/                   # Application React
│   └── src/
│       ├── components/         # Bibliothèque UI, layout, charts, toasts
│       ├── context/            # Auth + Notifications (providers globaux)
│       ├── lib/                # Client API, hooks, formateurs
│       └── pages/              # home, auth, app/*, admin/*
└── docs/                       # Documentation technique
```

---

## 🚀 Démarrage rapide

### Prérequis

- Python 3.11+
- Node.js 20+

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 manage.py migrate
python3 manage.py seed_demo          # jeu de données de démonstration
python3 manage.py runserver 0.0.0.0:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

Le serveur Vite proxifie `/api`, `/admin`, `/static` et `/media` vers
`http://127.0.0.1:8000` (voir `vite.config.js`, variable `VITE_API_URL`).

### Comptes de démonstration

| Compte              | Rôle             | Accès                                          |
| ------------------- | ---------------- | ---------------------------------------------- |
| `admin@cadria.io`   | Administrateur   | Espace admin + espace projet                   |
| `pm@cadria.io`      | Chef de projet   | Espace projet                                  |
| `member@cadria.io`  | Membre d'équipe  | Espace projet (mes tâches)                     |

**Mot de passe commun :** `Cadria@2026`

---

## 🧭 Les deux espaces

### Espace client (chef de projet)

| Page                | Rôle |
| ------------------- | ---- |
| **Tableau de bord** | KPI, vélocité, répartition des tâches, risques par nature, charge d'équipe, échéances, activité |
| **Projets**         | Portefeuille en cartes ou tableau, filtres santé/statut, export CSV |
| **Projet (détail)** | 9 onglets : vue d'ensemble, tâches & lots, kanban, équipe & charge, copilote, validation, risques, connecteurs, activité |
| **Mes tâches**      | Tâches assignées, filtres priorité/statut/risque, export CSV |
| **Copilote & agents** | Cartes agents, contrat d'interface, lancement d'exécution, journal |
| **Équipes**         | Équipes, membres, compétences, utilisation de capacité |
| **Notifications**   | Centre unifié, filtres, suivi, archivage, préférences |
| **Historique**      | Journal d'audit personnel, détail des entrées |
| **Profil**          | Identité, compétences, capacité, notifications, mot de passe |

### Espace administration

| Page                     | Rôle |
| ------------------------ | ---- |
| **Vue d'ensemble**       | Santé plateforme, croissance, répartition rôles/statuts, insights qualité |
| **Comptes**              | CRUD complet, rôles, suspension, reset mot de passe, actions groupées, export |
| **Projets**              | Supervision du portefeuille, budget, risques, échéances |
| **Supervision agents**   | Latence, taux d'erreur JSON, succès API, équilibrage, journal d'exécutions |
| **Journal d'audit**      | Traçabilité complète, filtres, détail des métadonnées et diffs |
| **Annonces**             | Diffusion ciblée par rôle ou sélection nominative |
| **Paramètres**           | Runtime agents, connecteurs, règles de gouvernance, stack |

---

## 🤖 Architecture multi-agents

Trois agents spécialisés, coordonnés par un orchestrateur (LangGraph, CrewAI ou
AutoGen), avec une **étape de validation humaine** avant toute écriture Jira/Trello.

| Agent | Rôle | Modèle suggéré |
| ----- | ---- | -------------- |
| **Agent 1 — Scoping** | Cadrage & décomposition (texte → JSON) | Llama 3.2 / Phi-3.5-mini / Qwen2.5-3B — LoRA/QLoRA |
| **Agent 2 — Ops** | Intégration Jira/Trello & assignation initiale | SLM tool-calling + sentence-transformers (all-MiniLM-L6-v2) |
| **Agent 3 — Risk** | Analyse & suivi des risques | XGBoost/LightGBM + DistilBERT/CamemBERT |

### ⚠️ État : emplacements réservés

**Aucun agent n'est implémenté.** Le contrat d'entrée/sortie est figé côté plateforme ;
les lancements créent une exécution au statut `SKIPPED` (« réservé »), journalisée dans
l'audit, **sans appel de modèle ni écriture externe**. Rien n'est simulé.

### Brancher le runtime

1. Implémenter `backend/orchestration/services.py::dispatch(run)`
   (appel HTTP au runtime, file Celery, ou exécution locale du modèle).
2. Renseigner `AgentDefinition.runtime_endpoint` pour chaque agent.
3. Activer la variable d'environnement :

```bash
AGENT_RUNTIME_ENABLED=True
SCOPING_AGENT_URL=https://agents.local/scoping
OPS_AGENT_URL=https://agents.local/ops
RISK_AGENT_URL=https://agents.local/risk
ORCHESTRATOR=LangGraph
```

Les helpers `build_scoping_payload()`, `build_ops_payload()` et `build_risk_payload()`
construisent déjà les charges utiles conformes au contrat.

### Validation humaine

`POST /api/proposals/{id}/validate/` avec `{"decision": "APPROVE"|"REJECT"}` :

- `APPROVE` → matérialise les tâches dans Cadria, applique les assignations acceptées,
  journalise l'action (et l'intention de poussée externe si `push_to_external: true`) ;
- `REJECT` → enregistre le motif, ne crée rien.

---

## 🔌 API — principaux endpoints

| Méthode | Endpoint | Description |
| ------- | -------- | ----------- |
| `POST` | `/api/auth/register/` | Inscription (rôle admin refusé) |
| `POST` | `/api/auth/login/` | Connexion → JWT access + refresh |
| `POST` | `/api/auth/refresh/` | Rafraîchissement du token |
| `GET`/`PATCH` | `/api/me/` | Profil courant |
| `GET` | `/api/analytics/dashboard/` | KPI espace client |
| `GET` | `/api/analytics/admin/` | KPI administration |
| `GET` | `/api/analytics/insights/` | Métriques qualité transverses |
| `CRUD` | `/api/projects/` | Projets (+ `board/`, `workload/`, `recompute/`, `sync/`) |
| `CRUD` | `/api/tasks/` | Tâches (+ `move/`, `bulk_status/`) |
| `CRUD` | `/api/work-packages/`, `/api/sprints/`, `/api/risks/`, `/api/comments/` | Domaines projet |
| `GET` | `/api/agents/` | Définitions des 3 agents |
| `POST` | `/api/agents/runs/start/` | Déclencher un agent |
| `GET` | `/api/agents/monitor/` | Supervision (latence, erreurs, statuts) |
| `POST` | `/api/proposals/{id}/validate/` | **Validation humaine** |
| `CRUD` | `/api/notifications/` | Notifications (+ `summary/`, `mark_all_read/`, `broadcast/`) |
| `CRUD` | `/api/users/` | Administration des comptes (rôle ADMIN requis) |
| `GET` | `/api/audit/`, `/api/audit/summary/` | Journal d'audit |

Liste complète : `GET /api/` (index) ou `http://localhost:8000/admin/`.

---

## ✅ Tests

```bash
cd backend
python3 manage.py test --parallel 1
```

**58 tests d'intégration** couvrant authentification, autorisations, projets, tâches,
kanban, agents (emplacements réservés), validation humaine, notifications, équipes,
audit et analytics. Ils exercent réellement les vues et sérialiseurs.

---

## 🎨 Charte graphique

| Rôle | Couleur |
| ---- | ------- |
| Primaire | `#2563EB` (brand-600) · foncé `#1D4ED8` · clair `#EFF6FF` |
| Secondaire | `#0EA5E9` (sky-500) |
| Succès | `#10B981` · Avertissement `#F59E0B` · Danger `#E11D48` |
| Agent / réservé | `#8B5CF6` (violet) |
| Neutre | `#F8FAFC` / `#E2E8F0` / `#64748B` / `#0F172A` |

Police : Inter (avec repli système). Rayons `12px` sur les cartes, `8px` sur les
contrôles. Ombres `shadow-card` au repos, `shadow-card-hover` au survol.
Palette complète dans `frontend/tailwind.config.js`, composants dans
`frontend/src/styles/index.css`.

---

## 🐳 Docker (optionnel)

```bash
docker compose up --build
# API      → http://localhost:8000
# Frontend → http://localhost:5173
```

---

## 📄 Documentation

- [`docs/API.md`](docs/API.md) — référence détaillée de l'API
- [`docs/AGENTS.md`](docs/AGENTS.md) — contrat des agents et procédure de branchement
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — modèle de données et décisions techniques

---

## 📜 Licence

Projet de démonstration réalisé à partir du cahier des charges « Copilote de cadrage,
de découpage et de pilotage de projets ».
