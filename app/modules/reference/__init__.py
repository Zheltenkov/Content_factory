"""Reference catalog module exports."""

from app.modules.reference.router import get_reference_repo, router
from app.modules.reference.service import ReferenceService

__all__ = ["ReferenceService", "get_reference_repo", "router"]
