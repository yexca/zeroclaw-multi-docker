from pathlib import Path

import pytest

from manager.backend.config_store import ConfigError
from manager.backend.skill_store import SkillStore


def config(tmp_path: Path) -> dict:
    return {
        "skills": {"allow_scripts": False},
        "skill_bundles": [{"id": "core", "directory": "shared/skills/core", "include": [], "exclude": []}],
        "agents": [{"id": "agent1", "skill_bundles": ["core"]}],
    }


def test_create_read_write_and_archive_skill(tmp_path: Path) -> None:
    store = SkillStore(tmp_path)
    cfg = config(tmp_path)

    created = store.create_skill(
        cfg,
        "core",
        {"name": "review", "frontmatter": {"name": "review", "description": "Review code"}, "body": "# Review\n"},
    )
    assert created["name"] == "review"
    assert (tmp_path / "shared" / "skills" / "core" / "review" / "SKILL.md").is_file()

    doc = store.read_skill(cfg, "core", "review")
    assert doc["frontmatter"]["description"] == "Review code"

    updated = store.write_skill(
        cfg,
        "core",
        "review",
        {"frontmatter": {"name": "review", "description": "Review deeply", "tags": ["coding"]}, "body": "# Body\n"},
    )
    assert updated["frontmatter"]["tags"] == ["coding"]

    removed = store.remove_skill(cfg, "core", "review")
    assert removed["purged"] is False
    assert Path(removed["archived_to"]).is_dir()


def test_support_file_policy_blocks_scripts_until_enabled(tmp_path: Path) -> None:
    store = SkillStore(tmp_path)
    cfg = config(tmp_path)
    store.create_skill(cfg, "core", {"name": "ops", "frontmatter": {"description": "Ops helper"}})

    with pytest.raises(ConfigError) as exc:
        store.write_support_file(cfg, "core", "ops", {"file_path": "scripts/run.sh", "content": "echo hi\n"})
    assert exc.value.code == "scripts_disabled"

    cfg["skills"]["allow_scripts"] = True
    result = store.write_support_file(cfg, "core", "ops", {"file_path": "scripts/run.sh", "content": "echo hi\n"})
    assert result["file_path"] == "scripts/run.sh"


def test_binary_support_files_use_bytes_api(tmp_path: Path) -> None:
    store = SkillStore(tmp_path)
    cfg = config(tmp_path)
    store.create_skill(cfg, "core", {"name": "assets", "frontmatter": {"description": "Asset helper"}})
    content = b"\x89PNG\r\n\x1a\n\x00\x00"

    result = store.write_support_file_bytes(cfg, "core", "assets", "assets/logo.png", content)
    assert result["file_path"] == "assets/logo.png"
    assert result["bytes"] == len(content)
    assert result["text"] is False

    info = store.support_file_info(cfg, "core", "assets", "assets/logo.png")
    assert info["text"] is False

    with pytest.raises(ConfigError) as exc:
        store.read_support_file(cfg, "core", "assets", "assets/logo.png")
    assert exc.value.code == "binary_file"

    download_info, downloaded = store.read_support_file_bytes(cfg, "core", "assets", "assets/logo.png")
    assert download_info["file_path"] == "assets/logo.png"
    assert downloaded == content


def test_rejects_paths_outside_shared_and_skill_dir(tmp_path: Path) -> None:
    store = SkillStore(tmp_path)
    cfg = {"skill_bundles": [{"id": "bad", "directory": "../outside"}]}
    with pytest.raises(ConfigError) as exc:
        store.list_skills(cfg, "bad")
    assert exc.value.code == "unsafe_skill_bundle_directory"

    cfg = config(tmp_path)
    store.create_skill(cfg, "core", {"name": "safe", "frontmatter": {"description": "Safe"}})
    with pytest.raises(ConfigError) as exc:
        store.write_support_file(cfg, "core", "safe", {"file_path": "../nope", "content": ""})
    assert exc.value.code == "invalid_support_path"
