"""SQLAlchemy repository adapter for methodology revision loop state."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import base64
from typing import Any
from collections.abc import Iterator

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

from app.core.config import get_settings
from app.core.methodology.revision.contracts import HumanApprovalCheckpoint, MethodologistChangeRequest, ScopedRevisionResult

metadata = sa.MetaData()

REVISION_SESSION = sa.Table(
    "methodology_revision_session",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("run_id", sa.Text(), nullable=False),
    sa.Column("artifact_ref", sa.Text(), nullable=False, server_default=""),
    sa.Column("status", sa.Text(), nullable=False, server_default="open"),
    sa.Column("current_node", sa.Text(), nullable=True),
    sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.CheckConstraint("status IN ('open', 'approved', 'rejected', 'rolled_back', 'closed')", name="ck_methodology_revision_session_status"),
)

REVISION_CHECKPOINT = sa.Table(
    "methodology_revision_checkpoint",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("session_id", sa.Integer(), sa.ForeignKey("methodology_revision_session.id", ondelete="CASCADE"), nullable=False),
    sa.Column("checkpoint_id", sa.Text(), nullable=False),
    sa.Column("stage", sa.Text(), nullable=False),
    sa.Column("node_id", sa.Text(), nullable=False),
    sa.Column("resume_from_node", sa.Text(), nullable=False),
    sa.Column("artifact_hash", sa.Text(), nullable=False),
    sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
    sa.Column("payload_json", sa.JSON(), nullable=False),
    sa.Column("context_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("decided_at", sa.DateTime(), nullable=True),
    sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'rolled_back')", name="ck_methodology_revision_checkpoint_status"),
)

REVISION_CHANGE_REQUEST = sa.Table(
    "methodology_revision_change_request",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("session_id", sa.Integer(), sa.ForeignKey("methodology_revision_session.id", ondelete="CASCADE"), nullable=False),
    sa.Column("checkpoint_row_id", sa.Integer(), sa.ForeignKey("methodology_revision_checkpoint.id", ondelete="SET NULL"), nullable=True),
    sa.Column("action_id", sa.Text(), nullable=False),
    sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
    sa.Column("target_stage", sa.Text(), nullable=False),
    sa.Column("target_selector", sa.Text(), nullable=False, server_default=""),
    sa.Column("scope", sa.Text(), nullable=False),
    sa.Column("instruction", sa.Text(), nullable=False),
    sa.Column("payload_json", sa.JSON(), nullable=False),
    sa.Column("result_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("processed_at", sa.DateTime(), nullable=True),
    sa.UniqueConstraint("session_id", "action_id", name="uq_methodology_revision_change_action"),
    sa.CheckConstraint("status IN ('pending', 'applied', 'skipped', 'rejected')", name="ck_methodology_revision_change_status"),
)

sa.Index("idx_methodology_revision_session_run", REVISION_SESSION.c.run_id)
sa.Index("idx_methodology_revision_checkpoint_session", REVISION_CHECKPOINT.c.session_id, REVISION_CHECKPOINT.c.created_at)
sa.Index("idx_methodology_revision_change_pending", REVISION_CHANGE_REQUEST.c.session_id, REVISION_CHANGE_REQUEST.c.status)


@dataclass(frozen=True)
class RevisionSessionRecord:
    id: int
    run_id: str
    artifact_ref: str
    status: str


@dataclass(frozen=True)
class RevisionCheckpointRecord:
    id: int
    session_id: int
    checkpoint: HumanApprovalCheckpoint
    status: str
    context_snapshot: dict[str, Any]


@dataclass(frozen=True)
class RevisionChangeRequestRecord:
    id: int
    session_id: int
    action_id: str
    request: MethodologistChangeRequest
    status: str
    checkpoint_row_id: int | None = None
    result: ScopedRevisionResult | None = None


def create_revision_schema(engine: Engine) -> None:
    metadata.create_all(engine)


def default_revision_repo() -> "MethodologyRevisionRepo":
    from sqlalchemy import create_engine

    if not get_settings().database_url:
        raise RuntimeError("DATABASE_URL is required for methodology revision repository")
    return MethodologyRevisionRepo(create_engine(get_settings().database_url))


class MethodologyRevisionRepo:
    """Durable storage for approval checkpoints and scoped revision actions."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        with self.engine.begin() as connection:
            yield connection

    def create_session(self, *, run_id: str, artifact_ref: str = "", payload: dict[str, Any] | None = None, current_node: str | None = None) -> RevisionSessionRecord:
        with self._connect() as con:
            session_id = _insert_id(
                con,
                REVISION_SESSION.insert().values(
                    run_id=run_id,
                    artifact_ref=artifact_ref,
                    current_node=current_node,
                    payload_json=_to_jsonable(payload or {}),
                    updated_at=_now(),
                ),
            )
            return RevisionSessionRecord(id=session_id, run_id=run_id, artifact_ref=artifact_ref, status="open")

    def save_checkpoint(
        self,
        session_id: int,
        checkpoint: HumanApprovalCheckpoint,
        *,
        context_snapshot: dict[str, Any] | None = None,
    ) -> RevisionCheckpointRecord:
        payload = checkpoint.model_dump(mode="json")
        with self._connect() as con:
            row_id = _insert_id(
                con,
                REVISION_CHECKPOINT.insert().values(
                    session_id=session_id,
                    checkpoint_id=checkpoint.id,
                    stage=checkpoint.stage,
                    node_id=checkpoint.node_id,
                    resume_from_node=checkpoint.resume_from_node,
                    artifact_hash=checkpoint.artifact_hash,
                    payload_json=payload,
                    context_snapshot_json=_to_jsonable(context_snapshot or {}),
                ),
            )
            self._touch_session(con, session_id, current_node=checkpoint.node_id)
            return RevisionCheckpointRecord(row_id, session_id, checkpoint, "pending", context_snapshot or {})

    def record_change_request(
        self,
        session_id: int,
        request: MethodologistChangeRequest,
        *,
        action_id: str,
        checkpoint_row_id: int | None = None,
    ) -> RevisionChangeRequestRecord:
        with self._connect() as con:
            row_id = _insert_id(
                con,
                REVISION_CHANGE_REQUEST.insert().values(
                    session_id=session_id,
                    checkpoint_row_id=checkpoint_row_id,
                    action_id=action_id,
                    target_stage=request.target_stage,
                    target_selector=request.target_selector,
                    scope=request.scope,
                    instruction=request.instruction,
                    payload_json=request.model_dump(mode="json"),
                ),
            )
            self._touch_session(con, session_id)
            return RevisionChangeRequestRecord(row_id, session_id, action_id, request, "pending", checkpoint_row_id)

    def pending_change_requests(self, session_id: int) -> list[RevisionChangeRequestRecord]:
        with self._connect() as con:
            rows = con.execute(
                REVISION_CHANGE_REQUEST.select()
                .where(REVISION_CHANGE_REQUEST.c.session_id == session_id, REVISION_CHANGE_REQUEST.c.status == "pending")
                .order_by(REVISION_CHANGE_REQUEST.c.id)
            ).mappings().all()
            return [_change_record(row) for row in rows]

    def store_revision_result(self, session_id: int, action_id: str, result: ScopedRevisionResult) -> bool:
        with self._connect() as con:
            updated = con.execute(
                REVISION_CHANGE_REQUEST.update()
                .where(REVISION_CHANGE_REQUEST.c.session_id == session_id, REVISION_CHANGE_REQUEST.c.action_id == action_id)
                .values(status=result.status, result_json=result.model_dump(mode="json"), processed_at=_now())
            ).rowcount
            self._touch_session(con, session_id)
            return bool(updated)

    def decide_checkpoint(self, checkpoint_row_id: int, *, status: str) -> bool:
        if status not in {"approved", "rejected", "rolled_back"}:
            raise ValueError("checkpoint decision status must be approved/rejected/rolled_back")
        with self._connect() as con:
            updated = con.execute(
                REVISION_CHECKPOINT.update()
                .where(REVISION_CHECKPOINT.c.id == checkpoint_row_id)
                .values(status=status, decided_at=_now())
            ).rowcount
            return bool(updated)

    def load_checkpoint(self, checkpoint_row_id: int) -> RevisionCheckpointRecord | None:
        with self._connect() as con:
            row = con.execute(REVISION_CHECKPOINT.select().where(REVISION_CHECKPOINT.c.id == checkpoint_row_id)).mappings().first()
            return _checkpoint_record(row) if row else None

    def latest_checkpoint(self, session_id: int) -> RevisionCheckpointRecord | None:
        with self._connect() as con:
            row = con.execute(
                REVISION_CHECKPOINT.select()
                .where(REVISION_CHECKPOINT.c.session_id == session_id)
                .order_by(REVISION_CHECKPOINT.c.id.desc())
                .limit(1)
            ).mappings().first()
            return _checkpoint_record(row) if row else None

    def rollback_to_checkpoint(self, checkpoint_row_id: int) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute(REVISION_CHECKPOINT.select().where(REVISION_CHECKPOINT.c.id == checkpoint_row_id)).mappings().first()
            if not row:
                return None
            con.execute(
                REVISION_CHECKPOINT.update()
                .where(REVISION_CHECKPOINT.c.id == checkpoint_row_id)
                .values(status="rolled_back", decided_at=_now())
            )
            con.execute(
                REVISION_SESSION.update()
                .where(REVISION_SESSION.c.id == row["session_id"])
                .values(status="rolled_back", payload_json=row["context_snapshot_json"], current_node=row["node_id"], updated_at=_now())
            )
            return _from_jsonable(row["context_snapshot_json"] or {})

    @staticmethod
    def _touch_session(con: Connection, session_id: int, *, current_node: str | None = None) -> None:
        values: dict[str, Any] = {"updated_at": _now()}
        if current_node is not None:
            values["current_node"] = current_node
        con.execute(REVISION_SESSION.update().where(REVISION_SESSION.c.id == session_id).values(**values))


def _checkpoint_record(row: Any) -> RevisionCheckpointRecord:
    checkpoint = HumanApprovalCheckpoint.model_validate(row["payload_json"])
    return RevisionCheckpointRecord(
        id=int(row["id"]),
        session_id=int(row["session_id"]),
        checkpoint=checkpoint,
        status=str(row["status"]),
        context_snapshot=_from_jsonable(row["context_snapshot_json"] or {}),
    )


def _change_record(row: Any) -> RevisionChangeRequestRecord:
    result_payload = dict(row["result_json"] or {})
    result = ScopedRevisionResult.model_validate(result_payload) if result_payload.get("action_id") else None
    return RevisionChangeRequestRecord(
        id=int(row["id"]),
        session_id=int(row["session_id"]),
        action_id=str(row["action_id"]),
        request=MethodologistChangeRequest.model_validate(row["payload_json"]),
        status=str(row["status"]),
        checkpoint_row_id=int(row["checkpoint_row_id"]) if row["checkpoint_row_id"] is not None else None,
        result=result,
    )


def _insert_id(con: Connection, stmt: Any) -> int:
    result = con.execute(stmt)
    inserted = result.inserted_primary_key
    if inserted:
        return int(inserted[0])
    return int(con.execute(sa.text("select last_insert_rowid()")).scalar_one())


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes_b64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]
    return value


def _from_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"__bytes_b64__"}:
            return base64.b64decode(str(value["__bytes_b64__"]).encode("ascii"))
        return {key: _from_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_from_jsonable(item) for item in value]
    return value
