#!/usr/bin/env python3
"""Minimal WebUI manager backend for the architecture skeleton stage."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = APP_ROOT / "frontend"


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class ManagerHandler(BaseHTTPRequestHandler):
    server_version = "ZeroClawManager/0.1"

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/healthz":
            json_response(self, 200, {"ok": True, "service": "zeroclaw-manager"})
            return

        if path == "/api/status":
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "stage": "architecture-skeleton",
                    "dockerApiUrl": os.getenv("DOCKER_API_URL", ""),
                    "managerConfigPath": os.getenv("MANAGER_CONFIG_PATH", ""),
                    "managerSecretsPath": os.getenv("MANAGER_SECRETS_PATH", ""),
                    "generatedConfigDir": os.getenv("GENERATED_CONFIG_DIR", ""),
                },
            )
            return

        self.serve_frontend(path)

    def serve_frontend(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (FRONTEND_DIR / relative).resolve()

        if FRONTEND_DIR not in target.parents and target != FRONTEND_DIR:
            self.send_error(403)
            return

        if not target.exists() or not target.is_file():
            self.send_error(404)
            return

        content_type = "text/html; charset=utf-8"
        if target.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif target.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"

        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = os.getenv("MANAGER_BIND_HOST", "0.0.0.0")
    port = int(os.getenv("MANAGER_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), ManagerHandler)
    print(f"ZeroClaw manager listening on {host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
