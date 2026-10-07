"""What the API returns. Kept apart from the tables so either can change alone."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from truelinks.modules.issue.models import IssueRow, WorkOrderRow
from truelinks.modules.issue.schema import Urgency
from truelinks.modules.lease.models import Decision, LeaseFieldRow, LeaseRow
from truelinks.modules.lease.rules import RuleResult
from truelinks.modules.unit.models import UnitRow


class UnitOut(BaseModel):
    unit_id: str
    label: str
    unit_type: str
    status: str
    building_name: str
    property_name: str

    @classmethod
    def of(cls, row: UnitRow) -> "UnitOut":
        return cls.model_validate(row, from_attributes=True)


class FieldOut(BaseModel):
    name: str
    value: Any
    quote: str | None
    status: str
    issue: str | None
    explanation: str | None
    decision: str
    corrected_value: Any

    @classmethod
    def of(cls, row: LeaseFieldRow) -> "FieldOut":
        return cls.model_validate(row, from_attributes=True)


class RuleOut(BaseModel):
    id: str
    description: str
    severity: str
    outcome: str
    reason: str
    inputs: list[str]
    decision: str

    @classmethod
    def of(cls, result: RuleResult, decisions: dict[str, str]) -> "RuleOut":
        return cls(
            id=result.rule.id,
            description=result.rule.description,
            severity=result.rule.severity,
            outcome=result.outcome,
            reason=result.reason,
            inputs=[field.name for field in result.inputs],
            decision=decisions.get(result.rule.id, Decision.PENDING),
        )


class LeaseOut(BaseModel):
    id: str
    filename: str
    status: str
    error: str | None
    unit_id: str | None
    created_at: datetime
    fields: list[FieldOut]
    rules: list[RuleOut]
    trace: list[dict[str, Any]]

    @classmethod
    def of(cls, lease: LeaseRow, rules: list[RuleResult]) -> "LeaseOut":
        return cls(
            id=lease.id,
            filename=lease.filename,
            status=lease.status,
            error=lease.error,
            unit_id=lease.unit_id,
            created_at=lease.created_at,
            fields=[FieldOut.of(row) for row in lease.fields],
            rules=[RuleOut.of(result, lease.rule_decisions) for result in rules],
            trace=lease.trace,
        )


class WorkOrderOut(BaseModel):
    id: str
    title: str
    description: str
    urgency: str
    # The agent's original wording, for comparison after a person edits it.
    draft: dict[str, Any]
    decision: str

    @classmethod
    def of(cls, row: WorkOrderRow) -> "WorkOrderOut":
        return cls.model_validate(row, from_attributes=True)


class IssueOut(BaseModel):
    id: str
    unit_id: str
    note: str
    status: str
    error: str | None
    photo_count: int
    assessment: dict[str, Any] | None
    flags: list[str]
    trace: list[dict[str, Any]]
    created_at: datetime
    work_order: WorkOrderOut | None

    @classmethod
    def of(cls, row: IssueRow) -> "IssueOut":
        return cls(
            id=row.id,
            unit_id=row.unit_id,
            note=row.note,
            status=row.status,
            error=row.error,
            photo_count=len(row.photos),
            assessment=row.assessment,
            flags=row.flags,
            trace=row.trace,
            created_at=row.created_at,
            work_order=WorkOrderOut.of(row.work_order) if row.work_order else None,
        )


class UnitSummaryOut(UnitOut):
    """A unit as the list shows it: is there a lease to review, are issues open."""

    lease_status: str | None
    open_issues: int


class UnitDetailOut(BaseModel):
    """The one screen an owner opens: a unit, its leases and the issues raised on it."""

    unit: UnitOut
    leases: list[LeaseOut]
    issues: list[IssueOut]


class WorkOrderDecisionIn(BaseModel):
    decision: Decision
    # Optional rewording by the person who accepts it.
    title: str | None = None
    description: str | None = None
    urgency: Urgency | None = None


class FieldDecisionIn(BaseModel):
    decision: Decision
    # Required when the decision is CORRECTED.
    value: Any = None


class RuleDecisionIn(BaseModel):
    decision: Decision


class SampleOut(BaseModel):
    name: str
