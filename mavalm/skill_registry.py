from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"
REGISTRY_PATH = SKILLS_ROOT / "registry.json"
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


@dataclass(frozen=True)
class SkillPackage:
    role: str
    name: str
    version: str
    root: Path
    instructions: str
    resources: dict[str, Path]

    @property
    def identity(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}

    def read_text(self, resource: str) -> str:
        return self.resources[resource].read_text(encoding="utf-8").strip()

    def read_json(self, resource: str) -> dict[str, Any]:
        with self.resources[resource].open(encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError(f"Skill resource must contain a JSON object: {resource}")
        return value


def _resolve_inside(root: Path, relative: str) -> Path:
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Skill path escapes package root: {relative}")
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _markdown_body(text: str) -> str:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md is missing YAML frontmatter")
    closing = text.find("\n---\n", 4)
    if closing < 0:
        raise ValueError("SKILL.md has unterminated YAML frontmatter")
    return text[closing + 5 :].strip()


def load_skill(role: str, registry_path: Path = REGISTRY_PATH) -> SkillPackage:
    with registry_path.open(encoding="utf-8") as handle:
        registry = json.load(handle)

    entry = registry.get("skills", {}).get(role)
    if not isinstance(entry, dict):
        raise KeyError(f"Unknown Skill role: {role}")

    version = str(entry.get("version", ""))
    if not SEMVER.fullmatch(version):
        raise ValueError(f"Skill {role} is not pinned to an exact SemVer: {version!r}")

    skills_root = registry_path.resolve().parent
    package_root = (skills_root / str(entry["path"])).resolve()
    if package_root.parent != skills_root or not package_root.is_dir():
        raise ValueError(f"Invalid package path for Skill {role}: {package_root}")

    instruction_path = _resolve_inside(package_root, str(entry["instruction"]))
    resources = {
        key: _resolve_inside(package_root, str(relative))
        for key, relative in entry.get("resources", {}).items()
    }
    return SkillPackage(
        role=role,
        name=str(entry["name"]),
        version=version,
        root=package_root,
        instructions=_markdown_body(instruction_path.read_text(encoding="utf-8")),
        resources=resources,
    )


def annotation_contract(registry_path: Path = REGISTRY_PATH) -> tuple[SkillPackage, dict[str, str], str]:
    package = load_skill("annotation", registry_path)
    schema = package.read_json("schema")
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ValueError("Annotation Skill schema has no properties")
    required = schema.get("required")
    if not isinstance(required, list) or set(required) != set(properties):
        raise ValueError("Annotation Skill must require exactly all schema properties")
    template = {field: "" for field in properties}
    prompt = (
        f"Pinned domain Skill: {package.name}@{package.version}\n\n"
        f"{package.instructions}\n\n"
        f"# Domain field guide\n\n{package.read_text('domain_rules')}\n\n"
        "# Exact JSON template\n\n"
        f"{json.dumps(template, indent=2)}"
    )
    return package, template, prompt


def verification_contract(registry_path: Path = REGISTRY_PATH) -> tuple[SkillPackage, str]:
    package = load_skill("verification", registry_path)
    prompt = (
        f"Pinned domain Skill: {package.name}@{package.version}\n\n"
        f"{package.instructions}\n\n"
        f"# Field-wise equivalence policy\n\n{package.read_text('domain_rules')}"
    )
    return package, prompt
