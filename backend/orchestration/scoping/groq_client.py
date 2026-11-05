"""
Groq Cloud LLM client — free, no local hardware required.

Groq provides an OpenAI-compatible API at https://api.groq.com/openai/v1/
Free tier: 14,400 requests/day, 30 req/min, ~1-3s latency.

Setup:
  1. Get a free API key at https://console.groq.com
  2. Set env var GROQ_API_KEY=gsk_...
  3. (Optional) Set GROQ_MODEL=llama-3.3-70b-versatile (default)

Usage:
  from .groq_client import chat_completion_json
  response = chat_completion_json(messages=msgs, schema_hint=schema_str)
"""
from __future__ import annotations
import json
import os
import time
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
DEFAULT_TIMEOUT = int(os.environ.get("GROQ_TIMEOUT", "60"))
DEFAULT_MAX_TOKENS = int(os.environ.get("GROQ_MAX_TOKENS", "8000"))

# Fallback models — Groq replaced Llama models with GPT-OSS and Qwen.
# These are the chat models currently available on Groq's free tier.
FALLBACK_MODELS = [
    "openai/gpt-oss-120b",         # Largest, best for structured generation
    "qwen/qwen3.8-27b",            # Good multilingual (French-friendly)
    "openai/gpt-oss-20b",          # Smaller but fast
    "allam-2-7b",                  # Last resort
]


class GroqError(Exception):
    """Raised when the Groq API call fails."""


def _get_api_key() -> str:
    """Get the Groq API key from multiple sources (in order of priority):
    1. OS environment variable (os.environ)
    2. Django settings (settings.GROQ_API_KEY)
    3. .env file on disk (read directly — no python-dotenv needed)
    """
    # 1. Try OS environment
    key = os.environ.get("GROQ_API_KEY") or os.environ.get("LLM_API_KEY", "")
    
    # 2. Try Django settings
    if not key:
        try:
            from django.conf import settings
            key = getattr(settings, "GROQ_API_KEY", "") or ""
        except Exception:
            pass

    # 3. Read .env file directly as last resort
    if not key:
        try:
            from pathlib import Path
            # Try backend/.env (next to manage.py)
            env_candidates = [
                Path(__file__).resolve().parent.parent.parent.parent / ".env",  # backend/.env
                Path.cwd() / ".env",  # current working directory
                Path(__file__).resolve().parent.parent.parent / ".env",  # config/.env
            ]
            for env_path in env_candidates:
                if env_path.exists():
                    for line in env_path.read_text().splitlines():
                        line = line.strip()
                        if line.startswith("GROQ_API_KEY=") and not line.startswith("#"):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
                    if key:
                        logger.info("Groq API key loaded from %s", env_path)
                        break
        except Exception as e:
            logger.warning("Failed to read .env file: %s", e)

    if not key:
        raise GroqError(
            "GROQ_API_KEY not set. Tried: os.environ, Django settings, backend/.env file. "
            "Get a free key at https://console.groq.com and add GROQ_API_KEY=gsk_... to backend/.env"
        )
    return key


def chat_completion_json(
    messages: list[dict[str, str]],
    schema_hint: str = "",
    model: str | None = None,
    timeout: int | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.4,
    max_retries: int = 1,
) -> dict[str, Any]:
    """
    Call Groq chat completions API and return the parsed JSON response.

    Forces JSON output via `response_format: {"type": "json_object"}`.

    Returns:
        {
            "content": str,        # raw LLM response (JSON string)
            "tokens_in": int,
            "tokens_out": int,
            "latency_ms": int,
            "model": str,
        }

    Raises:
        GroqError: if the API call fails after retries.
    """
    api_key = _get_api_key()
    model = model or DEFAULT_MODEL
    timeout = timeout or DEFAULT_TIMEOUT
    max_tokens = max_tokens or DEFAULT_MAX_TOKENS

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Inject schema hint into the system message if provided
    sys_msg = next((m for m in messages if m["role"] == "system"), None)
    if sys_msg and schema_hint:
        sys_msg["content"] = sys_msg["content"] + "\n\nSchéma JSON attendu:\n" + schema_hint

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    last_error: str | None = None

    # Try the primary model first, then fallback models if it returns 404
    models_to_try = [model] + [m for m in FALLBACK_MODELS if m != model]

    for current_model in models_to_try:
        body["model"] = current_model
        for attempt in range(max_retries + 1):
            start = time.monotonic()
            try:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(
                        f"{GROQ_BASE_URL}/chat/completions",
                        headers=headers,
                        json=body,
                    )
                latency_ms = int((time.monotonic() - start) * 1000)

                if resp.status_code == 429:
                    # Rate limited — wait and retry
                    retry_after = float(resp.headers.get("retry-after", "2"))
                    logger.warning("Groq rate limited, retrying after %ss", retry_after)
                    if attempt < max_retries:
                        time.sleep(retry_after)
                        continue
                    raise GroqError(f"Groq rate limited after {max_retries} retries")

                if resp.status_code == 404 or (
                    resp.status_code == 400 and "decommissioned" in resp.text.lower()
                ):
                    # Model not found or decommissioned — try next fallback model
                    last_error = f"HTTP {resp.status_code}: model '{current_model}' unavailable"
                    logger.warning("Groq model '%s' unavailable, trying next...", current_model)
                    break  # break inner loop, try next model

                resp.raise_for_status()
                data = resp.json()

                choice = data["choices"][0]
                content = choice["message"]["content"] or ""
                usage = data.get("usage", {})

                if current_model != model:
                    logger.info("Groq call succeeded with fallback model: %s", current_model)

                return {
                    "content": content,
                    "tokens_in": usage.get("prompt_tokens", 0),
                    "tokens_out": usage.get("completion_tokens", 0),
                    "latency_ms": latency_ms,
                    "model": current_model,
                }

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
                logger.warning("Groq HTTP error (attempt %d): %s", attempt + 1, last_error)
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                # Don't try next model on non-404 errors
                raise GroqError(last_error) from e
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_error = f"Network error: {e}"
                logger.warning("Groq network error (attempt %d): %s", attempt + 1, last_error)
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise GroqError(last_error) from e

    raise GroqError(last_error or "All models failed — no Groq model available")
