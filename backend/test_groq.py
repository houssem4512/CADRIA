"""
Test script for Groq API — run from backend folder:
    python test_groq.py
"""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import django
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")

print("=" * 60)
print("TEST 1: Check API key")
print("=" * 60)

try:
    from orchestration.scoping.groq_client import _get_api_key
    key = _get_api_key()
    print(f"OK - Key found: {key[:20]}...")
except Exception as e:
    print(f"FAIL - {e}")
    sys.exit(1)

print()
print("=" * 60)
print("TEST 2: List available Groq models")
print("=" * 60)

try:
    import httpx
    resp = httpx.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=15,
    )
    if resp.status_code == 200:
        models = resp.json().get("data", [])
        print(f"Available models ({len(models)}):")
        for m in models:
            print(f"  - {m['id']}")
    else:
        print(f"Failed to list models: HTTP {resp.status_code}")
except Exception as e:
    print(f"Failed: {e}")

print()
print("=" * 60)
print("TEST 3: Call Groq API (with model auto-fallback)")
print("=" * 60)

try:
    from orchestration.scoping.groq_client import chat_completion_json, GroqError
    result = chat_completion_json(
        messages=[
            {"role": "system", "content": "You return JSON only."},
            {"role": "user", "content": 'Return this JSON: {"test": "hello", "number": 42}'},
        ],
        schema_hint='{"test": "string", "number": "int"}',
    )
    print("OK - GROQ WORKS!")
    print(f"  Tokens in:  {result['tokens_in']}")
    print(f"  Tokens out: {result['tokens_out']}")
    print(f"  Latency:    {result['latency_ms']}ms")
    print(f"  Model:      {result['model']}")
    print(f"  Response:   {result['content'][:300]}")
except GroqError as e:
    print(f"FAIL - GROQ ERROR: {e}")
except Exception as e:
    print(f"FAIL - OTHER ERROR: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("TEST 4: Check RAG model")
print("=" * 60)

try:
    from orchestration.scoping.rag import _get_model
    model = _get_model(timeout_skip=False)
    if model is not None:
        vec = model.encode("test sentence", normalize_embeddings=True)
        print(f"OK - Model loaded, dimension: {vec.shape[0]}")
    else:
        print("SKIP - Model not loaded")
except Exception as e:
    print(f"FAIL - {e}")

print()
print("=" * 60)
print("DONE")
print("=" * 60)
