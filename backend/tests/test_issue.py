"""Issue reporting end to end, on an in-memory database and the demo stub."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from truelinks.api.app import create_app
from truelinks.modules.issue.demo import AC_LEAK
from truelinks.modules.issue.pipeline import IssueFlag, check_assessment
from truelinks.modules.issue.schema import IssueAssessment
from truelinks.platform.settings import AppSettings

UNIT = "MC-B-1204"
PHOTO = ("leak.jpg", b"\xff\xd8\xff not a real photo, the stub does not look", "image/jpeg")


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = AppSettings(database_url="sqlite://", llm_provider="stub", uploads_dir=tmp_path)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def report(client: TestClient, note: str, photos: int = 1) -> dict[str, Any]:
    """Report an issue and return it once the agent has finished."""
    files = [("photos", PHOTO)] * photos
    created = client.post(f"/units/{UNIT}/issues", data={"note": note}, files=files)
    assert created.status_code == 202
    assert created.json()["status"] == "PROCESSING"
    return client.get(f"/issues/{created.json()['id']}").json()


def test_report_becomes_an_assessment_and_a_draft_work_order(client: TestClient) -> None:
    issue = report(client, "The AC is dripping water down the wall.")

    assert issue["status"] == "OPEN"
    assert issue["assessment"]["overall_condition"] == "damaged"
    assert issue["assessment"]["equipment"][0]["name"] == "split AC indoor unit"
    assert issue["work_order"]["title"] == "AC unit leaking water onto wall"
    assert issue["work_order"]["decision"] == "PENDING"
    assert [step["name"] for step in issue["trace"]] == ["assess", "check"]


def test_issue_appears_on_its_units_page_next_to_the_lease(client: TestClient) -> None:
    client.post("/leases", data={"sample": "01-clean-mc-b-1204.txt"})
    issue = report(client, "Hot water heater looks rusty.")

    detail = client.get(f"/units/{UNIT}").json()

    assert [item["id"] for item in detail["issues"]] == [issue["id"]]
    assert len(detail["leases"]) == 1


def test_unit_list_counts_open_issues(client: TestClient) -> None:
    report(client, "Paint is peeling.")

    [unit] = [item for item in client.get("/units").json() if item["unit_id"] == UNIT]

    assert unit["open_issues"] == 1


def test_person_can_reword_and_accept_the_draft_and_the_original_is_kept(
    client: TestClient,
) -> None:
    issue = report(client, "The AC is dripping.")
    url = f"/work-orders/{issue['work_order']['id']}/decision"

    decided = client.post(url, json={"decision": "ACCEPTED", "title": "Fix AC leak"}).json()

    assert decided["work_order"]["decision"] == "ACCEPTED"
    assert decided["work_order"]["title"] == "Fix AC leak"
    assert decided["work_order"]["draft"]["title"] == "AC unit leaking water onto wall"


def test_rejecting_the_work_order_closes_the_issue(client: TestClient) -> None:
    issue = report(client, "The AC is dripping.")

    client.post(f"/work-orders/{issue['work_order']['id']}/decision", json={"decision": "REJECTED"})

    [unit] = [item for item in client.get("/units").json() if item["unit_id"] == UNIT]
    assert unit["open_issues"] == 0


def test_photo_is_served_by_its_number_in_the_report(client: TestClient) -> None:
    issue = report(client, "The AC is dripping.", photos=2)

    assert client.get(f"/issues/{issue['id']}/photos/2").content == PHOTO[1]
    assert client.get(f"/issues/{issue['id']}/photos/3").status_code == 404


def test_report_needs_an_image(client: TestClient) -> None:
    files = [("photos", ("notes.txt", b"hello", "text/plain"))]

    response = client.post(f"/units/{UNIT}/issues", data={"note": "x"}, files=files)

    assert response.status_code == 422
    assert "not an image" in response.json()["detail"]


def test_report_on_an_unknown_unit_is_refused(client: TestClient) -> None:
    response = client.post("/units/NOPE/issues", data={"note": "x"}, files=[("photos", PHOTO)])

    assert response.status_code == 404


def test_finding_that_points_at_a_photo_that_was_not_sent_is_flagged() -> None:
    assessment = IssueAssessment.model_validate(AC_LEAK)

    assert check_assessment(assessment, photo_count=1) == []
    assert check_assessment(assessment, photo_count=0) == [IssueFlag.INVALID_PHOTO_REFERENCE]


def test_report_with_no_visible_damage_is_flagged_for_inspection() -> None:
    assessment = IssueAssessment.model_validate(AC_LEAK | {"damages": []})

    assert check_assessment(assessment, photo_count=1) == [IssueFlag.NO_VISIBLE_DAMAGE]
