"""HTTP boundary for POST /notifications against contract sections 5 and 6.

These tests never call submit_notification. They exercise the FastAPI app in
claims.api.routes through TestClient. Each test wires a fresh repository and
policy client onto the routes module so suite order cannot leak state.
"""

from __future__ import annotations

import json
import re
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from claims.api import routes
from claims.policy_client import LookupFailureReason, StubPolicyClient
from claims.repository import NotificationRepository

_DATA = Path(__file__).resolve().parents[2] / "data"
_CLAIM_REFERENCE = re.compile(r"^CLM-\d{4}-\d{6}$")


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


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Fresh repository, policy client, and TestClient for every test."""
    routes.repository = NotificationRepository()
    routes.policy_client = StubPolicyClient()
    with TestClient(routes.app) as test_client:
        yield test_client


def _post(client: TestClient, payload: dict[str, Any]) -> Response:
    return cast(Response, client.post("/notifications", json=payload))


def _assert_error(
    response: Response,
    *,
    status: int,
    code: str,
    detail: dict[str, Any],
    expect_rule: bool,
) -> dict[str, Any]:
    assert response.status_code == status
    body = cast(dict[str, Any], response.json())
    assert body["code"] == code
    assert "message" in body
    for key, value in detail.items():
        assert body["detail"][key] == value
    if expect_rule:
        assert body["detail"]["rule"] == detail["rule"]
    else:
        assert "rule" not in body["detail"]
    return body


# --- 201 success ---


def test_valid_01_creates_notification(client: TestClient) -> None:
    """VALID-01 passes every rule and is recorded."""
    response = _post(client, _VALID["VALID-01"])
    assert response.status_code == 201
    body = response.json()
    assert _CLAIM_REFERENCE.match(body["claim_reference"])
    assert body["status"] == "recorded"


# --- Rule refusals V-1 through V-7 ---


def test_invalid_01_v1_policy_not_found(client: TestClient) -> None:
    """INVALID-01: policy number is absent from the master."""
    payload = _INVALID["INVALID-01"]
    _assert_error(
        _post(client, payload),
        status=422,
        code="POLICY_NOT_FOUND",
        detail={"rule": "V-1", "policy_number": payload["policy_number"]},
        expect_rule=True,
    )


def test_invalid_02_v2_loss_before_inception(client: TestClient) -> None:
    """INVALID-02: loss_date precedes policy effective_date."""
    payload = _INVALID["INVALID-02"]
    policy = _POLICIES[payload["policy_number"]]
    _assert_error(
        _post(client, payload),
        status=422,
        code="LOSS_BEFORE_INCEPTION",
        detail={
            "rule": "V-2",
            "loss_date": payload["loss_date"],
            "effective_date": policy["effective_date"],
        },
        expect_rule=True,
    )


def test_invalid_03_v3_loss_after_expiry(client: TestClient) -> None:
    """INVALID-03: loss_date falls after policy expiry_date."""
    payload = _INVALID["INVALID-03"]
    policy = _POLICIES[payload["policy_number"]]
    _assert_error(
        _post(client, payload),
        status=422,
        code="LOSS_AFTER_EXPIRY",
        detail={
            "rule": "V-3",
            "loss_date": payload["loss_date"],
            "expiry_date": policy["expiry_date"],
        },
        expect_rule=True,
    )


def test_invalid_04_v4_amount_exceeds_limit(client: TestClient) -> None:
    """INVALID-04: estimated_amount is above the policy limit."""
    payload = _INVALID["INVALID-04"]
    policy = _POLICIES[payload["policy_number"]]
    _assert_error(
        _post(client, payload),
        status=422,
        code="AMOUNT_EXCEEDS_LIMIT",
        detail={
            "rule": "V-4",
            "estimated_amount": payload["estimated_amount"],
            "limit": policy["limit"],
        },
        expect_rule=True,
    )


def test_invalid_05_v5_type_not_covered(client: TestClient) -> None:
    """INVALID-05: claim_type is not permitted on the product."""
    payload = _INVALID["INVALID-05"]
    _assert_error(
        _post(client, payload),
        status=422,
        code="TYPE_NOT_COVERED",
        detail={"rule": "V-5", "claim_type": payload["claim_type"]},
        expect_rule=True,
    )


def test_invalid_06_v6_duplicate_notification(client: TestClient) -> None:
    """INVALID-06: same policy_number, loss_date, and claim_type already recorded."""
    first = _post(client, _VALID["VALID-01"])
    assert first.status_code == 201
    claim_reference = first.json()["claim_reference"]

    _assert_error(
        _post(client, _INVALID["INVALID-06"]),
        status=409,
        code="DUPLICATE_NOTIFICATION",
        detail={"rule": "V-6", "claim_reference": claim_reference},
        expect_rule=True,
    )


def test_invalid_07_v7_policy_cancelled(client: TestClient) -> None:
    """INVALID-07: loss_date is on or after cancellation_date."""
    payload = _INVALID["INVALID-07"]
    policy = _POLICIES[payload["policy_number"]]
    _assert_error(
        _post(client, payload),
        status=422,
        code="POLICY_CANCELLED",
        detail={
            "rule": "V-7",
            "loss_date": payload["loss_date"],
            "cancellation_date": policy["cancellation_date"],
        },
        expect_rule=True,
    )


# --- Parse failure: not a rule code ---


def test_edge_08_malformed_missing_field(client: TestClient) -> None:
    """EDGE-08: required estimated_amount absent → MALFORMED_REQUEST, not a rule."""
    body = _assert_error(
        _post(client, _EDGE["EDGE-08"]),
        status=400,
        code="MALFORMED_REQUEST",
        detail={"field": "estimated_amount"},
        expect_rule=False,
    )
    assert body["code"] != "AMOUNT_EXCEEDS_LIMIT"


# --- Policy master lookup failures ---


@pytest.mark.parametrize(
    ("reason", "status", "code"),
    [
        pytest.param("timeout", 504, "POLICY_MASTER_TIMEOUT", id="timeout"),
        pytest.param("unreachable", 503, "POLICY_MASTER_UNAVAILABLE", id="unreachable"),
        pytest.param("unparsable", 502, "POLICY_MASTER_UNREADABLE", id="unparsable"),
    ],
)
def test_policy_master_fail_with(
    reason: LookupFailureReason,
    status: int,
    code: str,
) -> None:
    """StubPolicyClient.fail_with maps to the three POLICY_MASTER_* responses."""
    routes.repository = NotificationRepository()
    routes.policy_client = StubPolicyClient(fail_with=reason)
    payload = _VALID["VALID-01"]
    with TestClient(routes.app) as client:
        _assert_error(
            _post(client, payload),
            status=status,
            code=code,
            detail={"policy_number": payload["policy_number"]},
            expect_rule=False,
        )
