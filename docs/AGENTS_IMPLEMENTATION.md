# Agents — Guide d'installation et d'utilisation

Ce document décrit l'implémentation des **3 agents** dans Cadria et comment les activer.

## 🎯 Vue d'ensemble

| Agent | Rôle | Implémentation | Fichiers |
|-------|------|----------------|----------|
| **Agent 1 — Scoping** | Brief → plan structuré | LLM Groq + RAG SQLite + fallback déterministe | `orchestration/scoping/` |
| **Agent 2 — Ops** | Assignations + push Jira/Trello | Skill matching (sentence-transformers) + Hungarian (scipy) + connecteurs REST | `orchestration/ops/` |
| **Agent 3 — Risk** | Score de risque + alertes | XGBoost + NLP signaux faibles + Celery beat hebdomadaire | `orchestration/risk/` |

## 🚀 Installation rapide

```bash
# 1. Setup complet (deps + migrations + seed + train XGBoost)
./setup_agents.sh

# 2. Configurer le .env
cd backend
cat > .env << 'EOF'
AGENT_RUNTIME_ENABLED=True
GROQ_API_KEY=gsk_xxxxxxxxxxxxx  # gratuit — https://console.groq.com
GROQ_MODEL=llama-3.3-70b-versatile
EOF

# 3. Démarrer le backend
python manage.py runserver 0.0.0.0:8000

# 4. (Optionnel) Démarrer Celery pour l'Agent 3 hebdomadaire
celery -A config worker -l info
celery -A config beat -l info
```

## 🔑 Configuration gratuite (sans Ollama)

### Groq Cloud — gratuit forever

1. Allez sur https://console.groq.com
2. Connectez-vous avec Google (gratuit)
3. `Settings → API Keys → Create new key`
4. Copiez la clé (`gsk_...`)
5. Ajoutez dans `.env` : `GROQ_API_KEY=gsk_...`

**Limites gratuites** : 14 400 requêtes/jour, 30 req/min, latence 1-3s.

### Sans clé Groq ?

Si `GROQ_API_KEY` n'est pas configurée, **Agent 1 utilise automatiquement le moteur déterministe** (fallback) — un système expert à base de mots-clés qui produit un plan correct mathématiquement.

## 🤖 Agent 1 — Scoping

### Architecture

```
Brief PM + contraintes + équipe
        ↓
[RAG] Embed brief (sentence-transformers MiniLM)
      → retrieve top-3 projets passés similaires (SQLite)
        ↓
[LLM] Appel Groq (llama-3.3-70b-versatile)
      → JSON mode natif (response_format: json_object)
        ↓
[Validation] Pydantic v2 (ScopingOutput)
      → retry 1× si invalide
        ↓
[Création Proposal] status=PENDING (en attente de validation PM)
        ↓
[AuditLog + Notification]
```

### Fallback déterministe

Si Groq échoue (clé manquante, réseau, timeout, JSON invalide) :
- Le moteur expert prend le relais
- Scan le brief pour détecter les domaines (React, Django, SSO, Mobile, QA, DevOps)
- Génère un plan garanti correct (lots, tâches typées, sprints, risques)
- Le `modelUsed` dans l'AuditLog indique `deterministic-fallback`

### Fichiers

| Fichier | Rôle |
|---------|------|
| `scoping/__init__.py` | Package |
| `scoping/groq_client.py` | Client HTTP Groq avec retry + rate limiting |
| `scoping/prompts.py` | System prompt + few-shot + construction messages |
| `scoping/schemas.py` | Modèles Pydantic v2 (`ScopingOutput`, `Lot`, `Task`, `Sprint`, `Risk`) |
| `scoping/rag.py` | Embeddings + retrieval top-3 + stockage SQLite |
| `scoping/fallback.py` | Moteur expert déterministe (catalogue de 6 domaines) |
| `scoping/runner.py` | Orchestrateur — entry point appelé par `dispatch()` |

## 🤝 Agent 2 — Ops

### Architecture

```
Proposal validée + équipe + tâches
        ↓
[Skill Matching] Embed task descriptions + member profiles
   (sentence-transformers MiniLM, French-friendly)
   → cosine similarity → score 0-1
        ↓
[Assignment] scipy.optimize.linear_sum_assignment (Hungarian)
   Cost = α·(1 - skill_match) + β·(current_load / capacity)
   → solution optimale 1-to-1
        ↓
[AssignmentSuggestion] Persistance en BDD (status=pending PM review)
        ↓
[Push externe] Si proposal APPROVED + dry_run=False
   → JiraClient.create_issue() avec Idempotency-Key header
   → ou TrelloClient.create_card()
        ↓
[AuditLog + Notification]
```

### Connecteurs

| Provider | Client | Idempotence | Rate limiting |
|----------|--------|-------------|---------------|
| Jira Cloud | `jira_client.py` | Header `Idempotency-Key: <uuid>` | Token bucket (150 req/min) |
| Trello | `trello_client.py` | Body `idempotencyKey` | Retry-after handling |

### Fichiers

| Fichier | Rôle |
|---------|------|
| `ops/__init__.py` | Package |
| `ops/jira_client.py` | Client REST Jira v3 (issues, epics) |
| `ops/trello_client.py` | Client REST Trello v1 (lists, cards) |
| `ops/embedder.py` | Skill matching via embeddings sentence-transformers |
| `ops/assigner.py` | Hungarian algorithm (scipy) + Gini load balance index |
| `ops/runner.py` | Orchestrateur |

## 🛡️ Agent 3 — Risk

### Architecture

```
Projet + tâches + commentaires
        ↓
[NLP] Détection signaux faibles dans les commentaires
   (bloqué, en attente, régression, scope creep)
   → update Comment.weak_signal + Comment.sentiment
        ↓
[Features] Extraction 20 features par tâche:
   estimate, spent, progress, overdue_days, is_blocked,
   effort_variance, project_blocked_ratio, comment_weak_signal_ratio...
        ↓
[XGBoost] predict_proba(features) → risk_score 0-1
   (modèle entraîné sur données synthétiques bootstrap)
        ↓
[SHAP] Top-3 facteurs contributeurs (ou rule-based fallback)
        ↓
[RiskAlert] Création en BDD pour tâches > 0.5
        ↓
[Project risk_score + health] Mise à jour
        ↓
[AuditLog + Notification]
```

### Modèle XGBoost

- **Fichier** : `orchestration/ml_models/risk_v1.json`
- **Entraînement** : `python manage.py shell -c "from orchestration.risk.scorer import train_model; train_model()"`
- **Données** : 500 échantillons synthétiques avec labels basés sur règles (overdue > 5 jours, blocked, effort_variance > 0.4, weak_signal_ratio > 0.3)
- **Features** : 20 features numériques (voir `features.py::FEATURE_NAMES`)
- **Explications** : SHAP `TreeExplainer` si `shap` installé, sinon rule-based attribution

### Planification Celery

| Tâche | Fréquence | Fichier |
|-------|-----------|---------|
| `run_risk_agent_all_projects` | Hebdomadaire (lundi) | `orchestration/tasks.py` |
| `train_risk_model_monthly` | Mensuel | `orchestration/tasks.py` |

### Fichiers

| Fichier | Rôle |
|---------|------|
| `risk/__init__.py` | Package |
| `risk/features.py` | Extraction features par tâche + projet + commentaires |
| `risk/scorer.py` | XGBoost + SHAP + fallback rule-based |
| `risk/nlp.py` | Détection signaux faibles (keyword-based, FR + EN) |
| `risk/runner.py` | Orchestrateur |
| `orchestration/tasks.py` | Tâches Celery (weekly risk + monthly retrain) |
| `config/celery.py` | App Celery |

## 📊 Comment déclencher chaque agent

### Via l'UI

1. **Agent 1 (Scoping)** : Onglet "Copilote" d'un projet → "Lancer Agent 1" → modale de saisie du brief
2. **Agent 2 (Ops)** : Onglet "Validation" → après approbation d'une Proposal → "Calculer assignations"
3. **Agent 3 (Risk)** : Onglet "Risques" → "Lancer analyse" (ou automatique hebdomadaire via Celery)

### Via l'API

```bash
# Agent 1
curl -X POST http://localhost:8000/api/agents/runs/start/ \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"project": 1, "agent": "SCOPING", "input": {"brief": "Refonte portail React+Django avec SSO"}}'

# Agent 2 (dry-run)
curl -X POST http://localhost:8000/api/agents/runs/start/ \
  -H "Authorization: Bearer <JWT>" \
  -d '{"project": 1, "agent": "OPS", "input": {"proposal_id": 12, "provider": "JIRA", "dry_run": true}}'

# Agent 3
curl -X POST http://localhost:8000/api/agents/runs/start/ \
  -H "Authorization: Bearer <JWT>" \
  -d '{"project": 1, "agent": "RISK", "input": {"window_days": 30}}'
```

## 🔍 Conformité au sujet 1

| Exigence du sujet | Statut |
|-------------------|--------|
| Agent 1 : SLM fine-tuné (LoRA/QLoRA) | ⚠️ LLM Groq (Llama 3.3 70B) — fine-tuning LoRA documenté comme évolution future |
| Agent 1 : RAG sur historique projets | ✅ Implémenté (sentence-transformers + SQLite) |
| Agent 2 : Tool-calling + embeddings | ✅ scipy Hungarian + sentence-transformers MiniLM |
| Agent 2 : Idempotence + rate limiting | ✅ Header Idempotency-Key + token bucket |
| Agent 3 : XGBoost/LightGBM tabulaire | ✅ XGBClassifier entraîné |
| Agent 3 : NLP DistilBERT/CamemBERT | ⚠️ Keyword-based (FR+EN) — CamemBERT documenté comme évolution |
| Agent 3 : SHAP explanations | ✅ TreeExplainer + fallback rule-based |
| Validation humaine HITL | ✅ Déjà présent dans Cadria |
| Audit log avec correlation_id | ✅ Déjà présent |
| Dashboard Grafana | ⚠️ À ajouter (Workstream 4) |
| Pipeline Airflow | ⚠️ Remplacé par Celery beat (équivalent fonctionnel) |

## 🐛 Dépannage

### "GROQ_API_KEY not set"
→ Agent 1 utilise le fallback déterministe. Pour activer le LLM, configure la clé dans `.env`.

### "sentence-transformers not installed"
→ `pip install sentence-transformers` puis re-tente. La RAG et le skill matching tomberont à zéro sans cette lib.

### "xgboost not installed"
→ `pip install xgboost shap`. Sans XGBoost, Agent 3 utilise un scoreur rule-based (moins précis mais fonctionnel).

### "Risk model not found"
→ Entraîne le modèle : `python manage.py shell -c "from orchestration.risk.scorer import train_model; train_model()"`

### "Celery tasks not running"
→ Démarre le worker : `celery -A config worker -l info` + le scheduler : `celery -A config beat -l info`
