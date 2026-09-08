"""Rule table V-1 through V-7 against contract sections 4.1 and 4.2.

Each parametrized test is one rule. Named cases cover both sides of the
boundary, the boundary itself, and every work-item acceptance criterion for
that rule, including absence (cancellation_date is None). Evaluation order is
fixed by 4.1, so these call evaluate_notification rather than a single rule.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from claims.models import NotificationRequest
from claims.policy_client import StubPolicyClient
from claims.repository import NotificationRepository
from claims.service import ValidationOutcome, evaluate_notification

_DATA = Path(__file__).resolve().parents[2] / "data"


def _payloads(filename: str) -> dict[str, dict[str, Any]]:
    records = json.loads((_DATA / filename).read_text())
    return {record["id"]: record["payload"] for record in records}


_EDGE = _payloads("fnol_edge.json")
_INVALID = _payloads("fnol_invalid.json")
_VALID = _payloads("fnol_valid.json")


@pytest.fixture
def repository() -> NotificationRepository:
    return NotificationRepository()


def _evaluate(
    policy_client: StubPolicyClient,
    repository: NotificationRepository,
    payload: dict[str, Any],
    **overrides: Any,
) -> tuple[ValidationOutcome, NotificationRequest]:
    notification = NotificationRequest.model_validate({**payload, **overrides})
    outcome = evaluate_notification(notification, policy_client, repository)
    return outcome, notification


def _assert_passed(outcome: ValidationOutcome) -> None:
    assert outcome.passed is True
    assert outcome.rule is None
    assert outcome.code is None


def _assert_failed(outcome: ValidationOutcome, rule: str, code: str) -> None:
    assert outcome.passed is False
    assert outcome.rule == rule
    assert outcome.code == code


# --- V-1: policy_number exists in the policy master ---


@pytest.mark.parametrize(
    ("payload", "overrides", "expected_code"),
    [
        pytest.param(_VALID["VALID-01"], {}, None, id="VALID-01_exists"),
        pytest.param(
            _INVALID["INVALID-01"],
            {},
            "POLICY_NOT_FOUND",
            id="INVALID-01_WI-0142_AC-4_not_in_master",
        ),
        pytest.param(
            _EDGE["EDGE-07"],
            {},
            "POLICY_NOT_FOUND",
            id="EDGE-07_case_only_difference",
        ),
    ],
)
def test_v1_policy_number_exists(
    policy_client: StubPolicyClient,
    repository: NotificationRepository,
    payload: dict[str, Any],
    overrides: dict[str, Any],
    expected_code: str | None,
) -> None:
    """Exact match. Case is not folded. A miss is V-1, not a later policy rule."""
    outcome, _notification = _evaluate(policy_client, repository, payload, **overrides)
    if expected_code is None:
        _assert_passed(outcome)
        return
    _assert_failed(outcome, "V-1", expected_code)
    assert outcome.detail["policy_number"] == _notification.policy_number
    assert outcome.code != "LOSS_BEFORE_INCEPTION"


# --- V-2: loss_date >= effective_date (WI-0142) ---


@pytest.mark.parametrize(
    ("payload", "overrides", "expected_code"),
    [
        pytest.param(
            _EDGE["EDGE-01"],
            {"loss_date": "2026-03-14"},
            "LOSS_BEFORE_INCEPTION",
            id="day_before_inception",
        ),
        pytest.param(
            _EDGE["EDGE-01"],
            {},
            None,
            id="EDGE-01_WI-0142_AC-3_inception_day",
        ),
        pytest.param(
            _EDGE["EDGE-01"],
            {"loss_date": "2026-03-16"},
            None,
            id="day_after_inception",
        ),
        pytest.param(
            _INVALID["INVALID-02"],
            {},
            "LOSS_BEFORE_INCEPTION",
            id="INVALID-02_WI-0142_AC-1_before_inception",
        ),
        pytest.param(
            _EDGE["EDGE-05"],
            {},
            "LOSS_BEFORE_INCEPTION",
            id="EDGE-05_before_inception_not_over_limit",
        ),
    ],
)
def test_v2_loss_on_or_after_inception(
    policy_client: StubPolicyClient,
    repository: NotificationRepository,
    payload: dict[str, Any],
    overrides: dict[str, Any],
    expected_code: str | None,
) -> None:
    """Inclusive inception. A miss is V-2, even when a later rule would also fail."""
    outcome, notification = _evaluate(policy_client, repository, payload, **overrides)
    if expected_code is None:
        _assert_passed(outcome)
        return
    _assert_failed(outcome, "V-2", expected_code)
    assert outcome.detail["loss_date"] == notification.loss_date
    assert repository.find_matching(
        notification.policy_number, notification.loss_date, notification.claim_type
    ) is None
    assert outcome.code != "AMOUNT_EXCEEDS_LIMIT"


# --- V-3: loss_date <= expiry_date ---


@pytest.mark.parametrize(
    ("payload", "overrides", "expected_code"),
    [
        pytest.param(
            _EDGE["EDGE-03"],
            {"loss_date": "2026-02-27"},
            None,
            id="day_before_expiry",
        ),
        pytest.param(_EDGE["EDGE-03"], {}, None, id="EDGE-03_expiry_day"),
        pytest.param(
            _EDGE["EDGE-03"],
            {"loss_date": "2026-03-01"},
            "LOSS_AFTER_EXPIRY",
            id="day_after_expiry",
        ),
        pytest.param(
            _INVALID["INVALID-03"],
            {},
            "LOSS_AFTER_EXPIRY",
            id="INVALID-03_after_expiry",
        ),
    ],
)
def test_v3_loss_on_or_before_expiry(
    policy_client: StubPolicyClient,
    repository: NotificationRepository,
    payload: dict[str, Any],
    overrides: dict[str, Any],
    expected_code: str | None,
) -> None:
    """Inclusive expiry. The day after the term is LOSS_AFTER_EXPIRY."""
    outcome, notification = _evaluate(policy_client, repository, payload, **overrides)
    if expected_code is None:
        _assert_passed(outcome)
        return
    _assert_failed(outcome, "V-3", expected_code)
    assert outcome.detail["loss_date"] == notification.loss_date


# --- V-4: estimated_amount <= limit ---


@pytest.mark.parametrize(
    ("payload", "overrides", "expected_code"),
    [
        pytest.param(
            _EDGE["EDGE-02"],
            {"estimated_amount": "49999.99"},
            None,
            id="one_cent_below_limit",
        ),
        pytest.param(_EDGE["EDGE-02"], {}, None, id="EDGE-02_equals_limit"),
        pytest.param(
            _EDGE["EDGE-02"],
            {"estimated_amount": "50000.01"},
            "AMOUNT_EXCEEDS_LIMIT",
            id="one_cent_over_limit",
        ),
        pytest.param(
            _INVALID["INVALID-04"],
            {},
            "AMOUNT_EXCEEDS_LIMIT",
            id="INVALID-04_exceeds_limit",
        ),
        pytest.param(
            _EDGE["EDGE-06"],
            {},
            "AMOUNT_EXCEEDS_LIMIT",
            id="EDGE-06_exceeds_limit",
        ),
    ],
)
def test_v4_amount_within_limit(
    policy_client: StubPolicyClient,
    repository: NotificationRepository,
    payload: dict[str, Any],
    overrides: dict[str, Any],
    expected_code: str | None,
) -> None:
    """Inclusive limit. Equal is within cover; one cent over is not."""
    outcome, notification = _evaluate(policy_client, repository, payload, **overrides)
    if expected_code is None:
        _assert_passed(outcome)
        return
    _assert_failed(outcome, "V-4", expected_code)
    assert outcome.detail["estimated_amount"] == notification.estimated_amount


# --- V-5: claim_type permitted on the product ---


@pytest.mark.parametrize(
    ("payload", "overrides", "expected_code"),
    [
        pytest.param(
            _VALID["VALID-05"],
            {},
            None,
            id="VALID-05_liability_on_liability_only",
        ),
        pytest.param(
            _VALID["VALID-04"],
            {},
            None,
            id="VALID-04_weather_on_named_perils",
        ),
        pytest.param(
            _EDGE["EDGE-09"],
            {"claim_type": "theft"},
            None,
            id="theft_on_named_perils",
        ),
        pytest.param(
            _INVALID["INVALID-05"],
            {},
            "TYPE_NOT_COVERED",
            id="INVALID-05_collision_on_liability_only",
        ),
        pytest.param(
            _EDGE["EDGE-09"],
            {},
            "TYPE_NOT_COVERED",
            id="EDGE-09_collision_on_named_perils",
        ),
    ],
)
def test_v5_claim_type_permitted_on_product(
    policy_client: StubPolicyClient,
    repository: NotificationRepository,
    payload: dict[str, Any],
    overrides: dict[str, Any],
    expected_code: str | None,
) -> None:
    """A vocabulary type that the product does not permit is TYPE_NOT_COVERED."""
    outcome, notification = _evaluate(policy_client, repository, payload, **overrides)
    if expected_code is None:
        _assert_passed(outcome)
        return
    _assert_failed(outcome, "V-5", expected_code)
    assert outcome.detail["claim_type"] == notification.claim_type


# --- V-6: no recorded match on policy_number, loss_date, claim_type (WI-0151) ---


@pytest.mark.parametrize(
    ("record_id", "payload", "overrides", "expected_code"),
    [
        pytest.param(
            "VALID-01",
            _INVALID["INVALID-06"],
            {},
            "DUPLICATE_NOTIFICATION",
            id="INVALID-06_WI-0151_AC-1_same_three_fields",
        ),
        pytest.param(
            "VALID-01",
            _VALID["VALID-01"],
            {"policy_number": "MOT-4472"},
            None,
            id="different_policy_number",
        ),
        pytest.param(
            "VALID-01",
            _VALID["VALID-01"],
            {"loss_date": "2026-04-03"},
            None,
            id="different_loss_date",
        ),
        pytest.param(
            "VALID-01",
            _VALID["VALID-01"],
            {"claim_type": "theft"},
            None,
            id="different_claim_type",
        ),
        pytest.param(
            None,
            _INVALID["INVALID-02"],
            {},
            "LOSS_BEFORE_INCEPTION",
            id="WI-0151_AC-3_prior_refusal_is_not_duplicate",
        ),
    ],
)
def test_v6_no_duplicate_on_policy_loss_and_type(
    policy_client: StubPolicyClient,
    repository: NotificationRepository,
    record_id: str | None,
    payload: dict[str, Any],
    overrides: dict[str, Any],
    expected_code: str | None,
) -> None:
    """Match is all three fields. A refusal was never written, so it cannot duplicate."""
    stored = None
    if record_id is not None:
        recorded = NotificationRequest.model_validate(_VALID[record_id])
        stored = repository.record(
            policy_number=recorded.policy_number,
            loss_date=recorded.loss_date,
            claim_type=recorded.claim_type,
        )
    outcome, notification = _evaluate(policy_client, repository, payload, **overrides)
    if expected_code is None:
        _assert_passed(outcome)
        return
    if expected_code == "DUPLICATE_NOTIFICATION":
        assert stored is not None
        _assert_failed(outcome, "V-6", expected_code)
        assert outcome.detail["claim_reference"] == stored.claim_reference
        return
    _assert_failed(outcome, "V-2", expected_code)
    assert repository.find_matching(
        notification.policy_number, notification.loss_date, notification.claim_type
    ) is None


# --- V-7: cancellation_date is null OR loss_date < cancellation_date (WI-0158) ---


@pytest.mark.parametrize(
    ("payload", "overrides", "expected_code"),
    [
        pytest.param(
            _VALID["VALID-01"],
            {},
            None,
            id="WI-0158_AC-3_cancellation_date_none",
        ),
        pytest.param(
            _INVALID["INVALID-07"],
            {"loss_date": "2026-01-31"},
            None,
            id="day_before_cancellation",
        ),
        pytest.param(
            _EDGE["EDGE-04"],
            {},
            "POLICY_CANCELLED",
            id="EDGE-04_WI-0158_AC-2_cancellation_day",
        ),
        pytest.param(
            _INVALID["INVALID-07"],
            {},
            "POLICY_CANCELLED",
            id="INVALID-07_WI-0158_AC-1_after_cancellation",
        ),
        pytest.param(
            _EDGE["EDGE-10"],
            {},
            "POLICY_CANCELLED",
            id="EDGE-10_WI-0158_AC-4_cancelled_not_expired",
        ),
    ],
)
def test_v7_loss_before_cancellation_or_not_cancelled(
    policy_client: StubPolicyClient,
    repository: NotificationRepository,
    payload: dict[str, Any],
    overrides: dict[str, Any],
    expected_code: str | None,
) -> None:
    """Null means not cancelled. Cover ends at the start of the cancellation date."""
    outcome, notification = _evaluate(policy_client, repository, payload, **overrides)
    if expected_code is None:
        _assert_passed(outcome)
        return
    _assert_failed(outcome, "V-7", expected_code)
    assert outcome.detail["loss_date"] == notification.loss_date
    assert outcome.code != "LOSS_AFTER_EXPIRY"
