from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, ForeignKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from truelinks.modules.lease.models import Decision
from truelinks.platform.db import Base


class IssueStatus(StrEnum):
    PROCESSING = "PROCESSING"  # the agent is looking at the photos
    OPEN = "OPEN"  # assessed; its work order waits for or has a decision
    FAILED = "FAILED"


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class IssueRow(Base):
    __tablename__ = "issues"
    # An issue can only be raised on a unit of its own tenant.
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "unit_id"], ["units.tenant_id", "units.unit_id"]),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    # The reporter names the unit, so an issue always belongs to one.
    unit_id: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[str] = mapped_column(Text)
    # [{"filename": ..., "media_type": ..., "path": ...}] in the order sent.
    photos: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default=IssueStatus.PROCESSING)
    error: Mapped[str | None] = mapped_column(Text)
    # The agent's assessment (condition, damages, equipment), never overwritten.
    assessment: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    trace: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    work_order: Mapped["WorkOrderRow | None"] = relationship(
        back_populates="issue", cascade="all, delete-orphan", uselist=False
    )


class WorkOrderRow(Base):
    __tablename__ = "work_orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id"), unique=True)
    # The current text: the agent's draft until a person edits it.
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(String(8))
    # The agent's original draft, kept when a person edits the fields above.
    draft: Mapped[dict[str, Any]] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(16), default=Decision.PENDING)
    decided_at: Mapped[datetime | None]

    issue: Mapped[IssueRow] = relationship(back_populates="work_order")
