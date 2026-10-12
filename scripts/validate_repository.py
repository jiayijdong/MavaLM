#!/usr/bin/env python3
"""Validate Skill pins, schema alignment, JSON syntax and repository hygiene."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mavalm.metrics import SCHEMA_FIELDS  # noqa: E402
from mavalm.skill_registry import annotation_contract, load_skill, verification_contract  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_skills() -> None:
    annotation, template, prompt = annotation_contract()
    verification, judge_prompt = verification_contract()
    require(annotation.version == "1.0.0", "Unexpected annotation Skill version")
    require(verification.version == "1.2.0", "Unexpected verification Skill version")
    require(len(template) == 97, f"PSC schema contains {len(template)} fields, expected 97")
    require(set(template) == set(SCHEMA_FIELDS), "metrics FIELD_GROUPS do not cover the schema exactly")
    require(annotation.name in prompt and verification.name in judge_prompt, "Skill identity missing from runtime prompt")
    archived = load_skill("verification", REPO_ROOT / "skills" / "archive" / "registry.json")
    require(archived.version == "1.1.0", "Archived paper Skill must be psc-verify-v1@1.1.0")


def validate_json_files() -> None:
    for path in sorted(REPO_ROOT.rglob("*.json")):
        if ".git" in path.parts:
            continue
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
        require(isinstance(value, (dict, list)), f"Unexpected JSON root: {path}")


def validate_hygiene() -> None:
    forbidden = {".DS_Store", "Thumbs.db"}
    found = [p for p in REPO_ROOT.rglob("*") if ".git" not in p.parts and p.name in forbidden]
    require(not found, f"Forbidden housekeeping files remain: {found[:5]}")


def main() -> None:
    validate_skills()
    validate_json_files()
    validate_hygiene()
    print("MavaLM repository validation passed")


if __name__ == "__main__":
    main()
