#!/usr/bin/env python3
"""ZeroClaw WebUI manager backend API."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from config_store import ConfigError, ConfigStore, redact, to_json
from docker_controller import FakeDockerController


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
FRONTEND_DIR = APP_ROOT / "frontend"


def env_path(name: str, default: Path) -> Path:
    return Path(os.getenv(name, str(default))).resolve()


def build_store() -> ConfigStore:
    config_path = env_path("MANAGER_CONFIG_PATH", REPO_ROOT / "config" / "manager.yaml")
    example_path = env_path("MANAGER_CONFIG_EXAMPLE_PATH", REPO_ROOT / "config" / "manager.example.yaml")
    generated_dir = env_path("GENERATED_CONFIG_DIR", REPO_ROOT / "config" / "generated")
    return ConfigStore(config_path, example_path, generated_dir)


STORE = build_store()
DOCKER = FakeDockerController(os.getenv("DOCKER_API_URL", "http://docker-socket-proxy:2375"))


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def success(handler: BaseHTTPRequestHandler, status: int, data: object, meta: dict | None = None) -> None:
    payload: dict[str, object] = {"ok": True, "data": data}
    if meta:
        payload["meta"] = meta
    json_response(handler, status, payload)


def error_response(
    handler: BaseHTTPRequestHandler,
    status: int,
    code: str,
    message: str,
    details: dict | None = None,
) -> None:
    json_response(
        handler,
        status,
        {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        },
    )


class ManagerHandler(BaseHTTPRequestHandler):
    server_version = "ZeroClawManager/0.3"

    def log_message(self, format: str, *args: object) -> None:
        message = format % args
        print(f"{self.address_string()} - {message}", file=sys.stderr, flush=True)

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_PUT(self) -> None:
        self._handle("PUT")

    def do_DELETE(self) -> None:
        self._handle("DELETE")

    def _handle(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if method == "GET" and path == "/healthz":
                success(self, 200, {"service": "zeroclaw-manager", "status": "ok"})
                return
            if path.startswith("/api/"):
                self.route_api(method, path, parse_qs(parsed.query))
                return
            if method != "GET":
                error_response(self, 405, "method_not_allowed", "Only GET is supported for static assets.")
                return
            self.serve_frontend(path)
        except ConfigError as exc:
            error_response(self, exc.status, exc.code, exc.message, exc.details)
        except json.JSONDecodeError as exc:
            error_response(self, 400, "invalid_json", "Request body must be valid JSON.", {"error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive API boundary
            error_response(self, 500, "internal_error", "Unexpected manager backend error.", {"type": type(exc).__name__})

    def route_api(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        segments = [segment for segment in path.split("/") if segment]

        if method == "GET" and path == "/api/health":
            success(self, 200, {"service": "zeroclaw-manager", "status": "ok"})
            return

        if method == "GET" and path == "/api/status":
            success(
                self,
                200,
                {
                    "stage": "manager-backend-foundation",
                    "dockerApiUrl": os.getenv("DOCKER_API_URL", ""),
                    "managerConfigPath": str(STORE.config_path),
                    "generatedConfigDir": str(STORE.generated_dir),
                },
            )
            return

        if method == "GET" and path == "/api/webui/defaults":
            config = STORE.load()
            success(self, 200, config.get("webui", {}))
            return

        if path == "/api/config":
            if method == "GET":
                success(self, 200, STORE.load())
                return
            if method == "PUT":
                payload = self.read_json()
                print(f"config write requested: {to_json(payload)}", file=sys.stderr, flush=True)
                success(self, 200, STORE.update_full_config(payload))
                return

        if path == "/api/export" and method == "POST":
            success(self, 200, STORE.export(self.read_optional_json()))
            return

        if len(segments) >= 3 and segments[:2] == ["api", "profiles"]:
            self.route_collection(method, "profiles", segments[2:], query)
            return

        if len(segments) >= 2 and segments[:2] == ["api", "prompt-templates"]:
            self.route_collection(method, "prompt_templates", segments[2:], query)
            return

        if len(segments) >= 2 and segments[:2] == ["api", "agents"]:
            self.route_agents(method, segments[2:], query)
            return

        error_response(self, 404, "not_found", "API route was not found.", {"path": path, "method": method})

    def route_collection(self, method: str, group: str, segments: list[str], query: dict[str, list[str]]) -> None:
        kind = "prompt_templates" if group == "prompt_templates" else segments[0]
        remaining = segments if group == "prompt_templates" else segments[1:]

        if kind not in {"llm", "matrix", "mcp", "prompt_templates"}:
            error_response(self, 404, "not_found", "Collection was not found.", {"kind": kind})
            return

        if not remaining:
            if method == "GET":
                success(self, 200, STORE.list_collection(kind))
                return
            if method == "POST":
                success(self, 201, STORE.create_item(kind, self.read_json()))
                return

        if len(remaining) == 1:
            identifier = remaining[0]
            if method == "PUT":
                success(self, 200, STORE.update_item(kind, identifier, self.read_json()))
                return
            if method == "DELETE":
                success(self, 200, STORE.delete_item(kind, identifier))
                return

        error_response(self, 405, "method_not_allowed", "Unsupported collection operation.", {"method": method})

    def route_agents(self, method: str, segments: list[str], query: dict[str, list[str]]) -> None:
        if not segments:
            if method == "GET":
                success(self, 200, STORE.list_agents())
                return
            if method == "POST":
                success(self, 201, STORE.create_agent(self.read_json()))
                return

        if len(segments) == 1:
            identifier = segments[0]
            if method == "GET":
                success(self, 200, STORE.get_agent(identifier))
                return
            if method == "PUT":
                success(self, 200, STORE.update_agent(identifier, self.read_json()))
                return
            if method == "DELETE":
                success(self, 200, STORE.delete_agent(identifier))
                return

        if len(segments) == 2:
            identifier, action = segments
            agent = STORE.get_agent(identifier)
            if method == "POST" and action == "validate":
                success(self, 200, STORE.validate_agent(identifier))
                return
            if method == "POST" and action in {"start", "stop", "restart"}:
                success(self, 202, getattr(DOCKER, action)(agent))
                return
            if method == "GET" and action == "status":
                success(self, 200, DOCKER.status(agent))
                return
            if method == "GET" and action == "logs":
                tail = self.parse_tail(query)
                success(self, 200, DOCKER.logs(agent, tail=tail))
                return

        error_response(self, 405, "method_not_allowed", "Unsupported agent operation.", {"method": method})

    def parse_tail(self, query: dict[str, list[str]]) -> int:
        try:
            return max(1, min(2000, int((query.get("tail") or ["200"])[0])))
        except ValueError:
            return 200

    def read_json(self) -> object:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body)
        print(f"{self.command} {self.path} body={json.dumps(redact(payload), sort_keys=True)}", file=sys.stderr, flush=True)
        return payload

    def read_optional_json(self) -> object | None:
        if int(self.headers.get("Content-Length", "0")) <= 0:
            return None
        return self.read_json()

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
        elif target.suffix in {".js", ".mjs"}:
            content_type = "application/javascript; charset=utf-8"
        elif target.suffix == ".json":
            content_type = "application/json; charset=utf-8"

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
