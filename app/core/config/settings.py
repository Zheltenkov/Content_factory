"""Environment settings and threshold loading for core services."""

from __future__ import annotations

import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    """Small env-based settings object without framework coupling."""

    model_config = ConfigDict(extra="forbid")

    app_name: str = "content-factory"
    database_url: str | None = None
    environment: str = "local"
    thresholds_path: Path = Field(default_factory=lambda: Path(__file__).with_name("thresholds.yaml"))

    @classmethod
    def from_env(cls) -> "Settings":
        path = os.getenv("CONTENT_FACTORY_THRESHOLDS")
        return cls(
            app_name=os.getenv("APP_NAME", "content-factory"),
            database_url=os.getenv("DATABASE_URL"),
            environment=os.getenv("APP_ENV", "local"),
            thresholds_path=Path(path) if path else Path(__file__).with_name("thresholds.yaml"),
        )


class Thresholds(BaseModel):
    """Structured view over thresholds.yaml with dotted-path helpers."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    methodology: dict[str, Any] = Field(default_factory=dict)
    structural: dict[str, Any] = Field(default_factory=dict)
    checker: dict[str, Any] = Field(default_factory=dict)
    skills: dict[str, dict[str, Any]] = Field(default_factory=dict)
    enhancement: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Thresholds":
        if not path.exists():
            raise FileNotFoundError(f"thresholds.yaml not found: {path}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(payload)

    def get(self, dotted_path: str, default: Any = None) -> Any:
        value: Any = self.model_dump()
        for part in dotted_path.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def require_range(self, dotted_path: str) -> tuple[int | float, int | float]:
        value = self.get(dotted_path)
        if not isinstance(value, list | tuple) or len(value) != 2:
            raise ValueError(f"Threshold range {dotted_path!r} must contain exactly two values")
        return value[0], value[1]

    def skill_params(self, skill_id: str) -> dict[str, Any]:
        return deepcopy(self.skills.get(skill_id, {}))


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()


@lru_cache
def get_thresholds() -> Thresholds:
    return Thresholds.load(get_settings().thresholds_path)
