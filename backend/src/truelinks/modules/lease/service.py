"""What can happen to a lease record: the agent fills it in, a person decides.

The agent's answers and a person's decisions are stored side by side. Rules
are never stored: they are recomputed from the current values, so correcting a
field updates every rule that depends on it at once.
"""

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from truelinks.modules.lease.documents import Document, signature_page_path
from truelinks.modules.lease.models import Decision, LeaseFieldRow, LeaseRow, LeaseStatus
from truelinks.modules.lease.pipeline import analyse_lease
from truelinks.modules.lease.rules import (
    EscalationAssessment,
    Outcome,
    Rule,
    RuleResult,
    evaluate_rules,
)
from truelinks.modules.lease.schema import parse_field_value, to_json_value
from truelinks.modules.lease.verification import FieldStatus, VerificationIssue, VerifiedField
from truelinks.modules.unit.models import get_unit, list_units
from truelinks.modules.unit.records import find_units
from truelinks.platform.llm.types import LLMImage, LLMProvider
from truelinks.platform.trace import StepTrace

UNIT_REFERENCE = "unit_reference"


class LeaseActionError(Exception):
    """A person asked for something the lease's current state does not allow."""


def create_lease(
    session: Session,
    tenant_id: str,
    unit_id: str,
    filename: str,
    document: Document,
    uploads_dir: Path,
) -> LeaseRow:
    """Store a lease on the unit a person added it to; the agent reads it next."""
    # Reading is the first step of the trace, so a lease read by OCR says so.
    read = StepTrace(f"read: {document.method}", None, document.duration_ms)
    lease = LeaseRow(
        tenant_id=tenant_id,
        unit_id=unit_id,
        filename=filename,
        text=document.text,
        trace=[asdict(read)],
    )
    session.add(lease)
    session.flush()
    if document.signature_page is not None:
        signature_page_path(uploads_dir, lease.id).write_bytes(document.signature_page)
    session.commit()
    return lease


async def process_lease(
    session: Session, llm: LLMProvider, ruleset: list[Rule], lease_id: str, uploads_dir: Path
) -> None:
    """Run the lease agent and store its answer for review."""
    lease = session.get_one(LeaseRow, lease_id)
    units = [row.to_unit() for row in list_units(session, lease.tenant_id)]
    page_path = signature_page_path(uploads_dir, lease.id)
    signature_page = (
        LLMImage(media_type="image/png", data=page_path.read_bytes())
        if page_path.is_file()
        else None
    )

    try:
        analysis = await analyse_lease(llm, lease.text, ruleset, units, signature_page)
    except Exception as error:  # the job boundary: record the failure, do not lose it
        lease.status = LeaseStatus.FAILED
        lease.error = str(error)
        session.commit()
        return

    lease.fields = [
        LeaseFieldRow(
            position=position,
            name=field.name,
            value=to_json_value(field.value),
            quote=field.quote,
            status=field.status,
            issue=field.issue,
            explanation=field.explanation,
        )
        for position, field in enumerate(analysis.fields)
    ]
    lease.escalation = asdict(analysis.escalation) if analysis.escalation else None
    lease.trace = [*lease.trace, *(asdict(step) for step in analysis.trace)]
    lease.status = LeaseStatus.IN_REVIEW
    if lease.unit_id is None:
        _match_unit(session, lease)
    session.commit()


def current_fields(lease: LeaseRow) -> list[VerifiedField]:
    """The record as it stands: the agent's answers with a person's decisions applied."""
    return [_current_field(row) for row in lease.fields]


def _current_field(row: LeaseFieldRow) -> VerifiedField:
    if row.decision == Decision.REJECTED:
        return VerifiedField(row.name, None, row.quote, FieldStatus.MISSING)
    if row.decision == Decision.CORRECTED:
        value = parse_field_value(row.name, row.corrected_value)
        return VerifiedField(row.name, value, row.quote, FieldStatus.VERIFIED)
    return VerifiedField(
        row.name,
        parse_field_value(row.name, row.value),
        row.quote,
        FieldStatus(row.status),
        VerificationIssue(row.issue) if row.issue else None,
        row.explanation,
    )


def current_rules(session: Session, lease: LeaseRow, ruleset: list[Rule]) -> list[RuleResult]:
    if not lease.fields:
        return []
    units = [row.to_unit() for row in list_units(session, lease.tenant_id)]
    escalation = EscalationAssessment(**lease.escalation) if lease.escalation else None
    occupied_unit_id = lease.unit_id if lease.status == LeaseStatus.ACTIVE else None
    return evaluate_rules(
        ruleset, current_fields(lease), units, escalation, occupied_unit_id, lease.unit_id
    )


def decide_field(
    session: Session, lease: LeaseRow, name: str, decision: Decision, value: Any = None
) -> None:
    _require_in_review(lease)
    row = next((field for field in lease.fields if field.name == name), None)
    if row is None:
        raise LeaseActionError(f'This lease has no field "{name}".')

    if decision == Decision.CORRECTED:
        try:
            row.corrected_value = to_json_value(parse_field_value(name, value))
        except ValueError as error:
            raise LeaseActionError(f"{value!r} is not a valid value for {name}.") from error
    else:
        row.corrected_value = None

    row.decision = decision
    row.decided_at = datetime.now(UTC)
    if name == UNIT_REFERENCE and lease.unit_id is None:
        _match_unit(session, lease)
    session.commit()


def decide_rule(session: Session, lease: LeaseRow, rule_id: str, decision: Decision) -> None:
    _require_in_review(lease)
    lease.rule_decisions = lease.rule_decisions | {rule_id: decision}
    session.commit()


def activate_lease(session: Session, lease: LeaseRow, ruleset: list[Rule]) -> None:
    """Accept the lease and mark its unit occupied. The only place occupancy changes."""
    _require_in_review(lease)

    pending = [row.name for row in lease.fields if row.decision == Decision.PENDING]
    if pending:
        raise LeaseActionError(
            f"{len(pending)} fields still need a decision: {', '.join(pending)}."
        )

    unflagged = [
        result.rule.id
        for result in current_rules(session, lease, ruleset)
        if result.outcome is not Outcome.PASS and result.rule.id not in lease.rule_decisions
    ]
    if unflagged:
        raise LeaseActionError(f"Rules still need a decision: {', '.join(unflagged)}.")

    unit = get_unit(session, lease.tenant_id, lease.unit_id) if lease.unit_id else None
    if unit is None:
        raise LeaseActionError("The lease is not linked to a unit in the owner's records.")
    if unit.status != "available":
        raise LeaseActionError(f"Unit {unit.unit_id} is {unit.status}; it cannot take a new lease.")

    unit.status = "occupied"
    lease.status = LeaseStatus.ACTIVE
    lease.decided_at = datetime.now(UTC)
    session.commit()


def reject_lease(session: Session, lease: LeaseRow) -> None:
    _require_in_review(lease)
    lease.status = LeaseStatus.REJECTED
    lease.decided_at = datetime.now(UTC)
    session.commit()


def _require_in_review(lease: LeaseRow) -> None:
    if lease.status != LeaseStatus.IN_REVIEW:
        raise LeaseActionError(f"The lease is {lease.status}, not in review.")


def _match_unit(session: Session, lease: LeaseRow) -> None:
    """Link the lease to its unit when the reference names exactly one.

    Only for leases stored before a lease was always added to a unit: a person's
    choice of unit is never overridden by the agent's reading of the text.
    """
    reference = next(
        (field.value for field in current_fields(lease) if field.name == UNIT_REFERENCE), None
    )
    units = [row.to_unit() for row in list_units(session, lease.tenant_id)]
    matches = find_units(reference, units) if isinstance(reference, str) else []
    lease.unit_id = matches[0].unit_id if len(matches) == 1 else None
