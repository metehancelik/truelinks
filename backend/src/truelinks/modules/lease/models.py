from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, ForeignKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from truelinks.platform.db import Base


class LeaseStatus(StrEnum):
    PROCESSING = "PROCESSING"  # the agent is reading it
    IN_REVIEW = "IN_REVIEW"  # waiting for a person
    ACTIVE = "ACTIVE"  # accepted; the unit is occupied
    REJECTED = "REJECTED"
    FAILED = "FAILED"  # the agent could not process it


class Decision(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CORRECTED = "CORRECTED"  # a person replaced the value


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class LeaseRow(Base):
    __tablename__ = "leases"
    # A lease can only point at a unit of its own tenant.
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "unit_id"], ["units.tenant_id", "units.unit_id"]),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    # Set once the lease's unit reference matches exactly one unit record.
    unit_id: Mapped[str | None] = mapped_column(String(32), index=True)
    filename: Mapped[str]
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=LeaseStatus.PROCESSING)
    error: Mapped[str | None] = mapped_column(Text)
    # The evaluator's reading of the escalation clause, kept so rule R2 can be
    # re-evaluated without another model call.
    escalation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    trace: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Rule id -> a person's decision on that rule's flag.
    rule_decisions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    decided_at: Mapped[datetime | None]

    fields: Mapped[list["LeaseFieldRow"]] = relationship(
        back_populates="lease", cascade="all, delete-orphan", order_by="LeaseFieldRow.position"
    )


class LeaseFieldRow(Base):
    __tablename__ = "lease_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    lease_id: Mapped[str] = mapped_column(ForeignKey("leases.id"), index=True)
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String(64))
    # What the agent produced. Never overwritten.
    value: Mapped[Any | None] = mapped_column(JSON)
    quote: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    issue: Mapped[str | None] = mapped_column(String(32))
    explanation: Mapped[str | None] = mapped_column(Text)
    # What a person decided, kept beside the agent's answer rather than over it.
    decision: Mapped[str] = mapped_column(String(16), default=Decision.PENDING)
    corrected_value: Mapped[Any | None] = mapped_column(JSON)
    decided_at: Mapped[datetime | None]

    lease: Mapped[LeaseRow] = relationship(back_populates="fields")
