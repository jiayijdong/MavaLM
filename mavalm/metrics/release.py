"""Helpers for locating records inside a PSCbench-style data package.

Layout: ``<root>/data/<split>/{ground_truth,model_generated_answers,<judge>_evaluated_answers}/<sample>/*.json``
with ``<root>/metadata/models.json`` mapping generator labels to file tokens.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward until the MavaLM repository root is found."""
    start = (start or Path(__file__)).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "skills" / "registry.json").is_file():
            return candidate
    raise FileNotFoundError("Could not locate the MavaLM repository root")


@dataclass(frozen=True)
class ModelCatalog:
    """Ordered generator catalogue (label, file token, aliases) from models.json."""

    labels: tuple[str, ...]
    token_to_label: dict[str, str]
    aliases: dict[str, str]

    @classmethod
    def load(cls, path: Path) -> "ModelCatalog":
        with Path(path).open(encoding="utf-8") as handle:
            metadata = json.load(handle)
        labels: list[str] = []
        token_to_label: dict[str, str] = {}
        aliases: dict[str, str] = {}
        for entry in metadata["models"]:
            label = str(entry["label"])
            token = str(entry["file_token"])
            labels.append(label)
            token_to_label[token] = label
            for alias in entry.get("evaluation_aliases", []):
                aliases[str(alias)] = token
        return cls(tuple(labels), token_to_label, aliases)

    @property
    def tokens_longest_first(self) -> tuple[str, ...]:
        tokens = set(self.token_to_label) | set(self.aliases)
        return tuple(sorted(tokens, key=len, reverse=True))

    def label_for(self, token: str) -> str:
        token = self.aliases.get(token, token)
        return self.token_to_label.get(token, token)

    def canonical_token(self, token: str) -> str:
        return self.aliases.get(token, token)


def model_token_from_evaluation_name(name: str, tokens: Sequence[str]) -> str:
    """Resolve the generator token encoded in a verifier audit file name.

    Both release spellings are supported:
    ``Evaluation_<token>_<sample>_by_<judge>.json`` (PerovskiteNet split) and
    ``Evaluation_<token>_GT_<sample>.json`` (Perovskite Database split).
    Tokens must be tried longest-first so that ``o3`` never shadows ``o3_mini``.
    """
    core = name
    if core.startswith("Evaluation_"):
        core = core[len("Evaluation_") :]
    if core.endswith(".json"):
        core = core[: -len(".json")]
    lowered = core.casefold()
    for token in tokens:
        probe = token.casefold()
        if lowered == probe or lowered.startswith(probe + "_"):
            return token
    return "unknown"


def evaluation_files(evaluation_root: Path) -> Iterator[Path]:
    """Yield every verifier audit JSON under ``<root>/<sample_id>/``."""
    yield from sorted(Path(evaluation_root).glob("*/*.json"))
