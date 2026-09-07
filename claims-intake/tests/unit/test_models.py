"""Model constraints from docs/api-contract.md.

Each parametrized test is one behaviour. Each named case is a constraint that
must break, or a fixture payload classified as dying at the model versus passing
the model and becoming a Day 3 rules problem.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from claims.models import (
    ClaimRecord,
    ErrorCode,
    NotificationRequest,
    Policy,
    RuleFailure,
    RuleId,
)

_DATA = Path(__file__).resolve().parents[2] / "data"


def _payloads(filename: str) -> dict[str, dict[str, Any]]:
    records = json.loads((_DATA / filename).read_text())
    return {record["id"]: record["payload"] for record in records}


_EDGE = _payloads("fnol_edge.json")
_INVALID = _payloads("fnol_invalid.json")
_VALID = _payloads("fnol_valid.json")
_POLICIES = {
    record["policy_number"]: record
    for record in json.loads((_DATA / "policies.json").read_text())
}

_WELL_FORMED = _EDGE["EDGE-01"]
_EDGE_POLICY = _POLICIES[_WELL_FORMED["policy_number"]]


def _policy(*, cancellation_date: date | None = None) -> Policy:
    return Policy.model_validate(_EDGE_POLICY).model_copy(
        update={"cancellation_date": cancellation_date}
    )


# --- NotificationRequest: extra fields (contract 2.2) ---


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({**_WELL_FORMED, "claim_id": "CLM-1"}, id="unknown_field"),
        pytest.param(
            {**{k: v for k, v in _WELL_FORMED.items() if k != "policy_number"}, "policy_numbr": "MOT-4479"},
            id="misspelled_field",
        ),
    ],
)
def test_notification_request_rejects_unknown_fields(payload: dict[str, Any]) -> None:
    """A field this contract does not define is refused. extra='forbid'."""
    with pytest.raises(ValidationError):
        NotificationRequest.model_validate(payload)


# --- NotificationRequest: required fields, no defaults (contract 2.2, 2.4) ---


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({k: v for k, v in _WELL_FORMED.items() if k != "policy_number"}, id="missing_policy_number"),
        pytest.param({k: v for k, v in _WELL_FORMED.items() if k != "loss_date"}, id="missing_loss_date"),
        pytest.param({k: v for k, v in _WELL_FORMED.items() if k != "claim_type"}, id="missing_claim_type"),
        pytest.param(_EDGE["EDGE-08"], id="EDGE-08_missing_estimated_amount"),
    ],
)
def test_notification_request_rejects_missing_required_fields(payload: dict[str, Any]) -> None:
    """Required fields have no defaults. A default would invent data the caller never sent."""
    with pytest.raises(ValidationError):
        NotificationRequest.model_validate(payload)


# --- NotificationRequest: empty strings (contract 2.2) ---


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("policy_number", id="empty_policy_number"),
        pytest.param("claim_type", id="empty_claim_type"),
    ],
)
def test_notification_request_rejects_empty_strings(field: str) -> None:
    """policy_number and claim_type are not empty."""
    with pytest.raises(ValidationError):
        NotificationRequest.model_validate({**_WELL_FORMED, field: ""})


# --- NotificationRequest: types used in later comparisons (contract 2.2) ---


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({**_WELL_FORMED, "loss_date": 20260315}, id="loss_date_not_a_string_date"),
        pytest.param({**_WELL_FORMED, "loss_date": "03/15/2026"}, id="loss_date_not_iso"),
        pytest.param({**_WELL_FORMED, "estimated_amount": 5000.00}, id="estimated_amount_is_float"),
        pytest.param({**_WELL_FORMED, "claim_type": 1}, id="claim_type_not_string"),
    ],
)
def test_notification_request_rejects_wrong_types(payload: dict[str, Any]) -> None:
    """loss_date is a date, estimated_amount is a Decimal. Never str after parse, never float."""
    with pytest.raises(ValidationError):
        NotificationRequest.model_validate(payload)


# --- NotificationRequest: claim_type vocabulary (contract 2.3, 4.1) ---


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_EDGE["EDGE-11"], id="EDGE-11_flood_not_in_vocabulary"),
        pytest.param({**_WELL_FORMED, "claim_type": "Collision"}, id="claim_type_wrong_case"),
    ],
)
def test_notification_request_rejects_claim_type_outside_vocabulary(payload: dict[str, Any]) -> None:
    """A claim_type outside collision, theft, glass, liability, weather is not well formed. V-5 never runs."""
    with pytest.raises(ValidationError):
        NotificationRequest.model_validate(payload)


# --- NotificationRequest: estimated_amount shape (contract 2.2, 4.1) ---


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_EDGE["EDGE-12"], id="EDGE-12_three_decimal_places"),
        pytest.param({**_WELL_FORMED, "estimated_amount": "0.00"}, id="amount_zero"),
        pytest.param({**_WELL_FORMED, "estimated_amount": "-1.00"}, id="amount_negative"),
    ],
)
def test_notification_request_rejects_invalid_estimated_amount(payload: dict[str, Any]) -> None:
    """Two decimal places, greater than zero. The service does not round."""
    with pytest.raises(ValidationError):
        NotificationRequest.model_validate(payload)


# --- NotificationRequest: description optional (contract 2.2) ---


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_VALID["VALID-06"], id="VALID-06_description_absent"),
        pytest.param({**_WELL_FORMED, "description": None}, id="description_null"),
    ],
)
def test_notification_request_accepts_absent_or_null_description(payload: dict[str, Any]) -> None:
    """description is optional. Absent and null are equivalent."""
    notification = NotificationRequest.model_validate(payload)
    assert notification.description is None


# --- Parsed types after a well-formed body (contract 2.2) ---


@pytest.mark.parametrize(
    ("attr", "expected_type"),
    [
        pytest.param("loss_date", date, id="loss_date_is_date"),
        pytest.param("estimated_amount", Decimal, id="estimated_amount_is_decimal"),
    ],
)
def test_notification_request_parsed_types(attr: str, expected_type: type) -> None:
    """Comparisons in the rules layer need a date and a Decimal, not str or float."""
    notification = NotificationRequest.model_validate(_WELL_FORMED)
    assert isinstance(getattr(notification, attr), expected_type)


# --- Fixture payloads: dies at the model vs Day 3 rules ---


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_EDGE["EDGE-08"], id="EDGE-08_missing_estimated_amount"),
        pytest.param(_EDGE["EDGE-11"], id="EDGE-11_claim_type_not_in_vocabulary"),
        pytest.param(_EDGE["EDGE-12"], id="EDGE-12_amount_three_decimal_places"),
    ],
)
def test_payload_dies_at_the_model(payload: dict[str, Any]) -> None:
    """Shape, vocabulary, or scale. MALFORMED_REQUEST. No rule in section 4 runs."""
    with pytest.raises(ValidationError):
        NotificationRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_EDGE["EDGE-01"], id="EDGE-01_inception_day"),
        pytest.param(_EDGE["EDGE-02"], id="EDGE-02_amount_equals_limit"),
        pytest.param(_EDGE["EDGE-03"], id="EDGE-03_expiry_day"),
        pytest.param(_EDGE["EDGE-04"], id="EDGE-04_cancellation_day"),
        pytest.param(_EDGE["EDGE-05"], id="EDGE-05_before_inception_and_over_limit"),
        pytest.param(_EDGE["EDGE-06"], id="EDGE-06_over_limit"),
        pytest.param(_EDGE["EDGE-07"], id="EDGE-07_policy_number_lowercase"),
        pytest.param(_EDGE["EDGE-09"], id="EDGE-09_collision_on_named_perils"),
        pytest.param(_EDGE["EDGE-10"], id="EDGE-10_cancelled_and_expired"),
        pytest.param(_INVALID["INVALID-01"], id="INVALID-01_policy_not_found"),
        pytest.param(_INVALID["INVALID-02"], id="INVALID-02_loss_before_inception"),
        pytest.param(_INVALID["INVALID-03"], id="INVALID-03_loss_after_expiry"),
        pytest.param(_INVALID["INVALID-04"], id="INVALID-04_amount_exceeds_limit"),
        pytest.param(_INVALID["INVALID-05"], id="INVALID-05_type_not_covered"),
        pytest.param(_INVALID["INVALID-06"], id="INVALID-06_duplicate"),
        pytest.param(_INVALID["INVALID-07"], id="INVALID-07_cancelled"),
    ],
)
def test_payload_passes_the_model(payload: dict[str, Any]) -> None:
    """Well formed. Refusal, if any, is a Day 3 rule (V-1 through V-7)."""
    NotificationRequest.model_validate(payload)


# --- Policy: typing for the rules layer ---


@pytest.mark.parametrize(
    "cancellation_date",
    [
        pytest.param(None, id="not_cancelled"),
        pytest.param(date(2026, 1, 15), id="cancelled"),
    ],
)
def test_policy_cancellation_date_is_date_or_none(cancellation_date: date | None) -> None:
    """date | None so `loss_date > policy.cancellation_date` without a None check fails mypy."""
    policy = _policy(cancellation_date=cancellation_date)
    assert policy.cancellation_date == cancellation_date


@pytest.mark.parametrize(
    ("attr", "expected_type"),
    [
        pytest.param("effective_date", date, id="effective_date_is_date"),
        pytest.param("expiry_date", date, id="expiry_date_is_date"),
        pytest.param("limit", Decimal, id="limit_is_decimal"),
    ],
)
def test_policy_comparison_fields_use_rule_types(attr: str, expected_type: type) -> None:
    """Same typing discipline as NotificationRequest. Never str, never float."""
    assert isinstance(getattr(_policy(), attr), expected_type)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({**_EDGE_POLICY, "holder": "A. Smith"}, id="unknown_field"),
        pytest.param(
            {k: v for k, v in _EDGE_POLICY.items() if k != "policy_number"},
            id="missing_policy_number",
        ),
        pytest.param(
            {k: v for k, v in _EDGE_POLICY.items() if k != "cancellation_date"},
            id="missing_cancellation_date",
        ),
        pytest.param({**_EDGE_POLICY, "policy_number": ""}, id="empty_policy_number"),
        pytest.param({**_EDGE_POLICY, "product": ""}, id="empty_product"),
        pytest.param(
            {**_EDGE_POLICY, "effective_date": "06/01/2025"},
            id="effective_date_not_iso",
        ),
        pytest.param(
            {**_EDGE_POLICY, "cancellation_date": "01/15/2026"},
            id="cancellation_date_not_iso",
        ),
        pytest.param({**_EDGE_POLICY, "limit": 50000.00}, id="limit_is_float"),
        pytest.param({**_EDGE_POLICY, "limit": "0.00"}, id="limit_zero"),
        pytest.param({**_EDGE_POLICY, "limit": "50000.999"}, id="limit_three_decimal_places"),
        pytest.param(
            {**_EDGE_POLICY, "permitted_claim_types": []},
            id="empty_permitted_claim_types",
        ),
        pytest.param(
            {**_EDGE_POLICY, "permitted_claim_types": ["flood"]},
            id="claim_type_outside_vocabulary",
        ),
    ],
)
def test_policy_rejects_invalid_or_structurally_wrong_data(payload: dict[str, Any]) -> None:
    """Invalid policy data is rejected the same way a bad request is rejected."""
    with pytest.raises(ValidationError):
        Policy.model_validate(payload)


def test_policy_cancellation_date_null_means_not_cancelled() -> None:
    """WI-0158 AC-3: null is not cancelled. The field is date | None, never a string."""
    policy = Policy.model_validate(_EDGE_POLICY)
    assert policy.cancellation_date is None
    assert isinstance(policy.effective_date, date)
    assert isinstance(policy.limit, Decimal)


# --- RuleFailure: frozen, rule id and error code are distinct (contract 4.2, 5) ---


@pytest.mark.parametrize(
    ("rule_id", "error_code"),
    [
        pytest.param("V-1", "POLICY_NOT_FOUND", id="V-1"),
        pytest.param("V-2", "LOSS_BEFORE_INCEPTION", id="V-2"),
        pytest.param("V-3", "LOSS_AFTER_EXPIRY", id="V-3"),
        pytest.param("V-4", "AMOUNT_EXCEEDS_LIMIT", id="V-4"),
        pytest.param("V-5", "TYPE_NOT_COVERED", id="V-5"),
        pytest.param("V-6", "DUPLICATE_NOTIFICATION", id="V-6"),
        pytest.param("V-7", "POLICY_CANCELLED", id="V-7"),
    ],
)
def test_rule_failure_keeps_rule_id_and_error_code_separate(rule_id: str, error_code: str) -> None:
    """Two fields, two types (NewType). A rule id cannot be passed where an error code goes."""
    failure = RuleFailure(rule=RuleId(rule_id), code=ErrorCode(error_code))
    assert failure.rule == rule_id
    assert failure.code == error_code


def test_rule_failure_is_frozen() -> None:
    """Immutable. A failure is a fact about a decision that already happened."""
    failure = RuleFailure(rule=RuleId("V-2"), code=ErrorCode("LOSS_BEFORE_INCEPTION"))
    with pytest.raises(FrozenInstanceError):
        failure.rule = RuleId("V-1")  # type: ignore[misc]


# --- ClaimRecord: recorded fields, not a wrapped request (contract 3) ---


@pytest.mark.parametrize(
    ("payload", "claim_reference"),
    [
        pytest.param(_VALID["VALID-01"], "CLM-2026-000317", id="VALID-01_recorded"),
        pytest.param(_EDGE["EDGE-01"], "CLM-2026-000001", id="EDGE-01_recorded"),
    ],
)
def test_claim_record_stores_recorded_fields_not_the_request(
    payload: dict[str, Any],
    claim_reference: str,
) -> None:
    """policy_number, loss_date, claim_type plus claim_reference and status."""
    notification = NotificationRequest.model_validate(payload)
    record = ClaimRecord(
        claim_reference=claim_reference,
        status="recorded",
        policy_number=notification.policy_number,
        loss_date=notification.loss_date,
        claim_type=notification.claim_type,
    )
    assert record.claim_reference == claim_reference
    assert record.status == "recorded"
    assert record.policy_number == notification.policy_number
    assert record.loss_date == notification.loss_date
    assert record.claim_type == notification.claim_type
    assert not hasattr(record, "notification")
    assert not hasattr(record, "description")
    assert not hasattr(record, "estimated_amount")
