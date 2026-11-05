"""
Jeu de données de démonstration.

    python manage.py seed_demo            # charge les données de démo
    python manage.py seed_demo --reset    # purge puis recharge

Comptes créés (mot de passe commun : Cadria@2026)
    admin@cadria.io      — Administrateur
    pm@cadria.io         — Chef de projet ( propriétaire des projets de démo )
    member@cadria.io     — Membre d'équipe
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Skill, Team, User, UserSkill
from audit.models import AuditLog
from notifications.models import Notification, NotificationPreference
from orchestration.models import (
    AgentDefinition,
    AgentRun,
    AssignmentSuggestion,
    Proposal,
)
from projects.models import (
    Comment,
    Integration,
    Project,
    RiskAlert,
    Sprint,
    Task,
    WorkPackage,
)

random.seed(42)

PASSWORD = "Cadria@2026"

BLUES = ["#2563EB", "#1D4ED8", "#0EA5E9", "#0284C7", "#3B82F6", "#0369A1", "#1E40AF", "#38BDF8"]

SKILLS = {
    "TECH": ["Python", "Django", "React", "TypeScript", "Node.js", "PostgreSQL", "Docker",
             "Kubernetes", "CI/CD", "REST API", "GraphQL", "Terraform"],
    "DATA": ["Machine Learning", "NLP", "MLOps", "Data engineering", "XGBoost",
             "Sentence-Transformers", "LLM / RAG", "Fine-tuning LoRA"],
    "DESIGN": ["UX Research", "UI Design", "Design System", "Accessibilité"],
    "FUNC": ["Gestion de projet", "Recette fonctionnelle", "Rédaction de specs", "Conformité RGPD"],
    "MGMT": ["Scrum Master", "Management d'équipe", "Gestion des risques", "Chiffrage"],
}

PEOPLE = [
    # email, first, last, role, job title, company
    ("admin@cadria.io", "Amel", "Ben Salah", "ADMIN", "Directrice de la plateforme", "Cadria"),
    ("pm@cadria.io", "Yassine", "Trabelsi", "PM", "Chef de projet senior", "Cadria"),
    ("member@cadria.io", "Nour", "Chaabane", "MEMBER", "Développeuse full-stack", "Cadria"),
    ("sarah@cadria.io", "Sarah", "Mansour", "PM", "Cheffe de projet digital", "Cadria"),
    ("karim@cadria.io", "Karim", "Jaziri", "MEMBER", "Ingénieur backend", "Cadria"),
    ("ines@cadria.io", "Ines", "Gharbi", "MEMBER", "Data scientist", "Cadria"),
    ("luca@cadria.io", "Luca", "Moretti", "MEMBER", "Designer UX/UI", "Cadria"),
    ("hugo@cadria.io", "Hugo", "Bernard", "MEMBER", "Ingénieur DevOps", "Cadria"),
    ("lena@cadria.io", "Lena", "Kowalski", "MEMBER", "Ingénieure QA", "Cadria"),
    ("omar@cadria.io", "Omar", "Saidi", "VIEWER", "Sponsor produit", "Cadria"),
    ("julie@cadria.io", "Julie", "Fontaine", "MEMBER", "Product owner", "Cadria"),
    ("amine@cadria.io", "Amine", "Belhadj", "MEMBER", "Développeur mobile", "Cadria"),
]

AGENTS = [
    {
        "key": "SCOPING",
        "name": "Agent 1 — Cadrage & décomposition",
        "short_name": "Scoping",
        "icon": "sitemap",
        "color": "#2563EB",
        "description": (
            "Transforme une description en langage naturel en un plan structuré : "
            "architecture proposée, lots, tâches, estimations d'effort et risques identifiés. "
            "Génération JSON structurée via SLM fine-tuné (LoRA/QLoRA) + RAG sur l'historique projets."
        ),
        "suggested_model": "Llama 3.2 (1B/3B) · Phi-3.5-mini · Qwen2.5-3B — LoRA/QLoRA",
        "suggested_stack": "Fine-tuning sur cahiers des charges → décompositions de tâches",
        "requires_human_validation": True,
        "capabilities": [
            "Génération structurée texte → JSON (lots / tâches / estimations)",
            "RAG sur l'historique des projets passés",
            "Détection des dépendances entre tâches",
            "Extraction des hypothèses et du hors-périmètre",
        ],
        "input_schema_hint": {
            "brief": "string (description libre du projet)",
            "constraints": {"budget": "number", "deadline": "ISO date", "team_size": "number"},
            "team": [{"id": "number", "skills": [{"name": "string", "level": "1-5"}]}],
        },
        "output_schema_hint": {
            "lots": [{"name": "string", "description": "string", "estimate_hours": "number",
                      "confidence": "0-1", "color": "hex"}],
            "tasks": [{"ref": "string", "lot": "string", "title": "string", "description": "string",
                       "type": "FEATURE|BUG|TECH|SPIKE|DOC|TEST", "priority": "...",
                       "estimate_hours": "number", "story_points": "number",
                       "skills": ["string"], "acceptance_criteria": ["string"],
                       "risk_score": "0-100", "sprint": "string"}],
            "sprints": [{"name": "string", "goal": "string", "capacity_hours": "number"}],
            "risks": [{"category": "string", "title": "string", "score": "0-100"}],
            "assumptions": ["string"],
            "total_estimate_hours": "number",
            "confidence": "0-1",
        },
        "order": 1,
    },
    {
        "key": "OPS",
        "name": "Agent 2 — Intégration Jira/Trello & assignation",
        "short_name": "Ops",
        "icon": "plug",
        "color": "#0EA5E9",
        "description": (
            "Traduit le JSON de l'Agent 1 en appels API : création de sprints, d'epics, de tickets "
            "et de champs personnalisés. Réalise la première assignation par matching d'embeddings "
            "entre description de tâche et profils de compétences, avec équilibrage de charge."
        ),
        "suggested_model": "SLM tool-calling · LangGraph/CrewAI + sentence-transformers (all-MiniLM-L6-v2)",
        "suggested_stack": "Agent à tool-calling (function calling) — exécutable en CPU",
        "requires_human_validation": True,
        "capabilities": [
            "Création de sprints / epics / tickets via API Jira (REST) ou Trello",
            "Idempotence des appels & gestion du rate limiting",
            "Matching compétences par embeddings",
            "Équilibrage de charge (problème d'affectation)",
            "Journal d'audit de chaque écriture",
        ],
        "input_schema_hint": {
            "proposal_id": "number",
            "provider": "JIRA | TRELLO",
            "dry_run": "boolean",
            "tasks": ["..."],
            "assignments": [{"task_ref": "string", "user_id": "number", "score": "0-1"}],
        },
        "output_schema_hint": {
            "created": [{"external_id": "string", "external_url": "string", "entity": "sprint|epic|issue"}],
            "assignments": [{"task_ref": "string", "user_id": "number", "applied": "boolean"}],
            "api_calls": "number",
            "errors": ["string"],
        },
        "order": 2,
    },
    {
        "key": "RISK",
        "name": "Agent 3 — Analyse & suivi des risques",
        "short_name": "Risk",
        "icon": "shield-alert",
        "color": "#1E40AF",
        "description": (
            "Se connecte périodiquement à Jira/Trello (et GitHub) pour extraire vélocité, cycle time, "
            "ratio de tâches en retard, taux de réouverture de bugs et tâches bloquées. Combine un "
            "modèle tabulaire léger et une lecture NLP des commentaires (signaux faibles)."
        ),
        "suggested_model": "XGBoost / LightGBM + DistilBERT / CamemBERT (classification NLP)",
        "suggested_stack": "Entraînable en CPU local — cohérent avec les contraintes de ressources",
        "requires_human_validation": False,
        "capabilities": [
            "Extraction de métriques Jira/Trello/GitHub (vélocité, cycle time…)",
            "Scoring de risque par tâche / sprint / projet",
            "Explication automatique des facteurs contributeurs",
            "Détection de signaux faibles dans les commentaires",
            "Comparaison aux patterns de projets historiques (RAG)",
        ],
        "input_schema_hint": {
            "project_reference": "string",
            "window_days": "number",
            "tasks": [{"id": "number", "status": "string", "estimate_hours": "number",
                       "spent_hours": "number", "blocked": "boolean", "due_date": "ISO date"}],
            "comments": [{"id": "number", "body": "string"}],
        },
        "output_schema_hint": {
            "risk_score": "0-100",
            "alerts": [{"category": "DELAY|QUALITY|LOAD|BLOCKER|SCOPE|BUDGET",
                        "severity": "INFO|WARNING|CRITICAL", "title": "string",
                        "message": "string", "score": "0-100",
                        "factors": [{"label": "string", "weight": "number"}],
                        "recommendation": "string"}],
            "factors": ["string"],
        },
        "order": 3,
    },
]

PROJECTS = [
    {
        "name": "Refonte du portail client",
        "summary": "Nouveau portail self-service pour les clients grand compte",
        "brief": (
            "Nous devons refondre le portail client actuel, vieillissant et peu utilisé (12% d'adoption). "
            "L'objectif est de livrer en 5 mois un portail self-service permettant aux clients grands "
            "comptes de consulter leurs factures, suivre leurs commandes, gérer leurs utilisateurs et "
            "ouvrir des tickets de support. Le portail doit être responsive, accessible RGAA, intégrer "
            "le SSO existant (Keycloak) et exposer une API publique documentée. L'équipe dispose de "
            "2 développeurs front, 2 back, 1 designer et 1 QA."
        ),
        "methodology": "SCRUM",
        "status": "ACTIVE",
        "health": "AMBER",
        "tags": ["portail", "front", "SSO", "accessibilité"],
        "budget": 320000,
        "lots": [
            ("Cadrage & conception UX", 180, "#2563EB"),
            ("Refonte front-end", 420, "#0EA5E9"),
            ("API publique & intégrations", 360, "#1D4ED8"),
            ("SSO & sécurité", 160, "#0284C7"),
            ("Recette & mise en production", 200, "#3B82F6"),
        ],
        "tasks": [
            ("Ateliers de cadrage avec 5 clients référents", "Cadrage & conception UX", "SPIKE", "HIGH", 40, "DONE", "Julie Fontaine", ["Gestion de projet"]),
            ("Cartographie du parcours client actuel", "Cadrage & conception UX", "DOC", "MEDIUM", 24, "DONE", "Luca Moretti", ["UX Research"]),
            ("Maquettes haute fidélité (12 écrans)", "Cadrage & conception UX", "FEATURE", "HIGH", 80, "DONE", "Luca Moretti", ["UI Design"]),
            ("Design system & composants réutilisables", "Cadrage & conception UX", "FEATURE", "HIGH", 64, "IN_PROGRESS", "Luca Moretti", ["Design System"]),
            ("Migration du socle React 17 → 18", "Refonte front-end", "TECH", "HIGH", 40, "DONE", "Nour Chaabane", ["React", "TypeScript"]),
            ("Écran tableau de bord client", "Refonte front-end", "FEATURE", "HIGHEST", 56, "IN_PROGRESS", "Nour Chaabane", ["React", "TypeScript"]),
            ("Écran facturation & téléchargement PDF", "Refonte front-end", "FEATURE", "HIGH", 48, "TODO", "Amine Belhadj", ["React"]),
            ("Suivi de commande temps réel (WebSocket)", "Refonte front-end", "FEATURE", "MEDIUM", 72, "TODO", "Amine Belhadj", ["React", "TypeScript"]),
            ("Responsive mobile & tablette", "Refonte front-end", "FEATURE", "MEDIUM", 40, "TODO", "Nour Chaabane", ["UI Design", "React"]),
            ("Conformité RGAA 4.1 (audit + correctifs)", "Refonte front-end", "TECH", "HIGH", 56, "BLOCKED", "Luca Moretti", ["Accessibilité"]),
            ("Conception de l'API REST publique", "API publique & intégrations", "SPIKE", "HIGH", 32, "DONE", "Karim Jaziri", ["REST API"]),
            ("Implémentation des endpoints v1 (18 routes)", "API publique & intégrations", "FEATURE", "HIGHEST", 120, "IN_PROGRESS", "Karim Jaziri", ["Django", "REST API"]),
            ("Génération automatique de la doc OpenAPI", "API publique & intégrations", "DOC", "MEDIUM", 24, "TODO", "Karim Jaziri", ["REST API"]),
            ("Connecteur ERP SAP (lecture factures)", "API publique & intégrations", "FEATURE", "HIGH", 96, "BLOCKED", "Karim Jaziri", ["REST API", "Node.js"]),
            ("Gestion des quotas & rate limiting", "API publique & intégrations", "FEATURE", "MEDIUM", 32, "TODO", "Hugo Bernard", ["REST API"]),
            ("Intégration Keycloak (OIDC)", "SSO & sécurité", "FEATURE", "HIGHEST", 64, "IN_PROGRESS", "Hugo Bernard", ["Docker"]),
            ("Cartographie des rôles & permissions", "SSO & sécurité", "DOC", "HIGH", 24, "DONE", "Julie Fontaine", ["Conformité RGPD"]),
            ("Audit de sécurité & correction des failles", "SSO & sécurité", "TECH", "HIGH", 56, "TODO", "Hugo Bernard", ["CI/CD"]),
            ("Plan de recette (120 cas de test)", "Recette & mise en production", "TEST", "HIGH", 40, "TODO", "Lena Kowalski", ["Recette fonctionnelle"]),
            ("Automatisation des tests e2e (Cypress)", "Recette & mise en production", "TEST", "MEDIUM", 64, "TODO", "Lena Kowalski", ["CI/CD"]),
            ("Pipeline CI/CD & déploiement bleu-vert", "Recette & mise en production", "TECH", "HIGH", 48, "IN_PROGRESS", "Hugo Bernard", ["CI/CD", "Kubernetes"]),
            ("Conduite du changement & formation support", "Recette & mise en production", "DOC", "LOW", 32, "TODO", "Sarah Mansour", ["Gestion de projet"]),
        ],
    },
    {
        "name": "Copilote IA interne — Cadria",
        "summary": "Assistant de cadrage projet basé sur un système multi-agents",
        "brief": (
            "Construire un copilote interne de cadrage et de pilotage de projets. Le chef de projet "
            "saisit une description en langage naturel ; le système propose une architecture, découpe "
            "le travail en lots et tâches, estime l'effort, identifie les risques, crée les sprints et "
            "tickets dans Jira, assigne les tâches puis surveille en continu les risques. "
            "Architecture multi-agents avec orchestrateur et validation humaine obligatoire avant "
            "toute écriture dans Jira."
        ),
        "methodology": "SCRUM",
        "status": "ACTIVE",
        "health": "GREEN",
        "tags": ["IA", "multi-agents", "RAG", "Jira"],
        "budget": 180000,
        "lots": [
            ("Orchestration multi-agents", 200, "#2563EB"),
            ("Agent 1 — Cadrage", 240, "#0EA5E9"),
            ("Agent 2 — Intégration Jira/Trello", 180, "#1D4ED8"),
            ("Agent 3 — Analyse de risques", 200, "#0284C7"),
            ("Observabilité & MLOps", 140, "#3B82F6"),
        ],
        "tasks": [
            ("Choix de l'orchestrateur (LangGraph / CrewAI)", "Orchestration multi-agents", "SPIKE", "HIGH", 24, "DONE", "Ines Gharbi", ["Machine Learning"]),
            ("Définition du protocole inter-agents", "Orchestration multi-agents", "DOC", "HIGH", 32, "DONE", "Ines Gharbi", ["Machine Learning"]),
            ("File d'exécution & reprise sur erreur", "Orchestration multi-agents", "FEATURE", "HIGH", 48, "IN_PROGRESS", "Karim Jaziri", ["Python", "Django"]),
            ("Constitution du corpus d'apprentissage (120 CDC)", "Agent 1 — Cadrage", "SPIKE", "HIGHEST", 64, "DONE", "Ines Gharbi", ["Data engineering"]),
            ("Fine-tuning LoRA du SLM de génération", "Agent 1 — Cadrage", "FEATURE", "HIGHEST", 96, "IN_PROGRESS", "Ines Gharbi", ["LLM / RAG", "Fine-tuning LoRA"]),
            ("Pipeline RAG sur l'historique projets", "Agent 1 — Cadrage", "FEATURE", "HIGH", 56, "IN_PROGRESS", "Ines Gharbi", ["LLM / RAG", "NLP"]),
            ("Évaluation : complétude & taux de hors-format", "Agent 1 — Cadrage", "TEST", "HIGH", 40, "TODO", "Lena Kowalski", ["Recette fonctionnelle"]),
            ("Connecteur Jira (création sprint/epic/issue)", "Agent 2 — Intégration Jira/Trello", "FEATURE", "HIGHEST", 80, "IN_PROGRESS", "Karim Jaziri", ["REST API", "Python"]),
            ("Idempotence & gestion du rate limiting", "Agent 2 — Intégration Jira/Trello", "FEATURE", "HIGH", 40, "TODO", "Karim Jaziri", ["REST API"]),
            ("Matching compétences par embeddings", "Agent 2 — Intégration Jira/Trello", "FEATURE", "HIGH", 56, "TODO", "Ines Gharbi", ["Sentence-Transformers", "NLP"]),
            ("Algorithme d'équilibrage de charge", "Agent 2 — Intégration Jira/Trello", "FEATURE", "MEDIUM", 48, "TODO", "Ines Gharbi", ["Machine Learning"]),
            ("Collecte hebdomadaire des métriques Jira", "Agent 3 — Analyse de risques", "FEATURE", "HIGH", 48, "IN_PROGRESS", "Karim Jaziri", ["Data engineering", "REST API"]),
            ("Modèle de scoring de risque (XGBoost)", "Agent 3 — Analyse de risques", "FEATURE", "HIGHEST", 72, "TODO", "Ines Gharbi", ["XGBoost", "Machine Learning"]),
            ("Détection de signaux faibles (CamemBERT)", "Agent 3 — Analyse de risques", "FEATURE", "HIGH", 64, "TODO", "Ines Gharbi", ["NLP", "Machine Learning"]),
            ("Explicabilité des facteurs de risque", "Agent 3 — Analyse de risques", "FEATURE", "MEDIUM", 40, "TODO", "Ines Gharbi", ["Machine Learning"]),
            ("Dashboard Grafana (latence, erreurs, charge)", "Observabilité & MLOps", "FEATURE", "MEDIUM", 40, "IN_PROGRESS", "Hugo Bernard", ["Docker", "Kubernetes"]),
            ("Pipeline Airflow de ré-entraînement mensuel", "Observabilité & MLOps", "FEATURE", "MEDIUM", 56, "TODO", "Hugo Bernard", ["MLOps", "Data engineering"]),
            ("Journal d'audit des actions agents", "Observabilité & MLOps", "FEATURE", "HIGH", 32, "DONE", "Karim Jaziri", ["Django", "Python"]),
        ],
    },
    {
        "name": "Migration cloud & industrialisation",
        "summary": "Migration de l'infrastructure on-premise vers Kubernetes managé",
        "brief": (
            "Migrer les 34 applications internes hébergées on-premise vers un cluster Kubernetes "
            "managé, industrialiser les déploiements (GitOps) et réduire la facture d'hébergement de "
            "30%. Contraintes : aucune interruption de service supérieure à 15 minutes, conservation "
            "de la conformité ISO 27001, et formation des équipes ops."
        ),
        "methodology": "KANBAN",
        "status": "AT_RISK",
        "health": "RED",
        "tags": ["cloud", "kubernetes", "gitops", "iso27001"],
        "budget": 450000,
        "lots": [
            ("Inventaire & cartographie", 120, "#2563EB"),
            ("Conteneurisation", 320, "#0EA5E9"),
            ("Cluster & réseau", 240, "#1D4ED8"),
            ("GitOps & observabilité", 200, "#0284C7"),
            ("Bascule & décommissionnement", 180, "#3B82F6"),
        ],
        "tasks": [
            ("Inventaire des 34 applications & dépendances", "Inventaire & cartographie", "DOC", "HIGH", 48, "DONE", "Hugo Bernard", ["Docker"]),
            ("Analyse des flux réseau existants", "Inventaire & cartographie", "SPIKE", "HIGH", 32, "DONE", "Hugo Bernard", ["Kubernetes"]),
            ("Dockerisation – lot 1 (12 apps)", "Conteneurisation", "TECH", "HIGH", 120, "IN_PROGRESS", "Karim Jaziri", ["Docker", "CI/CD"]),
            ("Dockerisation – lot 2 (12 apps)", "Conteneurisation", "TECH", "HIGH", 120, "TODO", "Nour Chaabane", ["Docker"]),
            ("Dockerisation – lot 3 (10 apps legacy)", "Conteneurisation", "TECH", "HIGHEST", 160, "BLOCKED", "Karim Jaziri", ["Docker"]),
            ("Provisionning Terraform du cluster", "Cluster & réseau", "FEATURE", "HIGH", 56, "DONE", "Hugo Bernard", ["Terraform", "Kubernetes"]),
            ("Maillage réseau & politiques de sécurité", "Cluster & réseau", "FEATURE", "HIGHEST", 72, "IN_PROGRESS", "Hugo Bernard", ["Kubernetes", "Terraform"]),
            ("Sauvegarde & plan de reprise d'activité", "Cluster & réseau", "FEATURE", "HIGHEST", 64, "BLOCKED", "Hugo Bernard", ["Kubernetes"]),
            ("Mise en place ArgoCD (GitOps)", "GitOps & observabilité", "FEATURE", "HIGH", 48, "IN_PROGRESS", "Hugo Bernard", ["Kubernetes", "CI/CD"]),
            ("Stack Prometheus / Grafana / Loki", "GitOps & observabilité", "FEATURE", "MEDIUM", 40, "TODO", "Hugo Bernard", ["Kubernetes"]),
            ("Bascule – vague 1 (8 apps non critiques)", "Bascule & décommissionnement", "FEATURE", "HIGH", 64, "TODO", "Karim Jaziri", ["Kubernetes"]),
            ("Bascule – vague 2 (16 apps)", "Bascule & décommissionnement", "FEATURE", "HIGHEST", 96, "TODO", "Nour Chaabane", ["Kubernetes"]),
            ("Décommissionnement des serveurs on-premise", "Bascule & décommissionnement", "TECH", "MEDIUM", 40, "TODO", "Hugo Bernard", ["Terraform"]),
        ],
    },
    {
        "name": "Application mobile de reporting terrain",
        "summary": "App mobile offline-first pour les équipes d'intervention",
        "brief": (
            "Livrer une application mobile (iOS/Android) permettant aux techniciens terrain de saisir "
            "leurs rapports d'intervention hors ligne, de joindre des photos et de synchroniser "
            "automatiquement les données à la reconnexion. L'app doit fonctionner en mode dégradé, "
            "gérer les conflits de synchronisation et s'intégrer au SI existant."
        ),
        "methodology": "SCRUM",
        "status": "PLANNED",
        "health": "GREEN",
        "tags": ["mobile", "offline", "react-native"],
        "budget": 150000,
        "lots": [
            ("Conception mobile", 120, "#2563EB"),
            ("Développement applicatif", 300, "#0EA5E9"),
            ("Synchronisation offline", 180, "#1D4ED8"),
            ("Tests terrain & déploiement", 120, "#0284C7"),
        ],
        "tasks": [
            ("Interviews terrain (8 techniciens)", "Conception mobile", "SPIKE", "HIGH", 32, "DONE", "Julie Fontaine", ["UX Research"]),
            ("Maquettes & prototype navigable", "Conception mobile", "FEATURE", "HIGH", 56, "DONE", "Luca Moretti", ["UI Design"]),
            ("Socle React Native & navigation", "Développement applicatif", "FEATURE", "HIGH", 48, "IN_PROGRESS", "Amine Belhadj", ["React", "TypeScript"]),
            ("Formulaire d'intervention dynamique", "Développement applicatif", "FEATURE", "HIGHEST", 72, "TODO", "Amine Belhadj", ["React", "TypeScript"]),
            ("Capture photo & annotation", "Développement applicatif", "FEATURE", "MEDIUM", 40, "TODO", "Amine Belhadj", ["React"]),
            ("Stockage local chiffré (SQLite)", "Synchronisation offline", "FEATURE", "HIGH", 56, "TODO", "Karim Jaziri", ["PostgreSQL"]),
            ("Moteur de synchronisation & conflits", "Synchronisation offline", "FEATURE", "HIGHEST", 88, "TODO", "Karim Jaziri", ["Python", "REST API"]),
            ("Tests sur 3 sites pilotes", "Tests terrain & déploiement", "TEST", "HIGH", 48, "TODO", "Lena Kowalski", ["Recette fonctionnelle"]),
            ("Publication App Store / Play Store", "Tests terrain & déploiement", "FEATURE", "MEDIUM", 24, "TODO", "Amine Belhadj", ["React"]),
        ],
    },
]

RISK_TEMPLATES = [
    ("DELAY", "CRITICAL", "Dérive du lot « {lot} »",
     "La charge réalisée dépasse l'estimation initiale de plus de 40% sur ce lot.",
     "Ré-estimer le reste à faire avec l'équipe et arbitrer le périmètre du sprint suivant.",
     [{"label": "Écart estimé / réalisé", "weight": 0.42},
      {"label": "3 tâches bloquées", "weight": 0.28},
      {"label": "Vélocité en baisse (-18%)", "weight": 0.2},
      {"label": "Dépendance externe non tenue", "weight": 0.1}]),
    ("BLOCKER", "WARNING", "Tâche bloquée depuis 6 jours",
     "Un blocage est remonté dans les commentaires sans action corrective associée.",
     "Organiser une réunion de déblocage sous 24 h avec le référent métier.",
     [{"label": "Commentaire « en attente de »", "weight": 0.5},
      {"label": "Aucune mise à jour depuis 6 j", "weight": 0.3},
      {"label": "Tâche sur chemin critique", "weight": 0.2}]),
    ("QUALITY", "WARNING", "Taux de réouverture de bugs élevé",
     "Le taux de réouverture atteint 22% sur les 30 derniers jours, au-delà du seuil de 10%.",
     "Renforcer la revue de code et ajouter des tests de non-régression ciblés.",
     [{"label": "Taux de réouverture 22%", "weight": 0.45},
      {"label": "Couverture de tests 54%", "weight": 0.35},
      {"label": "2 releases correctives", "weight": 0.2}]),
    ("LOAD", "WARNING", "Surcharge de {member}",
     "La charge planifiée dépasse la capacité hebdomadaire de plus de 25%.",
     "Redistribuer 2 tâches vers des profils disponibles avant le prochain sprint.",
     [{"label": "Utilisation 128%", "weight": 0.55},
      {"label": "4 tâches haute priorité", "weight": 0.3},
      {"label": "Absence planifiée", "weight": 0.15}]),
    ("SCOPE", "INFO", "Nouvelles demandes en cours de sprint",
     "Trois demandes ont été ajoutées après le démarrage du sprint en cours.",
     "Geler le périmètre du sprint et placer les demandes dans le backlog.",
     [{"label": "+3 tickets en cours de sprint", "weight": 0.6},
      {"label": "Vélocité stable", "weight": 0.25},
      {"label": "Pas d'impact jalon", "weight": 0.15}]),
    ("BUDGET", "CRITICAL", "Consommation budgétaire à 82%",
     "Le budget consommé atteint 82% alors que l'avancement réel est de 61%.",
     "Présenter un arbitrage au comité de pilotage : réduire le périmètre ou demander une rallonge.",
     [{"label": "Écart budget / avancement 21 pts", "weight": 0.5},
      {"label": "Charge réalisée en hausse", "weight": 0.3},
      {"label": "Prestataires externes facturés", "weight": 0.2}]),
]

COMMENTS = [
    "POC validé avec l'équipe sécurité, on peut avancer sur l'implémentation.",
    "Je suis bloqué en attente de la validation du schéma par l'équipe ERP.",
    "Attention, on observe une régression depuis la dernière mise en production.",
    "Estimation revue à la hausse après l'atelier de mardi : +16 h.",
    "Le connecteur SAP n'expose pas les avoirs, il faut passer par un export batch.",
    "Impossible de reproduire le bug en environnement de recette, besoin de logs.",
    "Maquettes validées par le sponsor produit ✅",
    "La dépendance vers l'équipe Data n'est pas tenue, on glisse d'une semaine.",
    "Top, le taux de couverture de tests est remonté à 71%.",
]

NOTIFICATION_TEMPLATES = [
    (Notification.Category.AGENT, Notification.Level.AGENT, "Agent 1 — plan de découpage prêt",
     "Un plan de {n} tâches a été généré pour « {project} ». Une validation humaine est requise."),
    (Notification.Category.RISK, Notification.Level.ERROR, "Risque critique détecté",
     "Le projet « {project} » présente un risque de dérive budgétaire (82% consommés)."),
    (Notification.Category.VALIDATION, Notification.Level.WARNING, "Plan en attente de validation",
     "Le plan v2 de « {project} » attend votre validation avant écriture dans Jira."),
    (Notification.Category.TASK, Notification.Level.INFO, "Nouvelle tâche assignée",
     "« {task} » vous a été assignée sur « {project} »."),
    (Notification.Category.TEAM, Notification.Level.INFO, "{member} a rejoint l'équipe",
     "{member} a été ajouté(e) à l'équipe du projet « {project} »."),
    (Notification.Category.RISK, Notification.Level.WARNING, "Surcharge détectée",
     "{member} dépasse sa capacité de 28% sur le sprint en cours."),
    (Notification.Category.INTEGRATION, Notification.Level.ERROR, "Échec de synchronisation Jira",
     "La synchronisation de « {project} » a échoué : quota API dépassé (429)."),
    (Notification.Category.AGENT, Notification.Level.AGENT, "Agent 3 — analyse terminée",
     "Analyse de risques de « {project} » terminée : score global 34/100 (à surveiller)."),
    (Notification.Category.SYSTEM, Notification.Level.SUCCESS, "Sauvegarde hebdomadaire effectuée",
     "La sauvegarde complète de la plateforme s'est terminée sans erreur."),
    (Notification.Category.ACCOUNT, Notification.Level.INFO, "Nouveau membre inscrit",
     "{member} vient de créer son compte Cadria."),
]


class Command(BaseCommand):
    help = "Charge un jeu de données de démonstration complet pour Cadria."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Purge les données existantes avant chargement")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write(self.style.WARNING("Purge des données existantes…"))
            AuditLog.objects.all().delete()
            Notification.objects.all().delete()
            AssignmentSuggestion.objects.all().delete()
            Proposal.objects.all().delete()
            AgentRun.objects.all().delete()
            AgentDefinition.objects.all().delete()
            Task.objects.all().delete()
            Sprint.objects.all().delete()
            WorkPackage.objects.all().delete()
            RiskAlert.objects.all().delete()
            Comment.objects.all().delete()
            Integration.objects.all().delete()
            Project.objects.all().delete()
            Team.objects.all().delete()
            UserSkill.objects.all().delete()
            User.objects.exclude(is_superuser=True).delete()

        self.stdout.write("Création des compétences…")
        skills = self._skills()
        self.stdout.write("Création des utilisateurs…")
        users = self._users(skills)
        self.stdout.write("Création des équipes…")
        self._teams(users)
        self.stdout.write("Création des agents (emplacements réservés)…")
        agents = self._agents()
        self.stdout.write("Création des projets…")
        projects = self._projects(users)
        self.stdout.write("Génération des propositions & exécutions agent…")
        self._agent_activity(users, agents, projects)
        self.stdout.write("Génération des risques & commentaires…")
        self._risks(users, projects)
        self.stdout.write("Génération des notifications…")
        self._notifications(users, projects)
        self.stdout.write("Génération du journal d'audit…")
        self._audit(users, projects, agents)
        self._integrations(users, projects)

        self.stdout.write(self.style.SUCCESS(
            "\n✔ Données de démonstration chargées.\n"
            f"  Connexion : admin@cadria.io / pm@cadria.io / member@cadria.io\n"
            f"  Mot de passe : {PASSWORD}"
        ))

    # ------------------------------------------------------------------ helpers
    def _skills(self):
        out = {}
        for category, names in SKILLS.items():
            for n in names:
                s, _ = Skill.objects.get_or_create(name=n, defaults={"category": category})
                out[n] = s
        return out

    def _users(self, skills):
        out = {}
        for i, (email, first, last, role, title, company) in enumerate(PEOPLE):
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first, "last_name": last, "role": role,
                    "job_title": title, "company": company,
                    "status": User.Status.ACTIVE, "is_active": True,
                    "avatar_color": BLUES[i % len(BLUES)],
                    "weekly_capacity_hours": random.choice([28, 35, 35, 35, 42]),
                    "hourly_cost": random.choice([45, 52, 58, 62, 70]),
                    "phone": f"+33 6 {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
                    "bio": f"{title} — {random.choice(['10 ans', '5 ans', '7 ans', '3 ans'])} d'expérience.",
                },
            )
            if created:
                user.set_password(PASSWORD)
                user.save()
                # compétences
                pool = {
                    "ADMIN": ["Gestion de projet", "Management d'équipe", "Chiffrage", "Gestion des risques"],
                    "PM": ["Gestion de projet", "Scrum Master", "Rédaction de specs", "Chiffrage", "Gestion des risques"],
                    "MEMBER": None,
                    "VIEWER": ["Gestion de projet"],
                }[role]
                if pool is None:
                    all_names = list(skills.keys())
                    pool = random.sample(all_names, random.randint(4, 7))
                for name in pool:
                    if name in skills:
                        UserSkill.objects.get_or_create(
                            user=user, skill=skills[name],
                            defaults={"level": random.randint(3, 5)},
                        )
                NotificationPreference.objects.get_or_create(user=user)
            out[email] = user
        return out

    def _teams(self, users):
        squads = [
            ("Squad Portail", "Équipe produit en charge du portail client", "#2563EB",
             ["pm@cadria.io", "member@cadria.io", "luca@cadria.io", "karim@cadria.io", "lena@cadria.io"]),
            ("Squad IA", "Équipe data & IA — copilote interne", "#0EA5E9",
             ["sarah@cadria.io", "ines@cadria.io", "karim@cadria.io", "lena@cadria.io"]),
            ("Squad Platform", "Infrastructure, cloud & industrialisation", "#1D4ED8",
             ["hugo@cadria.io", "karim@cadria.io", "member@cadria.io"]),
        ]
        for name, desc, color, emails in squads:
            team, created = Team.objects.get_or_create(name=name, defaults={
                "description": desc, "color": color, "owner": users[emails[0]],
            })
            if created:
                for e in emails:
                    team.members.add(users[e])

    def _agents(self):
        out = {}
        for cfg in AGENTS:
            caps = cfg.pop("capabilities")
            inp = cfg.pop("input_schema_hint")
            outp = cfg.pop("output_schema_hint")
            agent, _ = AgentDefinition.objects.update_or_create(
                key=cfg["key"], defaults={**cfg, "capabilities": caps,
                                          "input_schema_hint": inp, "output_schema_hint": outp},
            )
            out[agent.key] = agent
        return out

    def _projects(self, users):
        out = []
        now = timezone.now().date()
        for idx, spec in enumerate(PROJECTS):
            owner = users["pm@cadria.io"] if idx % 2 == 0 else users["sarah@cadria.io"]
            project, created = Project.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "summary": spec["summary"], "brief": spec["brief"],
                    "methodology": spec["methodology"], "status": spec["status"],
                    "health": spec["health"], "owner": owner, "budget": spec["budget"],
                    "tags": spec["tags"], "start_date": now - timedelta(days=60 + idx * 12),
                    "target_end_date": now + timedelta(days=random.choice([45, 90, 120, 150])),
                    "external_provider": random.choice(["JIRA", "TRELLO"]),
                    "external_key": f"CAD-{idx + 1}",
                },
            )
            if not created:
                out.append(project)
                continue

            team_name = ["Squad Portail", "Squad IA", "Squad Platform", "Squad Portail"][idx]
            team = Team.objects.filter(name=team_name).first()
            project.team = team
            project.save()
            members = list(users.values())
            project.members.set(random.sample(members, 7) + [owner])

            # lots
            wp_by_name = {}
            for i, (lot_name, effort, color) in enumerate(spec["lots"]):
                wp = WorkPackage.objects.create(
                    project=project, name=lot_name, order=i, color=color,
                    estimated_effort_hours=effort, confidence=round(random.uniform(0.62, 0.94), 2),
                    description=f"Lot « {lot_name} » — {effort} h estimées, issu du découpage de l'Agent 1.",
                )
                wp_by_name[lot_name] = wp

            # sprints
            sprint_names = ["Sprint 1 · Fondations", "Sprint 2 · Socle", "Sprint 3 · Accélération",
                            "Sprint 4 · Durcissement", "Sprint 5 · Mise en production"]
            sprint_by_name = {}
            for i, sname in enumerate(sprint_names[: len(spec["tasks"]) // 4 + 2]):
                s = Sprint.objects.create(
                    project=project, name=sname, order=i,
                    goal=f"Objectif du {sname.split('·')[1].strip().lower()} — livrer un incrément démontrable.",
                    status=["COMPLETED", "COMPLETED", "ACTIVE", "PLANNED", "PLANNED"][i]
                    if i < 5 else "PLANNED",
                    start_date=now - timedelta(days=(5 - i) * 14),
                    end_date=now - timedelta(days=(4 - i) * 14),
                    committed_points=random.randint(28, 46),
                    completed_points=random.randint(18, 44),
                    capacity_hours=random.randint(180, 260),
                    risk_score=round(random.uniform(5, 62), 2),
                )
                sprint_by_name[sname] = s

            by_name = {u.full_name: u for u in users.values()}
            for i, (title, lot, ttype, prio, est, status, who, req_skills) in enumerate(spec["tasks"]):
                spent = 0
                if status == "DONE":
                    spent = round(est * random.uniform(0.72, 1.45), 1)
                elif status == "IN_PROGRESS":
                    spent = round(est * random.uniform(0.15, 0.85), 1)
                risk = 0
                if status == "BLOCKED":
                    risk = round(random.uniform(72, 95), 2)
                elif prio == "HIGHEST":
                    risk = round(random.uniform(35, 78), 2)
                elif spent and est and spent > est * 1.3:
                    risk = round(random.uniform(45, 85), 2)
                else:
                    risk = round(random.uniform(2, 40), 2)
                Task.objects.create(
                    project=project,
                    work_package=wp_by_name.get(lot),
                    sprint=random.choice(list(sprint_by_name.values())) if sprint_by_name else None,
                    title=title,
                    description=f"{title}. Description produite par l'Agent 1 lors du cadrage initial.",
                    task_type=ttype, priority=prio, status=status,
                    assignee=by_name.get(who),
                    estimate_hours=est, spent_hours=spent,
                    story_points=round(est / 8, 1),
                    required_skills=req_skills,
                    acceptance_criteria=[
                        "Critère 1 : comportement conforme à la spécification validée",
                        "Critère 2 : couverture de tests >= 70%",
                        "Critère 3 : revue de code validée par un pair",
                    ],
                    risk_score=risk,
                    risk_factors=[
                        {"label": "Dépendance externe", "weight": 0.3},
                        {"label": "Écart estimation", "weight": round(random.uniform(0.1, 0.5), 2)},
                    ] if risk > 40 else [],
                    blocked=(status == "BLOCKED"),
                    blocked_reason="En attente d'une validation métier externe" if status == "BLOCKED" else "",
                    due_date=now + timedelta(days=random.randint(-18, 70)),
                    created_by_agent=True,
                    labels=[lot.lower().replace(" ", "-"), ttype.lower()],
                )

            # agrégats
            project.estimated_effort_hours = sum(float(t.estimate_hours) for t in project.tasks.all())
            project.spent_effort_hours = sum(float(t.spent_hours) for t in project.tasks.all())
            done = project.tasks.filter(status="DONE").count()
            project.progress = round(done / max(1, project.tasks.count()) * 100)
            out.append(project)
            project.save()
        return out

    def _agent_activity(self, users, agents, projects):
        now = timezone.now()
        pm = users["pm@cadria.io"]
        for project in projects:
            # --- Run Agent 1 (SCOPING) réservé -----------------------------
            for i in range(random.randint(2, 4)):
                run = AgentRun.objects.create(
                    project=project, agent=agents["SCOPING"], triggered_by=pm,
                    trigger=random.choice([AgentRun.Trigger.MANUAL, AgentRun.Trigger.PIPELINE]),
                    status=AgentRun.Status.SKIPPED, step="Emplacement réservé — runtime non branché",
                    input_payload={"brief": (project.brief or "")[:400], "constraints": {"deadline": None}},
                    output_payload={"_reserved": True,
                                    "_message": "Emplacement réservé — aucun agent branché.",
                                    "_contract": agents["SCOPING"].output_schema_hint},
                    created_at=now - timedelta(days=random.randint(1, 40), hours=random.randint(0, 12)),
                )
            # --- Proposition en attente de validation ----------------------
            if random.random() < 0.75:
                lots = list(project.work_packages.all())
                tasks_qs = list(project.tasks.all())
                tasks_payload = [
                    {"ref": f"T-{i + 1:03d}", "lot": t.work_package.name if t.work_package else "Lot 1",
                     "title": t.title, "description": t.description[:120], "type": t.task_type,
                     "priority": t.priority, "estimate_hours": float(t.estimate_hours),
                     "story_points": float(t.story_points), "skills": t.required_skills,
                     "acceptance_criteria": t.acceptance_criteria, "risk_score": float(t.risk_score),
                     "sprint": t.sprint.name if t.sprint else "Sprint 1 · Fondations"}
                    for i, t in enumerate(random.sample(tasks_qs, min(8, len(tasks_qs))))
                ]
                proposal = Proposal.objects.create(
                    project=project,
                    title=f"Plan de découpage — {project.name}",
                    summary=(
                        f"Découpage proposé en {len(lots)} lots et {len(tasks_payload)} tâches, "
                        f"pour un effort total de {sum(t['estimate_hours'] for t in tasks_payload):.0f} h. "
                        "Estimations ancrées sur 12 projets similaires (RAG)."
                    ),
                    status=random.choice([Proposal.Status.PENDING, Proposal.Status.PENDING,
                                          Proposal.Status.APPROVED, Proposal.Status.REJECTED]),
                    version=random.choice([1, 2, 2, 3]),
                    lots_payload=[
                        {"name": wp.name, "description": wp.description,
                         "estimate_hours": float(wp.estimated_effort_hours),
                         "confidence": float(wp.confidence), "color": wp.color, "order": wp.order}
                        for wp in lots
                    ],
                    tasks_payload=tasks_payload,
                    sprints_payload=[
                        {"name": s.name, "goal": s.goal, "capacity_hours": float(s.capacity_hours)}
                        for s in project.sprints.all()[:3]
                    ],
                    risks_payload=[
                        {"category": "DELAY", "title": "Risque de dérive planning",
                         "score": round(random.uniform(40, 80), 1)},
                        {"category": "LOAD", "title": "Surcharge de l'équipe",
                         "score": round(random.uniform(30, 70), 1)},
                    ],
                    assumptions=[
                        "Équipe complète et disponible sur toute la durée du projet",
                        "Les accès aux environnements de recette sont fournis sous 5 jours",
                        "Aucune évolution réglementaire majeure pendant le projet",
                    ],
                    total_estimate_hours=sum(t["estimate_hours"] for t in tasks_payload),
                    confidence=round(random.uniform(0.68, 0.95), 2),
                    created_at=now - timedelta(days=random.randint(0, 20)),
                )
                # suggestions d'assignation (Agent 2)
                members = list(project.members.all())
                for t in tasks_payload[:6]:
                    cand = random.choice(members)
                    before = float(sum(
                        float(x.estimate_hours or 0) for x in cand.assigned_tasks.exclude(status="DONE")))
                    after = before + t["estimate_hours"]
                    AssignmentSuggestion.objects.create(
                        proposal=proposal, task_ref=t["ref"], task_title=t["title"],
                        candidate=cand, match_score=round(random.uniform(0.55, 0.98), 3),
                        rationale=(
                            f"Compétences {', '.join(t['skills'][:2]) or 'généralistes'} "
                            f"disponibles — charge après affectation "
                            f"{after / max(1, float(cand.weekly_capacity_hours)) * 100:.0f}% de la capacité."
                        ),
                        matched_skills=t["skills"],
                        workload_before_hours=round(before, 1),
                        workload_after_hours=round(after, 1),
                        accepted=random.choice([True, True, False, None]),
                    )
            # --- Run Agent 3 (RISK) ---------------------------------------
            for i in range(random.randint(3, 6)):
                AgentRun.objects.create(
                    project=project, agent=agents["RISK"],
                    triggered_by=random.choice(list(users.values())),
                    trigger=AgentRun.Trigger.SCHEDULED,
                    status=AgentRun.Status.SKIPPED, step="Collecte des métriques — runtime non branché",
                    input_payload={"window_days": 30, "project_reference": project.reference},
                    output_payload={"_reserved": True},
                    created_at=now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 20)),
                )
            # --- Run Agent 2 (OPS) ----------------------------------------
            for i in range(random.randint(1, 3)):
                AgentRun.objects.create(
                    project=project, agent=agents["OPS"],
                    triggered_by=pm, trigger=AgentRun.Trigger.MANUAL,
                    status=AgentRun.Status.SKIPPED, step="Traduction JSON → appels API (non branché)",
                    input_payload={"provider": project.external_provider, "dry_run": True},
                    output_payload={"_reserved": True},
                    created_at=now - timedelta(days=random.randint(0, 25)),
                )
        # stats agrégées des agents
        for key, agent in agents.items():
            runs = AgentRun.objects.filter(agent=agent)
            agent.total_runs = runs.count()
            agent.successful_runs = runs.filter(status=AgentRun.Status.SUCCEEDED).count()
            agent.failed_runs = runs.filter(status=AgentRun.Status.FAILED).count()
            agent.last_run_at = runs.order_by("-created_at").first().created_at if runs.exists() else None
            agent.save()

    def _risks(self, users, projects):
        now = timezone.now()
        for project in projects:
            tasks = list(project.tasks.all())
            for i in range(random.randint(2, 5)):
                cat, sev, title_tpl, msg, reco, factors = random.choice(RISK_TEMPLATES)
                lot = random.choice(list(project.work_packages.all())).name if project.work_packages.exists() else "Lot 1"
                member = random.choice(list(project.members.all())).full_name
                task = random.choice(tasks) if tasks and random.random() < 0.6 else None
                alert = RiskAlert.objects.create(
                    project=project, task=task,
                    sprint=task.sprint if task and task.sprint else None,
                    category=cat, severity=sev,
                    score=round(random.uniform(45, 92), 2) if sev == "CRITICAL"
                    else round(random.uniform(25, 65), 2) if sev == "WARNING"
                    else round(random.uniform(5, 30), 2),
                    title=title_tpl.format(lot=lot, member=member),
                    message=msg, factors=factors, recommendation=reco,
                    acknowledged=random.random() < 0.4,
                    detected_at=now - timedelta(days=random.randint(0, 25), hours=random.randint(0, 20)),
                )
                if alert.acknowledged:
                    alert.acknowledged_by = random.choice(list(users.values()))
                    alert.acknowledged_at = alert.detected_at + timedelta(hours=random.randint(1, 48))
                    alert.save()

            for _ in range(random.randint(3, 6)):
                body = random.choice(COMMENTS)
                weak = any(k in body.lower() for k in ("bloqué", "en attente", "régression", "impossible"))
                Comment.objects.create(
                    author=random.choice(list(project.members.all())),
                    project=project,
                    task=random.choice(tasks) if tasks and random.random() < 0.5 else None,
                    body=body, weak_signal=weak,
                    sentiment="NEGATIVE" if weak else random.choice(["NEUTRAL", "NEUTRAL", "POSITIVE"]),
                    created_at=now - timedelta(days=random.randint(0, 30)),
                )
            # recalcul du score projet
            open_alerts = project.risk_alerts.filter(acknowledged=False)
            crit = open_alerts.filter(severity="CRITICAL").count()
            warn = open_alerts.filter(severity="WARNING").count()
            overdue = sum(1 for t in tasks if t.is_overdue)
            blocked = project.tasks.filter(blocked=True).exclude(status="DONE").count()
            project.risk_score = min(100, crit * 22 + warn * 9 + overdue * 4 + blocked * 6)
            project.health = (Project.Health.RED if project.risk_score >= 55
                              else Project.Health.AMBER if project.risk_score >= 25
                              else Project.Health.GREEN)
            project.save()

    def _notifications(self, users, projects):
        now = timezone.now()
        user_list = list(users.values())
        for user in user_list:
            for i in range(random.randint(6, 14)):
                cat, level, title_tpl, msg_tpl = random.choice(NOTIFICATION_TEMPLATES)
                project = random.choice(projects)
                task = random.choice(list(project.tasks.all())) if project.tasks.exists() else None
                member = random.choice(user_list).full_name
                created = now - timedelta(days=random.randint(0, 21), hours=random.randint(0, 20))
                read = random.random() < 0.45
                Notification.objects.create(
                    user=user, category=cat, level=level,
                    title=title_tpl.format(project=project.name, member=member),
                    message=msg_tpl.format(project=project.name, member=member,
                                           task=task.title if task else "Tâche",
                                           n=random.randint(8, 42)),
                    link=random.choice([
                        f"/app/projects/{project.pk}",
                        f"/app/projects/{project.pk}/validation",
                        f"/app/projects/{project.pk}/risks",
                        "/app/notifications",
                        f"/app/projects/{project.pk}/agents",
                    ]),
                    entity_type="Project", entity_id=project.pk,
                    read=read, read_at=created + timedelta(hours=1) if read else None,
                    created_at=created,
                    starred=random.random() < 0.12,
                    metadata={"seed": True},
                )
        # diffusion admin
        Notification.objects.create(
            user=None, is_broadcast=True, target_role="ALL",
            category=Notification.Category.SYSTEM, level=Notification.Level.SUCCESS,
            title="Cadria 1.0 est disponible 🎉",
            message="Nouvelle interface, tableau de bord risques et centre de notifications. "
                    "Les agents restent en emplacement réservé jusqu'au branchement du runtime.",
            link="/app/dashboard", created_at=now - timedelta(days=2),
            metadata={"seed": True},
        )

    def _audit(self, users, projects, agents):
        now = timezone.now()
        user_list = list(users.values())
        actions = [
            (AuditLog.Action.CREATE, AuditLog.Severity.NOTICE, "Project", "Création du projet"),
            (AuditLog.Action.UPDATE, AuditLog.Severity.INFO, "Project", "Mise à jour du projet"),
            (AuditLog.Action.AGENT_RUN, AuditLog.Severity.NOTICE, "Project", "Lancement d'un agent"),
            (AuditLog.Action.VALIDATE, AuditLog.Severity.NOTICE, "Proposal", "Validation du plan"),
            (AuditLog.Action.REJECT, AuditLog.Severity.WARNING, "Proposal", "Rejet du plan"),
            (AuditLog.Action.UPDATE, AuditLog.Severity.INFO, "Task", "Changement de statut de tâche"),
            (AuditLog.Action.CREATE, AuditLog.Severity.INFO, "Task", "Création de tâche"),
            (AuditLog.Action.LOGIN, AuditLog.Severity.INFO, "User", "Connexion"),
            (AuditLog.Action.SYNC, AuditLog.Severity.NOTICE, "Project", "Synchronisation Jira/Trello"),
            (AuditLog.Action.ALERT, AuditLog.Severity.WARNING, "RiskAlert", "Alerte accusée réception"),
            (AuditLog.Action.PERMISSION, AuditLog.Severity.WARNING, "User", "Modification de rôle"),
        ]
        for i in range(140):
            action, sev, etype, label = random.choice(actions)
            project = random.choice(projects)
            actor = random.choice(user_list)
            agent_key = random.choice(["", "", "SCOPING", "OPS", "RISK"])
            run = (AgentRun.objects.filter(agent__key=agent_key).order_by("?").first()
                   if agent_key else None)
            AuditLog.objects.create(
                actor=actor, action=action, severity=sev,
                entity_type=etype,
                entity_id=str(project.pk) if etype == "Project" else str(random.randint(1, 200)),
                entity_label=project.name if etype == "Project" else label,
                description=f"{label} — {project.name}" if etype == "Project" else label,
                agent_key=agent_key, run=run,
                correlation_id=f"{random.randint(1000, 9999):04d}-{random.randint(1000, 9999):04d}",
                created_at=now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23)),
                metadata={"seed": True},
            )

    def _integrations(self, users, projects):
        for i, project in enumerate(projects):
            Integration.objects.get_or_create(
                project=project,
                provider=project.external_provider or "JIRA",
                defaults={
                    "owner": project.owner,
                    "name": f"{project.external_provider or 'Jira'} — {project.external_key}",
                    "base_url": f"https://cadria.atlassian.net" if (project.external_provider or "JIRA") == "JIRA"
                    else "https://api.trello.com/1",
                    "board_key": project.external_key,
                    "workspace": "Cadria",
                    "status": Integration.Status.DISCONNECTED,
                    "last_error": "Agent 2 (intégration) non branché." if i % 2 == 0 else "",
                    "auto_sync": True,
                    "sync_interval_minutes": 60,
                },
            )
