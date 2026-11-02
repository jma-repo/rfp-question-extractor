"""Paths and settings shared by every command."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(os.environ.get("RFPX_REPO", Path(__file__).resolve().parents[2])).resolve()


@dataclass(frozen=True)
class Settings:
    root: Path = REPO_ROOT

    @cached_property
    def config(self) -> dict[str, Any]:
        with (self.root / "configs" / "rfpx.yaml").open(encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def path(self, key: str) -> Path:
        return self.root / self.config["paths"][key]

    @property
    def max_chars(self) -> int:
        return int(self.config["chunk"]["max_chars"])

    @property
    def near_duplicate(self) -> float:
        return float(self.config["dedupe"]["near_duplicate"])

    @property
    def llm(self) -> dict[str, Any]:
        return dict(self.config["llm"])


def settings() -> Settings:
    return Settings()
