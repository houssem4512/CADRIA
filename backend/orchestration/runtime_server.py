"""
Serveur HTTP minimal du runtime d'agents Cadria.

Lancement depuis `backend/` :

    python -m orchestration.runtime_server

Endpoints (POST, corps `{"payload": {...}, "correlation_id": "..."}`) :

    /scoping/run
    /ops/run
    /risk/run
    /health

Aucune dépendance externe : uniquement la bibliothèque standard.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .engines import execute

ROUTES = {
    "/scoping/run": "SCOPING",
    "/ops/run": "OPS",
    "/risk/run": "RISK",
}


class RuntimeHandler(BaseHTTPRequestHandler):
    server_version = "CadriaAgentRuntime/1.0"

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") in ("/health", ""):
            self._send(200, {"status": "ok", "service": "cadria-agent-runtime",
                             "agents": sorted(ROUTES.values())})
        else:
            self._send(404, {"status": "FAILED", "error": "Route inconnue"})

    def do_POST(self):  # noqa: N802
        key = ROUTES.get(self.path.rstrip("/"))
        if key is None:
            self._send(404, {"status": "FAILED", "error": "Route inconnue"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            payload = body.get("payload") or body
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"status": "FAILED", "error": f"JSON invalide: {exc}"})
            return
        self._send(200, execute(key, payload))

    def _send(self, code: int, data: dict) -> None:
        raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        print(f"[runtime] {self.address_string()} {fmt % args}")


def main() -> None:
    host = os.environ.get("AGENT_RUNTIME_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENT_RUNTIME_PORT", "8100"))
    server = ThreadingHTTPServer((host, port), RuntimeHandler)
    print(f"Runtime d'agents Cadria à l'écoute sur http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
