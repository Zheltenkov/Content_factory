"""Backward-compatible CSV facade for curriculum plan endpoints."""

from __future__ import annotations

from app.core.models import UPSkeleton
from app.modules.curriculum.export import CSV_COLUMN_ALIASES, CSV_HEADERS, up_from_csv as _up_from_csv
from app.modules.curriculum.export import up_to_csv

__all__ = ["CSV_COLUMN_ALIASES", "CSV_HEADERS", "up_from_csv", "up_to_csv"]


def up_from_csv(text: str, *, title: str | None = None, direction: str | None = None) -> UPSkeleton:
    up = _up_from_csv(text, title=title, direction=direction)
    return up.model_copy(update={"metadata": {**up.metadata, "source": "csv_import"}})
