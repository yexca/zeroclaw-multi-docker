"""Skill bundle and canonical SKILL.md filesystem management."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

try:
    from config_store import ConfigError, item_id
except ModuleNotFoundError:  # pragma: no cover - package import path for tests
    from .config_store import ConfigError, item_id


SKILL_MANIFEST = "SKILL.md"
SKILL_SUBDIRS = ("scripts", "references", "assets")
SKILL_ARCHIVE_DIR = "_deleted"
MAX_FILE_BYTES = 256 * 1024
SAFE_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


@dataclass
class SkillDocument:
    frontmatter: dict[str, Any]
    body: str


class SkillStore:
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.shared_root = self.project_root / "shared"
        self.skills_root = self.shared_root / "skills"

    def list_bundles(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        bundles = []
        for bundle in normalize_bundles(config.get("skill_bundles")):
            alias = require_slug(item_id(bundle) or "", "bundle")
            bundles.append(
                {
                    "id": alias,
                    "alias": alias,
                    "directory": str(self.bundle_dir(config, alias)),
                    "include": list_value(bundle.get("include")),
                    "exclude": list_value(bundle.get("exclude")),
                }
            )
        return bundles

    def list_skills(self, config: dict[str, Any], bundle: str) -> list[dict[str, Any]]:
        alias = require_slug(bundle, "bundle")
        directory = self.bundle_dir(config, alias)
        if not directory.exists():
            return []
        rows = []
        for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir() or child.name == SKILL_ARCHIVE_DIR:
                continue
            manifest = child / SKILL_MANIFEST
            if not manifest.is_file():
                continue
            try:
                doc = parse_skill_document(manifest.read_text(encoding="utf-8"))
            except ConfigError:
                continue
            rows.append(
                {
                    "bundle": alias,
                    "name": child.name,
                    "directory": str(child),
                    "frontmatter": doc.frontmatter,
                    "files": self.list_support_files(child),
                }
            )
        return rows

    def agent_skills(self, config: dict[str, Any], agent: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(item_id(agent) or "")
        result = []
        for alias in list_value(agent.get("skill_bundles")):
            bundle = self.get_bundle(config, alias)
            include = set(list_value(bundle.get("include")))
            exclude = set(list_value(bundle.get("exclude")))
            for skill in self.list_skills(config, alias):
                name = skill["name"]
                if include and name not in include:
                    continue
                if name in exclude:
                    continue
                result.append(
                    {
                        "name": name,
                        "description": str(skill.get("frontmatter", {}).get("description") or ""),
                        "origin": "bundle",
                        "bundle": alias,
                        "directory": skill.get("directory"),
                        "editable": True,
                    }
                )
        return {"agent": agent_id, "skills": result}

    def read_skill(self, config: dict[str, Any], bundle: str, name: str) -> dict[str, Any]:
        alias = require_slug(bundle, "bundle")
        skill_name = require_slug(name, "skill")
        directory = self.skill_dir(config, alias, skill_name)
        manifest = directory / SKILL_MANIFEST
        if not manifest.is_file():
            raise ConfigError("not_found", "Skill was not found.", {"bundle": alias, "name": skill_name}, 404)
        doc = parse_skill_document(manifest.read_text(encoding="utf-8"))
        return {
            "bundle": alias,
            "name": skill_name,
            "directory": str(directory),
            "frontmatter": doc.frontmatter,
            "body": doc.body,
            "files": self.list_support_files(directory),
        }

    def create_skill(self, config: dict[str, Any], bundle: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ConfigError("invalid_payload", "Skill create payload must be an object.")
        alias = require_slug(bundle, "bundle")
        name = require_slug(str(payload.get("name") or payload.get("frontmatter", {}).get("name") or ""), "skill")
        directory = self.skill_dir(config, alias, name)
        if directory.exists():
            raise ConfigError("duplicate_skill", "Skill already exists.", {"bundle": alias, "name": name}, 409)
        frontmatter = normalize_frontmatter(payload.get("frontmatter") if isinstance(payload.get("frontmatter"), dict) else {})
        frontmatter["name"] = str(frontmatter.get("name") or name)
        if not str(frontmatter.get("description") or "").strip():
            raise ConfigError("missing_description", "Skill description is required.", status=422)
        body = str(payload.get("body") or "")
        directory.mkdir(parents=True, exist_ok=False)
        if not payload.get("no_scaffold"):
            for subdir in SKILL_SUBDIRS:
                (directory / subdir).mkdir(parents=True, exist_ok=True)
        self.atomic_write(directory / SKILL_MANIFEST, serialize_skill_document(SkillDocument(frontmatter, body)))
        return {"bundle": alias, "name": name, "directory": str(directory)}

    def write_skill(self, config: dict[str, Any], bundle: str, name: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ConfigError("invalid_payload", "Skill update payload must be an object.")
        alias = require_slug(bundle, "bundle")
        skill_name = require_slug(name, "skill")
        directory = self.skill_dir(config, alias, skill_name)
        if not directory.is_dir():
            raise ConfigError("not_found", "Skill was not found.", {"bundle": alias, "name": skill_name}, 404)
        frontmatter = normalize_frontmatter(payload.get("frontmatter") if isinstance(payload.get("frontmatter"), dict) else {})
        frontmatter["name"] = str(frontmatter.get("name") or skill_name)
        if not str(frontmatter.get("description") or "").strip():
            raise ConfigError("missing_description", "Skill description is required.", status=422)
        body = str(payload.get("body") or "")
        self.atomic_write(directory / SKILL_MANIFEST, serialize_skill_document(SkillDocument(frontmatter, body)))
        return self.read_skill(config, alias, skill_name)

    def write_support_file(self, config: dict[str, Any], bundle: str, name: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ConfigError("invalid_payload", "Support file payload must be an object.")
        alias = require_slug(bundle, "bundle")
        skill_name = require_slug(name, "skill")
        relative = safe_support_path(str(payload.get("file_path") or ""))
        content = str(payload.get("content") or "")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ConfigError("file_too_large", "Support file exceeds the maximum size.", {"max_bytes": MAX_FILE_BYTES}, 413)
        if relative.parts[0] == "scripts" and not bool((config.get("skills") or {}).get("allow_scripts")):
            raise ConfigError("scripts_disabled", "Script files are disabled by skills.allow_scripts.", status=422)
        directory = self.skill_dir(config, alias, skill_name)
        if not directory.is_dir():
            raise ConfigError("not_found", "Skill was not found.", {"bundle": alias, "name": skill_name}, 404)
        target = safe_child(directory, relative)
        self.atomic_write(target, content)
        return {"bundle": alias, "name": skill_name, "file_path": relative.as_posix(), "bytes": len(content.encode("utf-8"))}

    def read_support_file(self, config: dict[str, Any], bundle: str, name: str, file_path: str) -> dict[str, Any]:
        alias = require_slug(bundle, "bundle")
        skill_name = require_slug(name, "skill")
        relative = safe_support_path(file_path)
        target = safe_child(self.skill_dir(config, alias, skill_name), relative)
        if not target.is_file():
            raise ConfigError("not_found", "Support file was not found.", {"file_path": relative.as_posix()}, 404)
        content = target.read_text(encoding="utf-8")
        return {"bundle": alias, "name": skill_name, "file_path": relative.as_posix(), "content": content}

    def delete_support_file(self, config: dict[str, Any], bundle: str, name: str, file_path: str) -> dict[str, Any]:
        alias = require_slug(bundle, "bundle")
        skill_name = require_slug(name, "skill")
        relative = safe_support_path(file_path)
        target = safe_child(self.skill_dir(config, alias, skill_name), relative)
        if not target.is_file():
            raise ConfigError("not_found", "Support file was not found.", {"file_path": relative.as_posix()}, 404)
        target.unlink()
        return {"bundle": alias, "name": skill_name, "file_path": relative.as_posix()}

    def remove_skill(self, config: dict[str, Any], bundle: str, name: str, purge: bool = False) -> dict[str, Any]:
        alias = require_slug(bundle, "bundle")
        skill_name = require_slug(name, "skill")
        directory = self.skill_dir(config, alias, skill_name)
        if not directory.is_dir():
            raise ConfigError("not_found", "Skill was not found.", {"bundle": alias, "name": skill_name}, 404)
        if purge:
            shutil.rmtree(directory)
            return {"bundle": alias, "name": skill_name, "purged": True}
        archive_root = self.skills_root / SKILL_ARCHIVE_DIR
        archive_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = archive_root / f"{alias}-{skill_name}-{stamp}"
        shutil.move(str(directory), str(target))
        return {"bundle": alias, "name": skill_name, "purged": False, "archived_to": str(target)}

    def bundle_dir(self, config: dict[str, Any], alias: str) -> Path:
        bundle = self.get_bundle(config, alias)
        configured = str(bundle.get("directory") or "").strip()
        if configured:
            candidate = Path(configured)
            path = candidate if candidate.is_absolute() else self.project_root / candidate
        else:
            path = self.skills_root / alias
        return validate_shared_path(path.resolve(), self.shared_root)

    def skill_dir(self, config: dict[str, Any], bundle: str, name: str) -> Path:
        return safe_child(self.bundle_dir(config, bundle), PurePosixPath(name))

    def get_bundle(self, config: dict[str, Any], alias: str) -> dict[str, Any]:
        safe_alias = require_slug(alias, "bundle")
        for bundle in normalize_bundles(config.get("skill_bundles")):
            if item_id(bundle) == safe_alias:
                return bundle
        raise ConfigError("not_found", "Skill bundle was not found.", {"bundle": safe_alias}, 404)

    def list_support_files(self, directory: Path) -> list[str]:
        files: list[str] = []
        for subdir in SKILL_SUBDIRS:
            root = directory / subdir
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    files.append(path.relative_to(directory).as_posix())
        return files

    def atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def normalize_bundles(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        result = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("id", str(key))
                result.append(row)
        return result
    return []


def normalize_frontmatter(frontmatter: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("name", "description", "license", "author", "version", "category"):
        value = frontmatter.get(key)
        if value is not None and str(value).strip():
            result[key] = str(value).strip()
    tags = list_value(frontmatter.get("tags"))
    if tags:
        result["tags"] = tags
    return result


def parse_skill_document(content: str) -> SkillDocument:
    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise ConfigError("invalid_skill_document", "SKILL.md is missing YAML frontmatter.", status=422)
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise ConfigError("invalid_skill_document", "SKILL.md frontmatter is not closed.", status=422)
    frontmatter_src = normalized[4:end]
    body = normalized[end + 5 :]
    parsed = yaml.safe_load(frontmatter_src) or {}
    if not isinstance(parsed, dict):
        raise ConfigError("invalid_skill_document", "SKILL.md frontmatter must be a mapping.", status=422)
    frontmatter = normalize_frontmatter(parsed)
    if not str(frontmatter.get("name") or "").strip():
        raise ConfigError("invalid_skill_document", "SKILL.md frontmatter requires name.", status=422)
    if not str(frontmatter.get("description") or "").strip():
        raise ConfigError("invalid_skill_document", "SKILL.md frontmatter requires description.", status=422)
    return SkillDocument(frontmatter, body.lstrip("\n"))


def serialize_skill_document(document: SkillDocument) -> str:
    frontmatter = normalize_frontmatter(document.frontmatter)
    data = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False).strip()
    body = document.body or ""
    return f"---\n{data}\n---\n\n{body.rstrip()}\n"


def require_slug(value: str, kind: str) -> str:
    slug = str(value or "").strip()
    if not SAFE_SLUG.match(slug):
        raise ConfigError("invalid_slug", f"{kind.title()} name must use letters, numbers, underscore, or hyphen.", {kind: value}, 422)
    return slug


def list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def validate_shared_path(path: Path, shared_root: Path) -> Path:
    root = shared_root.resolve()
    normalized = path.resolve()
    if normalized != root and root not in normalized.parents:
        raise ConfigError(
            "unsafe_skill_bundle_directory",
            "Skill bundle directories must stay inside the project shared directory.",
            {"path": str(normalized), "shared": str(root)},
            422,
        )
    return normalized


def safe_child(root: Path, relative: PurePosixPath) -> Path:
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ConfigError("unsafe_path", "Path must be relative and stay inside the skill directory.", {"path": relative.as_posix()}, 422)
    target = (root / Path(*relative.parts)).resolve()
    root_resolved = root.resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise ConfigError("unsafe_path", "Path escapes the skill directory.", {"path": relative.as_posix()}, 422)
    return target


def safe_support_path(value: str) -> PurePosixPath:
    text = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or len(path.parts) < 2 or path.parts[0] not in SKILL_SUBDIRS:
        raise ConfigError("invalid_support_path", "Support files must be under scripts/, references/, or assets/.", {"path": value}, 422)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ConfigError("invalid_support_path", "Support file path contains an invalid segment.", {"path": value}, 422)
    return path
