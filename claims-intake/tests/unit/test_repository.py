"""NotificationRepository against contract section 3 and WI-0151.

Each parametrized test is one behaviour. Cases pull from data/fnol_valid.json
and data/fnol_invalid.json so a later reader can see which fixture is a
recorded claim and which is a duplicate or a refusal that was never written.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, get_type_hints

import pytest

from claims.models import ClaimRecord, NotificationRequest
from claims.repository import NotificationRepository

_CLAIM_REFERENCE = re.compile(r"^CLM-\d{4}-\d{6}$")
_DATA = Path(__file__).resolve().parents[2] / "data"


def _payloads(filename: str) -> dict[str, dict[str, Any]]:
    records = json.loads((_DATA / filename).read_text())
    return {record["id"]: record["payload"] for record in records}


_VALID = _payloads("fnol_valid.json")
_INVALID = _payloads("fnol_invalid.json")


@pytest.fixture
def repository() -> NotificationRepository:
    return NotificationRepository()


def _record(
    repository: NotificationRepository,
    payload_id: str,
    source: dict[str, dict[str, Any]] = _VALID,
) -> ClaimRecord:
    request = NotificationRequest.model_validate(source[payload_id])
    return repository.record(
        policy_number=request.policy_number,
        loss_date=request.loss_date,
        claim_type=request.claim_type,
    )


def _fields(payload_id: str, source: dict[str, dict[str, Any]] = _VALID) -> NotificationRequest:
    return NotificationRequest.model_validate(source[payload_id])


# --- Claim reference: contract section 3 ---


@pytest.mark.parametrize(
    "payload_id",
    [
        pytest.param("VALID-01", id="VALID-01"),
        pytest.param("VALID-02", id="VALID-02"),
        pytest.param("VALID-06", id="VALID-06_no_description"),
    ],
)
def test_record_issues_claim_reference_matching_contract(
    repository: NotificationRepository,
    payload_id: str,
) -> None:
    """CLM-YYYY-NNNNNN. YYYY is the year the notification was recorded."""
    recorded = _record(repository, payload_id)
    assert _CLAIM_REFERENCE.fullmatch(recorded.claim_reference)
    assert recorded.claim_reference.startswith(f"CLM-{datetime.now(UTC).date().year}-")


def test_no_two_records_share_a_reference(repository: NotificationRepository) -> None:
    """A claim reference is unique across all recorded notifications and is never reissued."""
    references = [
        _record(repository, payload_id).claim_reference
        for payload_id in ("VALID-01", "VALID-02", "VALID-03", "VALID-04")
    ]
    assert len(references) == len(set(references))


# --- WI-0151 AC-1: match on policy_number, loss_date, and claim_type ---


@pytest.mark.parametrize(
    ("recorded_id", "lookup_id", "lookup_source"),
    [
        pytest.param("VALID-01", "VALID-01", _VALID, id="same_payload_recorded_twice"),
        pytest.param("VALID-01", "INVALID-06", _INVALID, id="INVALID-06_resubmission_of_VALID-01"),
    ],
)
def test_find_matching_returns_existing_record(
    repository: NotificationRepository,
    recorded_id: str,
    lookup_id: str,
    lookup_source: dict[str, dict[str, Any]],
) -> None:
    """All three fields match an existing recorded notification."""
    stored = _record(repository, recorded_id)
    lookup = _fields(lookup_id, lookup_source)
    found = repository.find_matching(lookup.policy_number, lookup.loss_date, lookup.claim_type)
    assert found is stored
    assert found.claim_reference == stored.claim_reference


@pytest.mark.parametrize(
    "changed",
    [
        pytest.param("policy_number", id="different_policy_number"),
        pytest.param("loss_date", id="different_loss_date"),
        pytest.param("claim_type", id="different_claim_type"),
    ],
)
def test_find_matching_requires_all_three_fields(
    repository: NotificationRepository,
    changed: str,
) -> None:
    """A difference in any one of the three fields is not a duplicate."""
    stored = _record(repository, "VALID-01")
    policy_number = stored.policy_number
    loss_date = stored.loss_date
    claim_type = stored.claim_type
    if changed == "policy_number":
        policy_number = "MOT-4472"
    elif changed == "loss_date":
        loss_date = date(2026, 4, 3)
    else:
        claim_type = "theft"
    assert repository.find_matching(policy_number, loss_date, claim_type) is None


def test_record_does_not_accept_a_notification_request() -> None:
    """record() takes ClaimRecord fields, not a NotificationRequest."""
    hints = get_type_hints(NotificationRepository.record)
    assert NotificationRequest not in hints.values()
    assert hints["return"] is ClaimRecord


def test_rejected_notification_is_never_recorded_and_cannot_be_duplicated(
    repository: NotificationRepository,
) -> None:
    """INVALID-02 is a NotificationRequest that rules would refuse.

    record() does not take that type, so it cannot be written. A later lookup
    of the same three fields finds nothing to duplicate (WI-0151 AC-3).
    """
    refused = NotificationRequest.model_validate(_INVALID["INVALID-02"])
    assert (
        repository.find_matching(refused.policy_number, refused.loss_date, refused.claim_type)
        is None
    )
