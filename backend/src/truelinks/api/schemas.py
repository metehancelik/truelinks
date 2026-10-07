"""What the API returns. Kept apart from the tables so either can change alone."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

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


class UnitDetailOut(BaseModel):
    unit: UnitOut
    leases: list[LeaseOut]


class FieldDecisionIn(BaseModel):
    decision: Decision
    # Required when the decision is CORRECTED.
    value: Any = None


class RuleDecisionIn(BaseModel):
    decision: Decision


class SampleOut(BaseModel):
    name: str
