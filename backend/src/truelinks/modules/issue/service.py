"""What can happen to an issue: the agent assesses it, a person decides on the work order."""

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from truelinks.modules.issue.models import IssueRow, IssueStatus, WorkOrderRow
from truelinks.modules.issue.pipeline import assess_issue
from truelinks.modules.issue.schema import Urgency
from truelinks.modules.lease.models import Decision
from truelinks.modules.unit.models import UnitRow
from truelinks.platform.llm.types import LLMImage, LLMProvider

MAX_PHOTOS = 6
MAX_PHOTO_BYTES = 8 * 1024 * 1024


class IssueActionError(Exception):
    """A person asked for something the issue's current state does not allow."""


def create_issue(
    session: Session,
    tenant_id: str,
    unit_id: str,
    note: str,
    photos: list[tuple[str, str, bytes]],
    uploads_dir: Path,
) -> IssueRow:
    """Store the report and its photos. `photos` is (filename, media type, content)."""
    if not photos:
        raise IssueActionError("An issue report needs at least one photo.")
    if len(photos) > MAX_PHOTOS:
        raise IssueActionError(f"At most {MAX_PHOTOS} photos per report.")

    stored: list[dict[str, str]] = []
    for filename, media_type, content in photos:
        if not media_type.startswith("image/"):
            raise IssueActionError(f"{filename} is not an image.")
        if len(content) > MAX_PHOTO_BYTES:
            raise IssueActionError(f"{filename} is larger than 8 MB.")
        # Stored under a generated name: the reporter's file name is never a path.
        path = uploads_dir / f"{uuid4().hex}{Path(filename).suffix.lower()}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        stored.append({"filename": filename, "media_type": media_type, "path": str(path)})

    issue = IssueRow(tenant_id=tenant_id, unit_id=unit_id, note=note, photos=stored)
    session.add(issue)
    session.commit()
    return issue


async def process_issue(session: Session, llm: LLMProvider, issue_id: str) -> None:
    """Run the issue agent and store its assessment and draft work order."""
    issue = session.get_one(IssueRow, issue_id)
    unit = session.get_one(UnitRow, issue.unit_id).to_unit()
    photos = [
        LLMImage(media_type=photo["media_type"], data=Path(photo["path"]).read_bytes())
        for photo in issue.photos
    ]

    try:
        analysis = await assess_issue(llm, unit, issue.note, photos)
    except Exception as error:  # the job boundary: record the failure, do not lose it
        issue.status = IssueStatus.FAILED
        issue.error = str(error)
        session.commit()
        return

    draft = analysis.assessment.work_order.model_dump()
    issue.assessment = analysis.assessment.model_dump(exclude={"work_order"})
    issue.flags = [str(flag) for flag in analysis.flags]
    issue.trace = [asdict(step) for step in analysis.trace]
    issue.work_order = WorkOrderRow(draft=draft, **draft)
    issue.status = IssueStatus.OPEN
    session.commit()


def list_unit_issues(session: Session, unit_id: str) -> list[IssueRow]:
    query = select(IssueRow).where(IssueRow.unit_id == unit_id).order_by(IssueRow.created_at.desc())
    return list(session.scalars(query))


def is_open(issue: IssueRow) -> bool:
    """An issue stays open until its work order is rejected."""
    if issue.status == IssueStatus.PROCESSING:
        return True
    return issue.work_order is not None and issue.work_order.decision != Decision.REJECTED


def decide_work_order(
    session: Session,
    work_order: WorkOrderRow,
    decision: Decision,
    title: str | None = None,
    description: str | None = None,
    urgency: Urgency | None = None,
) -> None:
    """Accept or reject the draft. A person may reword it; the agent's draft is kept."""
    if decision not in (Decision.ACCEPTED, Decision.REJECTED):
        raise IssueActionError("A work order is either accepted or rejected.")

    work_order.title = title or work_order.title
    work_order.description = description or work_order.description
    work_order.urgency = urgency or work_order.urgency
    work_order.decision = decision
    work_order.decided_at = datetime.now(UTC)
    session.commit()
