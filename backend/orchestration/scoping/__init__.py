"""
Agent 1 — Scoping.

Lazy-loaded — only imported when dispatch() is called for a SCOPING run.
This prevents import errors if pydantic/httpx/sentence-transformers
aren't installed yet.
"""
def run(run):
    """Lazy entry point — imports the real runner on first call."""
    from .runner import run as _run
    return _run(run)
