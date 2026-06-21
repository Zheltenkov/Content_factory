"""Methodology rule contracts shared by harness, checker and gate."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.models.artifacts import ArtifactRef

Severity = Literal["hard", "soft"]


class _PositionalCompatModel(BaseModel):
    """Small compatibility shim for dataclass-style legacy constructors."""

    model_config = ConfigDict(extra="forbid")
    _positional_fields: ClassVar[tuple[str, ...]] = ()

    def __init__(self, *args: Any, **data: Any) -> None:
        if args:
            fields = type(self)._positional_fields
            if len(args) > len(fields):
                raise TypeError(f"Expected at most {len(fields)} positional arguments")
            for key, value in zip(fields, args, strict=False):
                data.setdefault(key, value)
        super().__init__(**data)


class RuleIssue(_PositionalCompatModel):
    """Deterministic methodology issue emitted by check.py skills."""

    _positional_fields = ("skill_id", "code", "severity", "message", "evidence")

    skill_id: str
    code: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class DocImage(_PositionalCompatModel):
    """Image metadata extracted from a generated document."""

    _positional_fields = ("path", "width", "height", "size_bytes", "format", "dpi", "is_vector")

    path: str
    width: int
    height: int
    size_bytes: int
    format: str
    dpi: int | None = None
    is_vector: bool = False


class GeneratedDoc(BaseModel):
    """Adapter-level document contract passed to methodology validators."""

    model_config = ConfigDict(extra="forbid")

    markdown: str
    images: list[DocImage] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    project_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
