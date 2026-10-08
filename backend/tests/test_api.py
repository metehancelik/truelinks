"""The API end to end, on an in-memory database and the demo stub."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from truelinks.api.app import create_app
from truelinks.platform.settings import AppSettings

CLEAN = "01-clean-mc-b-1204.txt"
PROBLEMS = "02-problems-mc-b-1205.txt"
# The unit each sample lease names in its own text.
UNIT_OF = {CLEAN: "MC-B-1204", PROBLEMS: "MC-B-1205"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = AppSettings(database_url="sqlite://", llm_provider="stub")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def upload(client: TestClient, sample: str, unit_id: str | None = None) -> dict[str, Any]:
    """Add a bundled sample to a unit and return the lease once the agent has finished.

    The test client runs background tasks before returning, so one fetch is enough.
    """
    data = {"sample": sample, "unit_id": unit_id or UNIT_OF[sample]}
    created = client.post("/leases", data=data)
    assert created.status_code == 202
    assert created.json()["status"] == "PROCESSING"
    return client.get(f"/leases/{created.json()['id']}").json()


def outcomes(lease: dict[str, Any]) -> dict[str, str]:
    return {rule["id"]: rule["outcome"] for rule in lease["rules"]}


def decide_all_fields(client: TestClient, lease: dict[str, Any]) -> None:
    for field in lease["fields"]:
        url = f"/leases/{lease['id']}/fields/{field['name']}/decision"
        assert client.post(url, json={"decision": "ACCEPTED"}).status_code == 200


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_units_are_seeded_from_the_owners_file(client: TestClient) -> None:
    units = client.get("/units").json()

    assert len(units) == 5
    assert {unit["status"] for unit in units} == {"available", "occupied"}


def test_clean_lease_is_ready_for_review_and_linked_to_its_unit(client: TestClient) -> None:
    lease = upload(client, CLEAN)

    assert lease["status"] == "IN_REVIEW"
    assert lease["unit_id"] == "MC-B-1204"
    assert set(outcomes(lease).values()) == {"PASS"}
    assert [step["name"] for step in lease["trace"]] == [
        "read: text",
        "extract",
        "verify",
        "review",
        "rules",
    ]


def test_unit_page_shows_its_lease(client: TestClient) -> None:
    lease = upload(client, CLEAN)

    detail = client.get("/units/MC-B-1204").json()

    assert [item["id"] for item in detail["leases"]] == [lease["id"]]


def test_occupancy_changes_only_when_a_person_activates_the_lease(client: TestClient) -> None:
    lease = upload(client, CLEAN)
    assert client.get("/units/MC-B-1204").json()["unit"]["status"] == "available"

    refused = client.post(f"/leases/{lease['id']}/activate")
    assert refused.status_code == 409
    assert "still need a decision" in refused.json()["detail"]

    decide_all_fields(client, lease)
    activated = client.post(f"/leases/{lease['id']}/activate")

    assert activated.json()["status"] == "ACTIVE"
    assert client.get("/units/MC-B-1204").json()["unit"]["status"] == "occupied"
    # The lease must not fail R7 because of the occupancy it created itself.
    assert outcomes(activated.json())["R7"] == "PASS"


def test_problem_lease_fails_six_rules_and_flags_the_contradiction(client: TestClient) -> None:
    lease = upload(client, PROBLEMS)

    assert outcomes(lease) == {
        "R1": "FAIL",
        "R2": "FAIL",
        "R3": "PASS",
        "R4": "FAIL",
        "R5": "FAIL",
        "R6": "FAIL",
        "R7": "FAIL",
    }
    [term] = [field for field in lease["fields"] if field["name"] == "term_months"]
    assert term["status"] == "UNVERIFIED"
    assert term["issue"] == "CONTRADICTION"


def test_correcting_a_field_re_evaluates_the_rules_without_a_model_call(
    client: TestClient,
) -> None:
    lease = upload(client, PROBLEMS)
    url = f"/leases/{lease['id']}/fields/deposit_amount/decision"

    corrected = client.post(url, json={"decision": "CORRECTED", "value": 11000}).json()

    assert outcomes(corrected)["R1"] == "PASS"
    [deposit] = [field for field in corrected["fields"] if field["name"] == "deposit_amount"]
    assert deposit["value"] == 5000  # the agent's answer is kept
    assert deposit["corrected_value"] == 11000


def test_rejecting_a_field_makes_its_rules_not_determinable(client: TestClient) -> None:
    lease = upload(client, CLEAN)
    url = f"/leases/{lease['id']}/fields/annual_rent/decision"

    rejected = client.post(url, json={"decision": "REJECTED"}).json()

    assert outcomes(rejected)["R6"] == "NOT_DETERMINABLE"


def test_correction_must_fit_the_fields_type(client: TestClient) -> None:
    lease = upload(client, CLEAN)
    url = f"/leases/{lease['id']}/fields/expiry_date/decision"

    response = client.post(url, json={"decision": "CORRECTED", "value": "next spring"})

    assert response.status_code == 409


def test_a_lease_on_an_occupied_unit_cannot_be_activated(client: TestClient) -> None:
    lease = upload(client, PROBLEMS)
    decide_all_fields(client, lease)
    for rule_id, outcome in outcomes(lease).items():
        if outcome != "PASS":
            url = f"/leases/{lease['id']}/rules/{rule_id}/decision"
            assert client.post(url, json={"decision": "ACCEPTED"}).status_code == 200

    response = client.post(f"/leases/{lease['id']}/activate")

    assert response.status_code == 409
    assert "MC-B-1205 is occupied" in response.json()["detail"]


def test_failing_rules_must_be_acknowledged_before_activation(client: TestClient) -> None:
    lease = upload(client, PROBLEMS)
    decide_all_fields(client, lease)

    response = client.post(f"/leases/{lease['id']}/activate")

    assert response.status_code == 409
    assert "Rules still need a decision" in response.json()["detail"]


def test_a_lease_belongs_to_the_unit_it_was_added_to(client: TestClient) -> None:
    lease = upload(client, CLEAN, unit_id="MC-B-0902")

    assert lease["unit_id"] == "MC-B-0902"
    [r7] = [rule for rule in lease["rules"] if rule["id"] == "R7"]
    assert r7["outcome"] == "FAIL"
    assert "names unit MC-B-1204, but it was added to MC-B-0902" in r7["reason"]


def test_a_lease_needs_a_unit_in_the_records(client: TestClient) -> None:
    unknown = client.post("/leases", data={"sample": CLEAN, "unit_id": "MC-Z-0000"})
    missing = client.post("/leases", data={"sample": CLEAN})

    assert unknown.status_code == 404
    assert missing.status_code == 422


def test_agent_failure_is_recorded_on_the_lease(client: TestClient) -> None:
    files = {"file": ("other.txt", b"A lease the demo has never seen.", "text/plain")}

    created = client.post("/leases", files=files, data={"unit_id": "MC-B-1204"}).json()
    lease = client.get(f"/leases/{created['id']}").json()

    assert lease["status"] == "FAILED"
    assert "Demo mode only knows the bundled sample leases" in lease["error"]


def test_empty_document_is_refused(client: TestClient) -> None:
    files = {"file": ("blank.txt", b"   ", "text/plain")}
    response = client.post("/leases", files=files, data={"unit_id": "MC-B-1204"})

    assert response.status_code == 422


def test_sample_name_cannot_leave_the_samples_folder(client: TestClient) -> None:
    data = {"sample": "../../data/units.json", "unit_id": "MC-B-1204"}
    response = client.post("/leases", data=data)

    assert response.status_code == 404


def test_two_owners_can_have_the_same_unit_id_without_seeing_each_other(tmp_path: Path) -> None:
    """A unit id is unique per owner, not globally, and every query is scoped to one owner."""
    database = f"sqlite:///{tmp_path / 'shared.db'}"

    def owner(tenant_id: str) -> TestClient:
        settings = AppSettings(database_url=database, llm_provider="stub", tenant_id=tenant_id)
        return TestClient(create_app(settings))

    with owner("first") as first, owner("second") as second:
        lease = upload(first, CLEAN)

        assert len(second.get("/units").json()) == 5  # same ids, seeded again, no collision
        assert first.get("/units/MC-B-1204").json()["leases"][0]["id"] == lease["id"]
        assert second.get("/units/MC-B-1204").json()["leases"] == []
        assert second.get(f"/leases/{lease['id']}").status_code == 404
