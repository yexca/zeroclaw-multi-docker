"""LLM-backed prompt template generation helpers."""

from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from typing import Any

try:
    from config_store import ConfigError, item_id
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from .config_store import ConfigError, item_id


DEFAULT_AI_FILL_INSTRUCTION = """You are helping create ZeroClaw workspace prompt template files.

Generate concise, practical Markdown for the selected files.
Preserve ZeroClaw file roles:
- AGENTS.md: session startup rules and file-reading behavior
- SOUL.md: agent personality, voice, boundaries
- TOOLS.md: local tools, skills, operating conventions
- IDENTITY.md: stable identity facts
- USER.md: user profile, preferences, relationship context
- MEMORY.md: long-term memory seeds
- HEARTBEAT.md: periodic heartbeat tasks; comments are allowed
- PROACTIVE.md: optional proactive sidecar notes and outbound judgment

Do not include secrets.
Keep placeholders such as {agent}, {user}, {tz}, and {comm_style} when useful.
Return only a JSON object mapping file names to Markdown strings."""

SUPPORTED_WIRE_APIS = {"chat_completions", "responses"}


class PromptTemplateAiFiller:
    def fill(self, config: dict[str, Any], payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ConfigError("invalid_payload", "AI fill payload must be an object.")
        profile_id = str(payload.get("llm_profile") or "").strip()
        if not profile_id:
            raise ConfigError("missing_llm_profile", "Choose an LLM profile before generating prompt files.")
        profile = self._find_llm_profile(config, profile_id)
        target_files = self._safe_file_names(payload.get("files"), "files")
        if not target_files:
            raise ConfigError("missing_files", "Choose at least one file to generate.")
        reference_files = self._reference_files(payload.get("reference_files"), target_files)
        instruction = str(payload.get("instruction") or DEFAULT_AI_FILL_INSTRUCTION).strip()
        description = str(payload.get("description") or "").strip()
        if not description:
            raise ConfigError("missing_description", "Describe the agent before generating prompt files.")
        current_files = payload.get("current_files") if isinstance(payload.get("current_files"), dict) else {}
        messages = self._messages(instruction, description, target_files, reference_files, current_files)
        text = self._call_llm(profile, messages)
        generated = self._parse_generated_files(text, target_files)
        return {"files": generated, "generated_files": list(generated.keys())}

    def _find_llm_profile(self, config: dict[str, Any], profile_id: str) -> dict[str, Any]:
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        llm_profiles = profiles.get("llm") if isinstance(profiles.get("llm"), list) else []
        for profile in llm_profiles:
            if isinstance(profile, dict) and item_id(profile) == profile_id:
                return profile
        raise ConfigError("not_found", "LLM profile was not found.", {"id": profile_id}, 404)

    def _safe_file_names(self, value: Any, field: str) -> list[str]:
        if not isinstance(value, list):
            raise ConfigError("invalid_files", f"{field} must be a list of workspace file names.")
        result: list[str] = []
        for item in value:
            name = str(item or "").strip()
            if not self._is_safe_file_name(name):
                raise ConfigError("invalid_files", "File names must be plain workspace file names.", {"file": name})
            if name not in result:
                result.append(name)
        return result

    def _reference_files(self, value: Any, target_files: list[str]) -> list[str]:
        if value is None:
            return []
        return [name for name in self._safe_file_names(value, "reference_files") if name in target_files]

    def _is_safe_file_name(self, name: str) -> bool:
        return bool(name and len(name) <= 128 and ".." not in name and re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", name))

    def _messages(
        self,
        instruction: str,
        description: str,
        target_files: list[str],
        reference_files: list[str],
        current_files: dict[str, Any],
    ) -> list[dict[str, str]]:
        references = {name: str(current_files.get(name) or "") for name in reference_files}
        user_payload = {
            "agent_description": description,
            "generate_files": target_files,
            "reference_files": references,
            "output_contract": {
                "type": "json_object",
                "keys": target_files,
                "values": "Markdown content strings",
            },
        }
        return [
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
        ]

    def _call_llm(self, profile: dict[str, Any], messages: list[dict[str, str]]) -> str:
        wire_api = str(profile.get("wire_api") or "chat_completions")
        if wire_api not in SUPPORTED_WIRE_APIS:
            raise ConfigError("unsupported_wire_api", "AI fill supports chat_completions and responses profiles only.", {"wire_api": wire_api})
        base_url = str(profile.get("base_url") or "").rstrip("/")
        if not base_url:
            raise ConfigError("missing_base_url", "LLM profile requires a base URL for AI fill.")
        model = str(profile.get("model") or "").strip()
        if not model:
            raise ConfigError("missing_model", "LLM profile requires a model for AI fill.")
        timeout = int(profile.get("timeout_secs") or 120)
        payload = self._request_payload(wire_api, model, messages, profile)
        endpoint = f"{base_url}/chat/completions" if wire_api == "chat_completions" else f"{base_url}/responses"
        headers = self._headers(profile)
        request = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ConfigError("llm_request_failed", "LLM provider rejected the AI fill request.", {"status": exc.code, "body": body}, 502) from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
            raise ConfigError("llm_request_failed", "Unable to reach the LLM provider.", {"reason": str(exc)}, 502) from exc
        except json.JSONDecodeError as exc:
            raise ConfigError("invalid_llm_response", "LLM provider returned invalid JSON.", {"error": str(exc)}, 502) from exc
        return self._extract_text(wire_api, data)

    def _request_payload(self, wire_api: str, model: str, messages: list[dict[str, str]], profile: dict[str, Any]) -> dict[str, Any]:
        extra = profile.get("provider_extra") if isinstance(profile.get("provider_extra"), dict) else {}
        payload: dict[str, Any]
        if wire_api == "chat_completions":
            payload = {
                "model": model,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
        else:
            payload = {
                "model": model,
                "input": messages,
                "text": {"format": {"type": "json_object"}},
            }
        if isinstance(profile.get("temperature"), (int, float)):
            payload["temperature"] = profile["temperature"]
        if isinstance(profile.get("max_tokens"), int):
            payload["max_output_tokens" if wire_api == "responses" else "max_tokens"] = profile["max_tokens"]
        payload.update(extra)
        return payload

    def _headers(self, profile: dict[str, Any]) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = str(profile.get("api_key") or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        extra_headers = profile.get("extra_headers")
        if isinstance(extra_headers, dict):
            for key, value in extra_headers.items():
                if value is not None:
                    headers[str(key)] = str(value)
        return headers

    def _extract_text(self, wire_api: str, data: Any) -> str:
        if not isinstance(data, dict):
            raise ConfigError("invalid_llm_response", "LLM provider response must be an object.", status=502)
        if wire_api == "chat_completions":
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message") if isinstance(choices[0], dict) else {}
                content = message.get("content") if isinstance(message, dict) else ""
                if isinstance(content, str) and content.strip():
                    return content
        text = data.get("output_text")
        if isinstance(text, str) and text.strip():
            return text
        output = data.get("output")
        if isinstance(output, list):
            chunks: list[str] = []
            for item in output:
                content = item.get("content") if isinstance(item, dict) else None
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            chunks.append(part["text"])
            if chunks:
                return "\n".join(chunks)
        raise ConfigError("invalid_llm_response", "LLM provider response did not contain generated text.", status=502)

    def _parse_generated_files(self, text: str, target_files: list[str]) -> dict[str, str]:
        raw = text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError("invalid_ai_json", "AI fill response was not valid JSON.", {"error": str(exc)}, 502) from exc
        if not isinstance(parsed, dict):
            raise ConfigError("invalid_ai_json", "AI fill response must be a JSON object.", status=502)
        generated = {name: str(parsed[name]) for name in target_files if name in parsed and str(parsed[name]).strip()}
        missing = [name for name in target_files if name not in generated]
        if missing:
            raise ConfigError("missing_ai_files", "AI fill response omitted one or more requested files.", {"files": missing}, 502)
        return generated
