"""Small connectivity checks for LLM profiles."""

from __future__ import annotations

import json
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

try:
    from config_store import ConfigError, item_id
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from .config_store import ConfigError, item_id


UrlOpen = Callable[[Request, float], Any]


class LlmProfileTester:
    def __init__(self, opener: UrlOpen | None = None):
        self.opener = opener or (lambda request, timeout: urlopen(request, timeout=timeout))

    def test_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(profile, dict):
            raise ConfigError("invalid_payload", "LLM profile test payload must be an object.", status=400)
        profile_id = item_id(profile) or ""
        wire_api = str(profile.get("wire_api") or "chat_completions")
        base_url = self.base_url(profile)
        model = str(profile.get("model") or "").strip()
        if not model:
            raise ConfigError("missing_model", "LLM profile test requires a model.", {"profile": profile_id}, 422)
        if wire_api not in {"chat_completions", "responses"}:
            raise ConfigError("unsupported_wire_api", "LLM profile test supports chat_completions and responses.", {"wire_api": wire_api}, 422)

        url = self.endpoint_url(base_url, wire_api)
        payload = self.payload_for(wire_api, model)
        headers = self.headers_for(profile)
        timeout = min(max(int(profile.get("timeout_secs") or profile.get("timeout") or 30), 1), 30)
        started = time.monotonic()
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with self.opener(request, timeout) as response:
                body = response.read()
                status = int(getattr(response, "status", 200) or 200)
        except HTTPError as exc:
            raise ConfigError(
                "llm_test_http_error",
                self.safe_error_message(exc),
                {"status": exc.code, "base_url": base_url, "model": model, "wire_api": wire_api},
                502,
            ) from exc
        except URLError as exc:
            raise ConfigError(
                "llm_test_connection_error",
                "Could not reach the LLM provider.",
                {"reason": str(exc.reason), "base_url": base_url, "model": model, "wire_api": wire_api},
                502,
            ) from exc
        except TimeoutError as exc:
            raise ConfigError("llm_test_timeout", "LLM profile test timed out.", {"timeout_secs": timeout}, 504) from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": True,
            "profile": profile_id,
            "provider_family": profile.get("provider_family") or profile.get("family") or "",
            "wire_api": wire_api,
            "model": model,
            "status": status,
            "latency_ms": latency_ms,
            "message": "LLM profile is reachable.",
            "preview": self.extract_preview(body, wire_api),
        }

    def base_url(self, profile: dict[str, Any]) -> str:
        family = str(profile.get("provider_family") or profile.get("family") or "openai")
        base_url = str(profile.get("base_url") or "").strip()
        if not base_url:
            if family == "ollama":
                base_url = "http://localhost:11434/v1"
            else:
                base_url = "https://api.openai.com/v1"
        return base_url.rstrip("/") + "/"

    def endpoint_url(self, base_url: str, wire_api: str) -> str:
        endpoint = "responses" if wire_api == "responses" else "chat/completions"
        return urljoin(base_url, endpoint)

    def headers_for(self, profile: dict[str, Any]) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        extra = profile.get("extra_headers") if isinstance(profile.get("extra_headers"), dict) else {}
        for key, value in extra.items():
            if value is not None:
                headers[str(key)] = str(value)
        api_key = str(profile.get("api_key") or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def payload_for(self, wire_api: str, model: str) -> dict[str, Any]:
        if wire_api == "responses":
            return {"model": model, "input": "Reply with exactly: ok", "max_output_tokens": 8, "temperature": 0}
        return {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
            "max_tokens": 8,
            "temperature": 0,
        }

    def extract_preview(self, body: bytes, wire_api: str) -> str:
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ""
        if wire_api == "responses":
            text = data.get("output_text")
            if isinstance(text, str):
                return text[:120]
        choices = data.get("choices") if isinstance(data, dict) else None
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else {}
            content = message.get("content") if isinstance(message, dict) else ""
            if isinstance(content, str):
                return content[:120]
        return ""

    def safe_error_message(self, exc: HTTPError) -> str:
        try:
            data = exc.read(4096)
            parsed = json.loads(data.decode("utf-8"))
            error = parsed.get("error") if isinstance(parsed, dict) else None
            message = error.get("message") if isinstance(error, dict) else parsed.get("message")
            if isinstance(message, str) and message:
                return message
        except Exception:
            pass
        if exc.code in {401, 403}:
            return "Authentication failed. Check the API key and provider permissions."
        return "LLM provider returned an error."
