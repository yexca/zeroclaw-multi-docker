from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from manager.backend.agent_renderer import AgentRenderer, REQUIRED_ENV_KEYS
from manager.backend.ai_fill import PromptTemplateAiFiller
from manager.backend.config_store import ConfigError, ConfigStore, redact
from manager.backend.config_validator import ConfigValidator
from manager.backend.docker_controller import (
    AGENT_ID_LABEL,
    AGENT_NAME_LABEL,
    MANAGER_LABEL,
    DockerApiError,
    DockerApiController,
    FakeDockerController,
    decode_build_stream,
    decode_docker_log_stream,
)
from manager.backend.observability import OperationHistory, normalize_agent_state, redact_lines
from manager.backend.app import ManagerHandler


class ConfigStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.config_path = root / "manager.yaml"
        self.example_path = root / "manager.example.yaml"
        self.generated_dir = root / "generated"
        templates_dir = root / "templates" / "workspace"
        templates_dir.mkdir(parents=True)
        for filename, content in {
            "AGENTS.md": "# AGENTS.md\n\nDefault Personal Assistant",
            "SOUL.md": "# SOUL.md\n\nDefault soul",
            "TOOLS.md": "# TOOLS.md\n\nDefault tools",
            "IDENTITY.md": "# IDENTITY.md\n\nDefault identity",
            "USER.md": "# USER.md\n\nDefault user",
            "HEARTBEAT.md": "# HEARTBEAT.md\n\n# Keep this file empty",
            "MEMORY.md": "# MEMORY.md\n\nDefault memory",
            "PROACTIVE.md": "# PROACTIVE.md\n\n# Optional proactive service",
        }.items():
            (templates_dir / filename).write_text(content, encoding="utf-8")
        self.write_modular_config(
            {
                "profiles": {
                    "llm": [{"id": "deepseek-text", "model": "deepseek-chat"}],
                    "matrix": [{"id": "matrix-main", "homeserver": "https://matrix.example.com"}],
                    "mcp": [{"id": "gateway", "enabled": True}],
                },
                "prompt_templates": [{"id": "default", "files": {"AGENTS.md": ""}}],
                "agents": [{"id": "agent1", "enabled": True, "llm_profile": "deepseek-text"}],
            },
            self.example_path,
        )
        self.store = ConfigStore(self.config_path, self.example_path, self.generated_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_modular_config(self, payload: dict, root_path: Path | None = None) -> None:
        root = Path(self.temp_dir.name)
        config_root = root / "config"
        modules = {
            "llm_dir": str(config_root / "llm"),
            "vision_dir": str(config_root / "vision"),
            "matrix_dir": str(config_root / "matrix"),
            "mcp_dir": str(config_root / "mcp"),
            "agents_dir": str(config_root / "agents"),
            "prompts_dir": str(config_root / "prompts"),
            "skills_dir": str(config_root / "skills"),
            "secrets_file": str(config_root / "secrets.yaml"),
        }
        root_payload = {
            "version": 2,
            "paths": {"instances_dir": str(root / "instances")},
            "config_modules": modules,
        }
        for key, value in payload.items():
            if key not in {"profiles", "prompt_templates", "agents", "skill_bundles"}:
                root_payload[key] = value
        (root_path or self.config_path).write_text(yaml.safe_dump(root_payload, sort_keys=False), encoding="utf-8")
        profiles = payload.get("profiles") if isinstance(payload.get("profiles"), dict) else {}
        for kind in ("llm", "vision", "matrix", "mcp"):
            for item in profiles.get(kind, []) if isinstance(profiles.get(kind), list) else []:
                directory = Path(modules[f"{kind}_dir"])
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f"{item['id']}.yaml").write_text(yaml.safe_dump(item, sort_keys=False, allow_unicode=True), encoding="utf-8")
        for item in payload.get("agents", []) if isinstance(payload.get("agents"), list) else []:
            directory = Path(modules["agents_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{item['id']}.yaml").write_text(yaml.safe_dump(item, sort_keys=False, allow_unicode=True), encoding="utf-8")
        for item in payload.get("skill_bundles", []) if isinstance(payload.get("skill_bundles"), list) else []:
            directory = Path(modules["skills_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{item['id']}.yaml").write_text(yaml.safe_dump(item, sort_keys=False, allow_unicode=True), encoding="utf-8")
        for template in payload.get("prompt_templates", []) if isinstance(payload.get("prompt_templates"), list) else []:
            prompt_dir = Path(modules["prompts_dir"]) / template["id"]
            prompt_dir.mkdir(parents=True, exist_ok=True)
            files = template.get("files", {})
            manifest_files = {}
            for filename, content in files.items():
                (prompt_dir / filename).write_text(str(content), encoding="utf-8")
                manifest_files[filename] = filename
            manifest = {"id": template["id"], "name": template.get("name", template["id"]), "files": manifest_files}
            (prompt_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def modular_payload(self, payload: dict) -> dict:
        root = Path(self.temp_dir.name)
        config_root = root / "config"
        base = {
            "version": 2,
            "paths": {"instances_dir": str(root / "instances")},
            "config_modules": {
                "llm_dir": str(config_root / "llm"),
                "vision_dir": str(config_root / "vision"),
                "matrix_dir": str(config_root / "matrix"),
                "mcp_dir": str(config_root / "mcp"),
                "agents_dir": str(config_root / "agents"),
                "prompts_dir": str(config_root / "prompts"),
                "skills_dir": str(config_root / "skills"),
                "secrets_file": str(config_root / "secrets.yaml"),
            },
        }
        base.update(payload)
        return base

    def test_loads_example_and_normalizes_defaults(self) -> None:
        config = self.store.load()

        self.assertEqual(config["webui"]["default_language"], "en")
        self.assertEqual(config["profiles"]["llm"][0]["id"], "deepseek-text")
        self.assertEqual(config["agents"][0]["id"], "agent1")

    def test_load_adds_default_prompt_template_when_missing(self) -> None:
        self.config_path.write_text(
            yaml.safe_dump(self.modular_payload({"prompt_templates": []}), sort_keys=False),
            encoding="utf-8",
        )

        config = self.store.load()
        template = config["prompt_templates"][0]

        self.assertEqual(template["id"], "default")
        self.assertIn("AGENTS.md", template["files"])
        self.assertIn("SOUL.md", template["files"])
        self.assertIn("HEARTBEAT.md", template["files"])
        self.assertIn("PROACTIVE.md", template["files"])
        self.assertIn("Personal Assistant", template["files"]["AGENTS.md"])
        self.assertIn("Keep this file empty", template["files"]["HEARTBEAT.md"])
        self.assertIn("optional proactive service", template["files"]["PROACTIVE.md"])

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
        self.assertIn("not_found", {entry["code"] for entry in result["errors"]})

    def test_export_writes_generated_yaml(self) -> None:
        result = self.store.export({"filename": "resolved.test.yaml"})

        self.assertTrue(Path(result["path"]).exists())
        self.assertEqual(result["config"]["version"], 2)

    def test_legacy_single_file_config_requires_migration(self) -> None:
        self.config_path.write_text(yaml.safe_dump({"version": 1, "agents": []}), encoding="utf-8")

        with self.assertRaises(ConfigError) as context:
            self.store.load()

        self.assertEqual(context.exception.code, "legacy_config_requires_migration")

    def test_resource_decisions_are_persisted(self) -> None:
        self.store.update_resource_decision("ignore", "volume", "zeroclaw-old-data")
        self.store.update_resource_decision("adopt", "container", "zeroclaw-old-agent")

        decisions = self.store.load_resource_decisions()

        self.assertEqual(decisions["ignored"][0]["name"], "zeroclaw-old-data")
        self.assertEqual(decisions["adopted"][0]["name"], "zeroclaw-old-agent")

        self.store.update_resource_decision("clear", "volume", "zeroclaw-old-data")
        decisions = self.store.load_resource_decisions()
        self.assertEqual(decisions["ignored"], [])

    def test_rotate_matrix_device_id_updates_agent_override(self) -> None:
        self.store.update_full_config(
            self.modular_payload({
                "profiles": {
                    "llm": [{"id": "llm", "provider_family": "ollama", "provider_alias": "local", "model": "qwen"}],
                    "matrix": [{"id": "matrix", "homeserver": "https://matrix.example.com", "access_token": "token", "device_id": "PROFILE_DEVICE"}],
                    "mcp": [],
                },
                "agents": [
                    {
                        "id": "agent1",
                        "host_port": 42641,
                        "llm_profile": "llm",
                        "matrix_profile": "matrix",
                        "matrix": {"user_id": "@agent1:matrix.example.com", "external_peers": ["@you:matrix.example.com"]},
                    }
                ],
            })
        )

        result = self.store.rotate_matrix_device_id("agent1")
        agent = self.store.get_agent("agent1")

        self.assertTrue(result["device_id"].startswith("ZEROCLAW_AGENT1_"))
        self.assertEqual(agent["matrix"]["device_id"], result["device_id"])
        self.assertEqual(result["previous_device_id"], "")

    def test_apply_prompt_template_writes_workspace_files(self) -> None:
        self.store.update_full_config(
            self.modular_payload({
                "prompt_templates": [{"id": "default", "files": {"AGENTS.md": "hello"}}],
                "profiles": {
                    "llm": [{"id": "llm", "provider_family": "ollama", "provider_alias": "local", "model": "qwen"}],
                    "matrix": [{"id": "matrix", "homeserver": "https://matrix.example.com", "access_token": "token"}],
                    "mcp": [],
                },
                "agents": [
                    {
                        "id": "agent1",
                        "host_port": 42641,
                        "llm_profile": "llm",
                        "matrix_profile": "matrix",
                        "prompt_template": "default",

                        "matrix": {"user_id": "@agent1:matrix.example.com", "external_peers": ["@you:matrix.example.com"]},
                    }
                ],
            })
        )

        result = self.store.apply_prompt_template("agent1", {"mode": "overwrite"})

        self.assertIn("AGENTS.md", result["written"])
        self.assertIn("SOUL.md", result["written"])
        self.assertIn("HEARTBEAT.md", result["written"])
        self.assertEqual(
            (Path(self.temp_dir.name) / "instances" / "agent1" / "workspace" / "AGENTS.md").read_text(encoding="utf-8"),
            "hello",
        )

    def test_update_profile_rejects_running_referenced_agent(self) -> None:
        self.store.set_agent_status_provider(lambda _config, agent: {"running": agent.get("id") == "agent1", "state": "running"})

        with self.assertRaises(ConfigError) as context:
            self.store.update_item("llm", "deepseek-text", {"id": "deepseek-text", "model": "updated"})

        self.assertEqual(context.exception.code, "runtime_config_in_use")
        self.assertEqual(context.exception.status, 409)
        self.assertEqual(context.exception.details["agents"][0]["id"], "agent1")

    def test_update_profile_allows_stopped_referenced_agent(self) -> None:
        self.store.set_agent_status_provider(lambda _config, _agent: {"running": False, "state": "exited"})

        result = self.store.update_item("llm", "deepseek-text", {"id": "deepseek-text", "model": "updated"})

        self.assertEqual(result["model"], "updated")

    def test_update_unused_profile_allows_running_other_agent(self) -> None:
        self.store.update_full_config(
            self.modular_payload(
                {
                    "profiles": {
                        "llm": [
                            {"id": "deepseek-text", "provider_family": "openai", "provider_alias": "main", "model": "gpt-4.1"},
                            {"id": "unused", "provider_family": "openai", "provider_alias": "main", "model": "gpt-4.1"},
                        ],
                        "matrix": [{"id": "matrix", "homeserver": "https://matrix.example.com", "access_token": "token"}],
                        "mcp": [],
                    },
                    "agents": [
                        {
                            "id": "agent1",
                            "host_port": 42641,
                            "llm_profile": "deepseek-text",
                            "matrix_profile": "matrix",
                            "matrix": {"user_id": "@agent1:matrix.example.com", "external_peers": ["@you:matrix.example.com"]},
                        }
                    ],
                }
            )
        )
        self.store.set_agent_status_provider(lambda _config, _agent: {"running": True, "state": "running"})

        result = self.store.update_item("llm", "unused", {"id": "unused", "model": "updated"})

        self.assertEqual(result["model"], "updated")

    def test_apply_prompt_template_rejects_running_agent(self) -> None:
        self.store.set_agent_status_provider(lambda _config, _agent: {"running": True, "state": "running"})

        with self.assertRaises(ConfigError) as context:
            self.store.apply_prompt_template("agent1", {"mode": "overwrite"})

        self.assertEqual(context.exception.code, "runtime_workspace_in_use")
        self.assertEqual(context.exception.status, 409)

    def test_agent_workspace_initialized_requires_written_files(self) -> None:
        self.store.update_full_config(
            self.modular_payload({
                "prompt_templates": [{"id": "default", "files": {"AGENTS.md": "hello"}}],
                "profiles": {
                    "llm": [{"id": "llm", "provider_family": "ollama", "provider_alias": "local", "model": "qwen"}],
                    "matrix": [{"id": "matrix", "homeserver": "https://matrix.example.com", "access_token": "token"}],
                    "mcp": [],
                },
                "agents": [
                    {
                        "id": "agent1",
                        "host_port": 42641,
                        "llm_profile": "llm",
                        "matrix_profile": "matrix",
                        "prompt_template": "default",
                        "matrix": {"user_id": "@agent1:matrix.example.com", "external_peers": ["@you:matrix.example.com"]},
                    }
                ],
            })
        )
        config = self.store.load()
        agent = self.store.get_agent("agent1")

        self.assertFalse(self.store.agent_workspace_initialized(config, agent))
        self.store.apply_prompt_template("agent1", {"mode": "overwrite"})
        self.assertTrue(self.store.agent_workspace_initialized(config, agent))

    def test_update_full_config_rejects_validation_errors(self) -> None:
        with self.assertRaises(ConfigError) as context:
            self.store.update_full_config(self.modular_payload({"agents": [{"id": "bad agent", "host_port": 70000}]}))

        self.assertEqual(context.exception.code, "validation_failed")

    def test_redact_masks_sensitive_fields(self) -> None:
        payload = {
            "api_key": "secret",
            "nested": {"matrix_access_token": "token", "plain": "value"},
        }

        self.assertEqual(redact(payload)["api_key"], "[REDACTED]")
        self.assertEqual(redact(payload)["nested"]["matrix_access_token"], "[REDACTED]")
        self.assertEqual(redact(payload)["nested"]["plain"], "value")

    def test_delete_agent_keeps_instance_dir_by_default(self) -> None:
        instances_dir = Path(self.temp_dir.name) / "instances"
        workspace = instances_dir / "agent1" / "workspace"
        workspace.mkdir(parents=True)
        (workspace / "AGENTS.md").write_text("keep me", encoding="utf-8")
        self.store.update_full_config(
            self.modular_payload({
                "paths": {"instances_dir": str(instances_dir)},
                "profiles": {
                    "llm": [{"id": "llm", "provider_family": "ollama", "provider_alias": "local", "model": "qwen"}],
                    "matrix": [{"id": "matrix", "homeserver": "https://matrix.example.com", "access_token": "token"}],
                    "mcp": [],
                },
                "agents": [
                    {
                        "id": "agent1",
                        "host_port": 42641,
                        "llm_profile": "llm",
                        "matrix_profile": "matrix",

                        "matrix": {"user_id": "@agent1:matrix.example.com", "external_peers": ["@you:matrix.example.com"]},
                    }
                ],
            })
        )

        result = self.store.delete_agent("agent1")

        self.assertFalse(result["instance_dir_deleted"])
        self.assertTrue((workspace / "AGENTS.md").exists())

    def test_export_redacts_secrets_by_default(self) -> None:
        self.store.update_full_config(
            self.modular_payload({
                "profiles": {
                    "llm": [{"id": "remote", "provider_family": "openai", "provider_alias": "main", "model": "gpt", "api_key": "secret-key"}],
                    "matrix": [{"id": "matrix", "homeserver": "https://matrix.example.com", "access_token": "matrix-token"}],
                    "mcp": [],
                },
                "agents": [
                    {
                        "id": "agent1",
                        "host_port": 42641,
                        "llm_profile": "remote",
                        "matrix_profile": "matrix",

                        "matrix": {"user_id": "@agent1:matrix.example.com", "external_peers": ["@you:matrix.example.com"]},
                    }
                ],
            })
        )

        result = self.store.export({"agent": "agent1"})
        text = Path(result["path"]).read_text(encoding="utf-8")

        self.assertNotIn("secret-key", text)
        self.assertNotIn("matrix-token", text)
        self.assertIn("[REDACTED]", text)


class DockerControllerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_fake_controller_returns_stable_operation_shape(self) -> None:
        controller = FakeDockerController("http://docker-socket-proxy:2375")

        result = controller.start({}, {"id": "agent1"})

        self.assertTrue(result["accepted"])
        self.assertEqual(result["operation"], "start")
        self.assertEqual(result["controller"], "fake")

    def test_build_container_spec_uses_manager_labels_and_mounts(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))

        spec = controller.build_container_spec(
            {
                "docker": {"project_name": "zeroclaw-dockyard"},
                "paths": {},
                "defaults": {"zeroclaw_image": "example/zeroclaw:test"},
            },
            {
                "id": "agent1",
                "host_port": 42641,
                "matrix": {"user_id": "@agent1:example.test"},
            },
        )

        self.assertEqual(spec.container_name, "zeroclaw-matrix-agent1")
        self.assertEqual(spec.image, "example/zeroclaw:test")
        self.assertEqual(spec.network_name, "zeroclaw-dockyard_default")
        self.assertEqual(spec.labels[MANAGER_LABEL], "true")
        self.assertEqual(spec.labels[AGENT_ID_LABEL], "agent1")
        self.assertEqual(spec.labels[AGENT_NAME_LABEL], "agent1")
        self.assertIn("host.docker.internal:host-gateway", spec.extra_hosts)
        self.assertEqual(spec.storage_driver, "volume")
        self.assertEqual(spec.volume_name, "zeroclaw-dockyard-agent-agent1-data")
        self.assertEqual(spec.local_instance_dir, Path("/app/instances") / "agent1")

    def test_manager_label_is_required_for_operations(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))
        spec = controller.build_container_spec({}, {"id": "agent1", "host_port": 42641})

        self.assertFalse(controller.is_managed_container({"Config": {"Labels": {}}}, spec))
        self.assertTrue(
            controller.is_managed_container(
                {
                    "Config": {
                        "Labels": {
                            MANAGER_LABEL: "true",
                            AGENT_ID_LABEL: "agent1",
                            AGENT_NAME_LABEL: "agent1",
                        }
                    }
                },
                spec,
            )
        )

    def test_resource_decisions_move_rows_out_of_review_buckets(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))
        buckets = {
            "expected": [],
            "conflicts": [{"name": "expected-volume"}],
            "legacy": [{"name": "other-zeroclaw-volume"}],
            "orphans": [],
        }

        result = controller.apply_resource_decisions(
            buckets,
            "volume",
            {
                "adopted": [{"kind": "volume", "name": "expected-volume"}],
                "ignored": [{"kind": "volume", "name": "other-zeroclaw-volume"}],
            },
        )

        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["legacy"], [])
        self.assertEqual(result["adopted"][0]["classification"], "adopted")
        self.assertEqual(result["ignored"][0]["classification"], "ignored")

    def test_image_risk_acknowledgement_is_persisted(self) -> None:
        root = Path(self.temp_dir.name)
        store = ConfigStore(root / "manager.yaml", root / "manager.example.yaml", root / "generated")

        result = store.acknowledge_image_risk("python")

        self.assertTrue(result["acknowledged"]["python"]["accepted"])
        self.assertTrue(store.load_image_state()["acknowledged"]["python"]["accepted"])

    def test_python_dockerfile_installs_python_and_restores_base_user(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))

        dockerfile = controller.derived_dockerfile("python", "example/zeroclaw:test", "1000:1000")

        self.assertIn("USER root", dockerfile)
        self.assertIn("python3 python3-pip python3-venv", dockerfile)
        self.assertIn("USER 1000:1000", dockerfile)

    def test_root_dockerfile_leaves_user_root(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))

        dockerfile = controller.derived_dockerfile("root", "example/zeroclaw:test", "1000:1000")

        self.assertIn("USER root", dockerfile)
        self.assertNotIn("USER 1000:1000", dockerfile)

    def test_decode_build_stream_reads_json_lines(self) -> None:
        events = decode_build_stream(b'{"stream":"Step 1"}\n{"aux":{"ID":"sha256:abc"}}\n')

        self.assertEqual(events[0]["stream"], "Step 1")
        self.assertEqual(events[1]["aux"]["ID"], "sha256:abc")

    def test_build_image_403_reports_disabled_build_permission(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))
        controller.pull_image = lambda _image: None
        controller.inspect_image = lambda _image: {"Config": {"User": "1000:1000"}}

        def denied(*_args, **_kwargs):
            raise DockerApiError(403, "<html><body><h1>403 Forbidden</h1> Request forbidden by administrative rules. </body></html>")

        controller.client.request_bytes = denied

        with self.assertRaises(ConfigError) as context:
            controller.build_derived_image("python", "example/zeroclaw:test", "zeroclaw-python:test")

        self.assertEqual(context.exception.code, "docker_build_permission_disabled")
        self.assertIn("DOCKER_SOCKET_PROXY_BUILD=1", context.exception.message)
        self.assertNotIn("<html>", context.exception.message)

    def test_delete_refuses_expected_resource(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))
        controller.manager_mount_sources = lambda: {}
        config = {
            "docker": {"project_name": "zeroclaw-dockyard"},
            "agents": [{"id": "agent1", "host_port": 42641}],
        }
        controller.list_containers_for_audit = lambda expected: []
        controller.list_volumes_for_audit = lambda expected: []
        controller.list_networks_for_audit = lambda expected: []

        with self.assertRaises(ConfigError) as context:
            controller.ensure_resource_delete_allowed(config, "volume", "zeroclaw-dockyard-agent-agent1-data")

        self.assertEqual(context.exception.code, "resource_delete_refused")

    def test_build_container_spec_uses_manager_mount_sources(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))
        controller._manager_mounts = {
            "/app/instances": str(Path(self.temp_dir.name) / "host-instances"),
            "/app/bootstrap": str(Path(self.temp_dir.name) / "host-bootstrap"),
        }

        spec = controller.build_container_spec({"docker": {"storage_driver": "bind"}}, {"id": "agent1", "host_port": 42641})

        self.assertEqual(spec.instance_dir, Path(self.temp_dir.name) / "host-instances" / "agent1")
        self.assertEqual(spec.bootstrap_dir, Path(self.temp_dir.name) / "host-bootstrap")

    def test_build_proactive_spec_uses_agent_host_port(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))
        controller._manager_mounts = {
            "/app/instances": str(Path(self.temp_dir.name) / "host-instances"),
            "/app/bootstrap": str(Path(self.temp_dir.name) / "host-bootstrap"),
        }
        agent = {
            "id": "agent1",
            "host_port": 42641,
            "matrix": {"external_peers": ["@you:matrix.example.com"]},
            "proactive": {"enabled": True, "random_min_minutes": 10, "random_max_minutes": 20},
        }

        spec = controller.build_proactive_spec({}, agent)

        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.container_name, "zeroclaw-proactive-agent1")
        self.assertEqual(spec.environment["PROACTIVE_AGENT_URL"], "http://host.docker.internal:42641/webhook?agent=agent1")
        self.assertEqual(spec.environment["PROACTIVE_TARGET"], "@you:matrix.example.com")
        self.assertEqual(spec.storage_driver, "volume")
        self.assertEqual(spec.volume_name, "zeroclaw-dockyard-agent-agent1-data")
        self.assertEqual(spec.local_instance_dir, Path("/app/instances") / "agent1")

    def test_build_proactive_spec_allows_gateway_url_override(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))
        controller._manager_mounts = {
            "/app/instances": str(Path(self.temp_dir.name) / "host-instances"),
            "/app/bootstrap": str(Path(self.temp_dir.name) / "host-bootstrap"),
        }
        agent = {
            "id": "agent1",
            "host_port": 42641,
            "matrix": {"external_peers": ["@you:matrix.example.com"]},
            "proactive": {"enabled": True, "agent_url": "http://gateway.local/custom"},
        }

        spec = controller.build_proactive_spec({}, agent)

        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.environment["PROACTIVE_AGENT_URL"], "http://gateway.local/custom")

    def test_reset_matrix_state_rejects_running_container(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))
        agent = {"id": "agent1", "host_port": 42641}
        spec = controller.build_container_spec({}, agent)
        controller.find_container = lambda _spec: {
            "Id": "container-id",
            "State": {"Running": True},
            "Config": {"Labels": spec.labels},
        }

        with self.assertRaises(ConfigError) as context:
            controller.reset_matrix_state({}, agent)

        self.assertEqual(context.exception.code, "agent_running")

    def test_reset_matrix_state_removes_bind_matrix_directory(self) -> None:
        root = Path(self.temp_dir.name)
        instance = root / "instances" / "agent1"
        matrix_dir = instance / ".zeroclaw" / "state" / "matrix"
        matrix_dir.mkdir(parents=True)
        (matrix_dir / "crypto.sqlite3").write_text("state", encoding="utf-8")
        controller = DockerApiController("http://docker-socket-proxy:2375", root)
        controller._manager_mounts = {
            "/app/instances": str(root / "instances"),
            "/app/bootstrap": str(root / "bootstrap"),
        }
        controller.find_container = lambda _spec: None

        result = controller.reset_matrix_state({"docker": {"storage_driver": "bind"}}, {"id": "agent1", "host_port": 42641})

        self.assertFalse(matrix_dir.exists())
        self.assertIn("matrix_state_removed_from_local", result["actions"])

    def test_sync_script_uses_staged_mirror_replace(self) -> None:
        controller = DockerApiController("http://docker-socket-proxy:2375", Path(self.temp_dir.name))

        script = controller.sync_script("to-runtime", "agent1")

        self.assertIn("def mirror_tree", script)
        self.assertIn("copy_tree(src, stage)", script)
        self.assertIn("move_dir_contents(backup, dst)", script)
        self.assertNotIn("copy_tree(local, volume)", script)

    def test_decode_docker_multiplexed_logs(self) -> None:
        frame = b"\x01\x00\x00\x00" + (6).to_bytes(4, "big") + b"hello\n"

        self.assertEqual(decode_docker_log_stream(frame), "hello\n")


class ObservabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_redact_lines_masks_config_secret_values_and_token_patterns(self) -> None:
        bearer_token = "abcdefgh" + "ijklmnop"
        lines = [
            "MODEL_PROVIDER_API_KEY=secret-key",
            f"Authorization: Bearer {bearer_token}",
            "plain line",
        ]
        config = {"profiles": {"llm": [{"api_key": "secret-key"}]}}

        redacted = "\n".join(redact_lines(lines, config))

        self.assertNotIn("secret-key", redacted)
        self.assertNotIn(bearer_token, redacted)
        self.assertIn("[REDACTED]", redacted)
        self.assertIn("plain line", redacted)

    def test_normalize_agent_state_maps_required_dashboard_states(self) -> None:
        self.assertEqual(normalize_agent_state({"state": "absent"}), "missing")
        self.assertEqual(normalize_agent_state({"state": "created"}), "created")
        self.assertEqual(normalize_agent_state({"state": "running"}), "running")
        self.assertEqual(normalize_agent_state({"state": "running", "health_status": "unhealthy"}), "unhealthy")
        self.assertEqual(normalize_agent_state({"state": "exited"}), "stopped")
        self.assertEqual(normalize_agent_state({"state": "restarting"}), "restarting")
        self.assertEqual(normalize_agent_state({"error": {"message": "boom"}}), "error")

    def test_operation_history_redacts_results(self) -> None:
        history = OperationHistory(Path(self.temp_dir.name) / "history.jsonl")

        history.append("start", agent_id="agent1", result={"api_key": "secret", "state": "running"})
        entries = history.list()

        self.assertEqual(entries[0]["operation"], "start")
        self.assertEqual(entries[0]["agent_id"], "agent1")
        self.assertEqual(entries[0]["result"]["api_key"], "[REDACTED]")


class ApiRoutingTest(unittest.TestCase):
    def test_parse_tail_is_clamped(self) -> None:
        handler = object.__new__(ManagerHandler)

        self.assertEqual(handler.parse_tail({"tail": ["0"]}), 1)
        self.assertEqual(handler.parse_tail({"tail": ["9999"]}), 2000)
        self.assertEqual(handler.parse_tail({"tail": ["bad"]}), 200)

    def test_parse_limit_is_clamped(self) -> None:
        handler = object.__new__(ManagerHandler)

        self.assertEqual(handler.parse_limit({"limit": ["0"]}, default=50, maximum=100), 1)
        self.assertEqual(handler.parse_limit({"limit": ["999"]}, default=50, maximum=100), 100)
        self.assertEqual(handler.parse_limit({"limit": ["bad"]}, default=50, maximum=100), 50)


class PromptTemplateAiFillerTest(unittest.TestCase):
    def test_parse_generated_files_accepts_requested_json(self) -> None:
        filler = PromptTemplateAiFiller()

        result = filler._parse_generated_files('{"AGENTS.md": "# A", "SOUL.md": "# S", "OTHER.md": "skip"}', ["AGENTS.md", "SOUL.md"])

        self.assertEqual(result, {"AGENTS.md": "# A", "SOUL.md": "# S"})

    def test_parse_generated_files_rejects_missing_requested_file(self) -> None:
        filler = PromptTemplateAiFiller()

        with self.assertRaises(ConfigError) as context:
            filler._parse_generated_files('{"AGENTS.md": "# A"}', ["AGENTS.md", "SOUL.md"])

        self.assertEqual(context.exception.code, "missing_ai_files")

    def test_safe_file_validation_rejects_paths(self) -> None:
        filler = PromptTemplateAiFiller()

        with self.assertRaises(ConfigError) as context:
            filler._safe_file_names(["../secret"], "files")

        self.assertEqual(context.exception.code, "invalid_files")


class AgentRendererTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.renderer = AgentRenderer(self.root)
        self.config = {
            "paths": {"instances_dir": str(self.root / "instances")},
            "docker": {"project_name": "zeroclaw-dockyard", "matrix_host_ip": "127.0.0.1"},
            "defaults": {
                "zeroclaw_image": "example/zeroclaw:test",
                "matrix": {"homeserver": "https://matrix.example.com", "reply_in_thread": True},
            },
            "profiles": {
                "llm": [
                    {
                        "id": "deepseek-text",
                        "provider_family": "deepseek",
                        "provider_alias": "text",
                        "model": "deepseek-chat",
                        "base_url": "https://api.deepseek.com/v1",
                        "wire_api": "chat_completions",
                        "timeout_secs": 120,
                        "temperature": 0.2,
                        "max_tokens": 4096,
                        "fallback_models": ["deepseek-reasoner"],
                        "extra_headers": {"X-Test": "yes"},
                    }
                ],
                "matrix": [{"id": "matrix-main", "mention_only": False}],
                "mcp": [{"id": "mcp-home", "enabled": False, "server_name": "home"}],
            },
            "prompt_templates": [{"id": "default", "files": {"AGENTS.md": "hello", "MEMORY.md": "memory"}}],
        }
        self.agent = {
            "id": "agent1",
            "host_port": 42641,
            "llm_profile": "deepseek-text",
            "matrix_profile": "matrix-main",
            "mcp_profile": "mcp-home",
            "prompt_template": "default",
            "matrix": {"user_id": "@agent1:matrix.example.com", "device_id": "ZEROCLAW_AGENT1"},
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_render_env_includes_required_variables(self) -> None:
        env = self.renderer.render_env(self.config, self.agent)

        for key in REQUIRED_ENV_KEYS:
            self.assertIn(key, env)
        self.assertEqual(env["BOT_NAME"], "agent1")
        self.assertEqual(env["MODEL_PROVIDER_MODEL"], "deepseek-chat")
        self.assertEqual(env["MODEL_PROVIDER_TEMPERATURE"], "0.2")
        self.assertEqual(env["MODEL_PROVIDER_MAX_TOKENS"], "4096")
        self.assertEqual(env["MODEL_PROVIDER_FALLBACK_MODELS"], '["deepseek-reasoner"]')
        self.assertEqual(env["MODEL_PROVIDER_EXTRA_HEADERS"], '{ "X-Test" = "yes" }')
        self.assertEqual(env["MATRIX_USER_ID"], "@agent1:matrix.example.com")

    def test_workspace_keep_and_merge_modes_do_not_silently_overwrite(self) -> None:
        first = self.renderer.initialize_workspace(self.config, self.agent, mode="overwrite")
        workspace = Path(first["workspace"])
        agents_file = workspace / "AGENTS.md"
        agents_file.write_text("user edit", encoding="utf-8")

        keep = self.renderer.initialize_workspace(self.config, self.agent, mode="keep")
        merge = self.renderer.initialize_workspace(self.config, self.agent, mode="merge")

        self.assertIn("AGENTS.md", keep["skipped"])
        self.assertIn("AGENTS.md", merge["merged"])
        self.assertIn("user edit", agents_file.read_text(encoding="utf-8"))
        self.assertIn("ZeroClaw template merge", agents_file.read_text(encoding="utf-8"))

    def test_workspace_allows_safe_custom_prompt_template_files(self) -> None:
        config = copy_config(self.config)
        config["prompt_templates"][0]["files"]["BOOTSTRAP.md"] = "first run"
        config["prompt_templates"][0]["files"]["RHYTHM.md"] = "custom rhythm"
        config["prompt_templates"][0]["files"]["../escape.md"] = "nope"

        result = self.renderer.initialize_workspace(config, self.agent, mode="overwrite")
        workspace = Path(result["workspace"])

        self.assertIn("BOOTSTRAP.md", result["written"])
        self.assertIn("RHYTHM.md", result["written"])
        self.assertIn("../escape.md", result["skipped"])
        self.assertEqual((workspace / "BOOTSTRAP.md").read_text(encoding="utf-8"), "first run")
        self.assertEqual((workspace / "RHYTHM.md").read_text(encoding="utf-8"), "custom rhythm")
        self.assertFalse((workspace.parent / "escape.md").exists())

    def test_export_agent_returns_env_and_preview(self) -> None:
        self.config["profiles"]["vision"] = [
            {
                "id": "vision-openai",
                "provider_family": "openai",
                "provider_alias": "vision",
                "model": "gpt-4o-mini",
                "base_url": "https://api.openai.com/v1",
                "wire_api": "chat_completions",
                "timeout_secs": 90,
                "max_images": 3,
                "max_image_size_mb": 6,
                "max_image_turns": 1,
            }
        ]
        self.agent["vision_profile"] = "vision-openai"
        exported = self.renderer.export_agent(self.config, self.agent)

        self.assertIn("env", exported["formats"])
        self.assertIn("zeroclaw_config_preview", exported["formats"])
        self.assertIn("schema_version = 3", exported["formats"]["zeroclaw_config_preview"])
        self.assertEqual(exported["formats"]["env"]["VISION_PROVIDER_FAMILY"], "openai")
        self.assertEqual(exported["formats"]["env"]["VISION_PROVIDER_ALIAS"], "vision")
        self.assertIn("[providers.models.openai.vision]", exported["formats"]["zeroclaw_config_preview"])
        self.assertIn('vision_model_provider = "openai.vision"', exported["formats"]["zeroclaw_config_preview"])

    def test_agent_without_vision_profile_disables_vision_route(self) -> None:
        config = copy_config(self.config)
        config["profiles"]["vision"] = [
            {
                "id": "vision-openai",
                "provider_family": "openai",
                "provider_alias": "vision",
                "model": "gpt-4o-mini",
                "base_url": "https://api.openai.com/v1",
                "wire_api": "chat_completions",
            }
        ]
        agent = copy_config(self.agent)
        agent.pop("vision_profile", None)

        exported = self.renderer.export_agent(config, agent)

        self.assertEqual(exported["formats"]["env"]["VISION_ENABLED"], "false")
        self.assertNotIn("vision_model_provider", exported["formats"]["zeroclaw_config_preview"])

    def test_export_agent_redacts_preview_when_requested(self) -> None:
        config = copy_config(self.config)
        config["profiles"]["llm"][0]["api_key"] = "secret-key"
        config["profiles"]["matrix"][0]["access_token"] = "matrix-token"

        exported = self.renderer.export_agent(config, self.agent, include_secrets=False)
        serialized = yaml.safe_dump(exported)

        self.assertNotIn("secret-key", serialized)
        self.assertNotIn("matrix-token", serialized)
        self.assertIn("[REDACTED]", serialized)


class ConfigValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.validator = ConfigValidator(self.root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validator_returns_multiple_agent_errors(self) -> None:
        config = {
            "paths": {"instances_dir": str(self.root / "instances")},
            "profiles": {"llm": [{"id": "remote", "provider_family": "openai", "provider_alias": "main"}], "matrix": [{"id": "matrix"}], "mcp": []},
            "prompt_templates": [],
            "agents": [
                {
                    "id": "bad agent",
                    "host_port": 70000,
                    "llm_profile": "remote",
                    "matrix_profile": "matrix",
                    "prompt_template": "missing",
                }
            ],
        }

        result = self.validator.validate_config(config)
        codes = {entry["code"] for entry in result["errors"]}

        self.assertFalse(result["valid"])
        self.assertIn("invalid_agent_id", codes)
        self.assertIn("invalid_host_port", codes)
        self.assertIn("missing_model", codes)
        self.assertIn("missing_matrix_homeserver", codes)
        self.assertIn("missing_matrix_credentials", codes)
        self.assertIn("missing_matrix_external_peers", codes)

    def test_start_validation_raises_structured_error(self) -> None:
        config = {
            "paths": {"instances_dir": str(self.root / "instances")},
            "profiles": {"llm": [], "matrix": [], "mcp": []},
            "agents": [{"id": "agent1", "host_port": 42641}],
        }

        with self.assertRaises(ConfigError) as context:
            self.validator.ensure_valid_for_start(config, config["agents"][0])

        self.assertEqual(context.exception.code, "validation_failed")

    def test_validator_checks_vision_config(self) -> None:
        config = {
            "profiles": {
                "llm": [],
                "vision": [
                    {
                        "id": "bad-vision",
                        "provider_family": "bad family",
                        "provider_alias": "vision",
                        "model": "",
                        "base_url": "ftp://example.com",
                        "wire_api": "",
                        "max_images": 99,
                    }
                ],
                "matrix": [],
                "mcp": [],
            },
            "agents": [],
        }

        result = self.validator.validate_config(config)
        codes = {entry["code"] for entry in result["errors"]}

        self.assertFalse(result["valid"])
        self.assertIn("invalid_vision_provider_family", codes)
        self.assertIn("missing_vision_model", codes)
        self.assertIn("invalid_vision_base_url", codes)
        self.assertIn("missing_vision_wire_api", codes)
        self.assertIn("invalid_vision_number", codes)


def copy_config(config: dict) -> dict:
    return yaml.safe_load(yaml.safe_dump(config))


if __name__ == "__main__":
    unittest.main()
