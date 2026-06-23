"""Runtime observability helpers for status, logs, and operation history."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from config_store import item_id, redact
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from .config_store import item_id, redact


SECRET_KEY_WORDS = ("api_key", "token", "password", "recovery_key", "recover_key", "secret", "key")
TOKEN_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)(access[_-]?token|api[_-]?key|password|recovery[_-]?key|secret)=([^\s]+)"),
    re.compile(r"(?i)(Bearer\s+)([A-Za-z0-9_\-\.=]{12,})"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_config_hash(value: Any) -> str:
    import hashlib

    encoded = json.dumps(redact(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def collect_secret_values(value: Any) -> set[str]:
    secrets: set[str] = set()

    def visit(node: Any, key: str = "") -> None:
        if isinstance(node, dict):
            for child_key, child in node.items():
                visit(child, str(child_key))
            return
        if isinstance(node, list):
            for child in node:
                visit(child, key)
            return
        if isinstance(node, str) and node and any(word in key.lower() for word in SECRET_KEY_WORDS):
            if len(node) >= 4 and node != "[REDACTED]":
                secrets.add(node)

    visit(value)
    return secrets


def redact_text(text: str, config: dict[str, Any] | None = None) -> str:
    redacted = text
    for secret in sorted(collect_secret_values(config or {}), key=len, reverse=True):
        redacted = redacted.replace(secret, "[REDACTED]")
    for pattern in TOKEN_PATTERNS:
        if pattern.groups == 2:
            redacted = pattern.sub(
                lambda match: f"{match.group(1)}[REDACTED]"
                if match.group(1).lower().startswith("bearer")
                else f"{match.group(1)}=[REDACTED]",
                redacted,
            )
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redact_lines(lines: list[str], config: dict[str, Any] | None = None) -> list[str]:
    return redact_text("\n".join(lines), config).splitlines()


def normalize_agent_state(status: dict[str, Any]) -> str:
    if status.get("error"):
        return "error"
    raw = str(status.get("state") or "").lower()
    if raw in {"absent", "missing", "not_found"}:
        return "missing"
    if raw in {"created"}:
        return "created"
    if raw in {"running"}:
        health = str(status.get("health_status") or status.get("health") or "").lower()
        return "unhealthy" if health == "unhealthy" else "running"
    if raw in {"exited", "dead", "stopped"}:
        return "stopped"
    if raw in {"restarting"}:
        return "restarting"
    if raw in {"paused"}:
        return "stopped"
    return raw or "error"


def mapped_port(status: dict[str, Any]) -> str:
    ports = status.get("ports") if isinstance(status.get("ports"), dict) else {}
    bindings = ports.get("42617/tcp") if isinstance(ports, dict) else None
    if isinstance(bindings, list) and bindings:
        binding = bindings[0]
        return f"{binding.get('HostIp', '')}:{binding.get('HostPort', '')}".strip(":")
    if status.get("host_port"):
        return f"127.0.0.1:{status['host_port']}"
    return ""


def enrich_status(status: dict[str, Any], expected_hash: str | None = None, latest_export_time: str | None = None) -> dict[str, Any]:
    enriched = dict(status)
    if expected_hash and "expected_spec_hash" not in enriched:
        enriched["expected_spec_hash"] = expected_hash
    enriched["normalized_state"] = normalize_agent_state(enriched)
    enriched["mapped_port"] = mapped_port(enriched)
    enriched["config_hash"] = enriched.get("expected_spec_hash") or expected_hash or ""
    enriched["container_config_hash"] = enriched.get("spec_hash") or ""
    enriched["needs_rebuild"] = bool(enriched.get("needs_recreate"))
    enriched["latest_export_time"] = latest_export_time or ""
    return enriched


class OperationHistory:
    def __init__(self, path: Path):
        self.path = path

    def append(self, operation: str, agent_id: str | None = None, result: Any | None = None, status: str = "ok") -> dict[str, Any]:
        entry = {
            "timestamp": utc_now(),
            "operation": operation,
            "agent_id": agent_id or "",
            "status": status,
            "result": redact(result or {}),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=True) + "\n")
        return entry

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        entries: list[dict[str, Any]] = []
        for line in lines[-max(1, min(limit, 1000)) :]:
            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    entries.append(payload)
            except json.JSONDecodeError:
                continue
        return entries

    def latest_export_time(self, agent_id: str | None = None) -> str:
        for entry in reversed(self.list(limit=1000)):
            if entry.get("operation") != "export":
                continue
            if agent_id and entry.get("agent_id") not in {"", agent_id}:
                continue
            return str(entry.get("timestamp") or "")
        return ""


def history_from_env(generated_dir: Path) -> OperationHistory:
    path = Path(os.getenv("OPERATION_HISTORY_PATH", str(generated_dir / "operation-history.jsonl"))).resolve()
    return OperationHistory(path)


def agent_identifier(agent: dict[str, Any]) -> str:
    return item_id(agent) or str(agent.get("name") or "")
