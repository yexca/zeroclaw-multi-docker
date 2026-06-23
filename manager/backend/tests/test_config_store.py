from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from manager.backend.config_store import ConfigError, ConfigStore, redact
from manager.backend.docker_controller import FakeDockerController


class ConfigStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.config_path = root / "manager.yaml"
        self.example_path = root / "manager.example.yaml"
        self.generated_dir = root / "generated"
        self.example_path.write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "profiles": {
                        "llm": [{"id": "deepseek-text", "model": "deepseek-chat"}],
                        "matrix": [{"id": "matrix-main", "homeserver": "https://matrix.example.com"}],
                        "mcp": [{"id": "gateway", "enabled": True}],
                    },
                    "prompt_templates": [{"id": "default", "files": ["AGENTS.md"]}],
                    "agents": [{"id": "agent1", "enabled": True, "llm_profile": "deepseek-text"}],
                }
            ),
            encoding="utf-8",
        )
        self.store = ConfigStore(self.config_path, self.example_path, self.generated_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_loads_example_and_normalizes_defaults(self) -> None:
        config = self.store.load()

        self.assertEqual(config["webui"]["default_language"], "en")
        self.assertEqual(config["profiles"]["llm"][0]["id"], "deepseek-text")
        self.assertEqual(config["agents"][0]["id"], "agent1")

    def test_profile_crud_is_persisted(self) -> None:
        created = self.store.create_item("llm", {"id": "local", "model": "qwen"})
        updated = self.store.update_item("llm", "local", {"id": "local", "model": "qwen2.5"})
        deleted = self.store.delete_item("llm", "local")

        self.assertEqual(created["model"], "qwen")
        self.assertEqual(updated["model"], "qwen2.5")
        self.assertEqual(deleted["id"], "local")
        self.assertTrue(self.config_path.exists())

    def test_duplicate_item_raises_structured_error(self) -> None:
        with self.assertRaises(ConfigError) as context:
            self.store.create_item("llm", {"id": "deepseek-text"})

        self.assertEqual(context.exception.code, "duplicate_id")
        self.assertEqual(context.exception.status, 409)

    def test_agent_validation_reports_missing_references(self) -> None:
        self.store.create_agent({"id": "agent2", "llm_profile": "missing"})

        result = self.store.validate_agent("agent2")

        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"][0]["field"], "llm_profile")

    def test_export_writes_generated_yaml(self) -> None:
        result = self.store.export({"filename": "resolved.test.yaml"})

        self.assertTrue(Path(result["path"]).exists())
        self.assertEqual(result["config"]["version"], 1)

    def test_redact_masks_sensitive_fields(self) -> None:
        payload = {
            "api_key": "secret",
            "nested": {"matrix_access_token": "token", "plain": "value"},
        }

        self.assertEqual(redact(payload)["api_key"], "[REDACTED]")
        self.assertEqual(redact(payload)["nested"]["matrix_access_token"], "[REDACTED]")
        self.assertEqual(redact(payload)["nested"]["plain"], "value")


class DockerControllerTest(unittest.TestCase):
    def test_fake_controller_returns_stable_operation_shape(self) -> None:
        controller = FakeDockerController("http://docker-socket-proxy:2375")

        result = controller.start({"id": "agent1"})

        self.assertTrue(result["accepted"])
        self.assertEqual(result["operation"], "start")
        self.assertEqual(result["controller"], "fake")


if __name__ == "__main__":
    unittest.main()
