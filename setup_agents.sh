#!/usr/bin/env bash
# ============================================================================
# Cadria — Agents setup script
# Installs deps, runs migrations, trains XGBoost model, seeds demo data
# ============================================================================
set -e

echo "=== 1. Installing Python dependencies ==="
cd backend
pip install -r requirements.txt

echo ""
echo "=== 2. Running Django migrations ==="
python manage.py migrate

echo ""
echo "=== 3. Seeding demo data (admin@cadria.io / Cadria@2026) ==="
python manage.py seed_demo

echo ""
echo "=== 4. Training XGBoost risk model (Agent 3) ==="
python manage.py shell -c "
from orchestration.risk.scorer import train_model
path = train_model()
print(f'Model saved to: {path}')
"

echo ""
echo "=== 5. Enabling agents ==="
echo "Set these env vars in your .env before running the server:"
echo ""
echo "  AGENT_RUNTIME_ENABLED=True"
echo "  GROQ_API_KEY=gsk_xxx  (get a free key at https://console.groq.com)"
echo "  GROQ_MODEL=llama-3.3-70b-versatile"
echo ""
echo "If GROQ_API_KEY is not set, Agent 1 will use the deterministic fallback."

echo ""
echo "=== Done! Now start the backend ==="
echo "  cd backend"
echo "  python manage.py runserver 0.0.0.0:8000"
echo ""
echo "And in another terminal, start the Celery worker (for weekly Risk agent):"
echo "  cd backend"
echo "  celery -A config worker -l info"
echo "  celery -A config beat -l info   # separate terminal for the scheduler"
