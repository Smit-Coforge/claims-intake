"""HTTP surface for the claims intake service.

This layer does three things and no more: it parses the request, it calls the
service, and it maps the outcome to a status code. It holds no rule logic. A rule
that appears here is a rule the service layer cannot be tested for.

Day 4 lab. Implement against `docs/api-contract.md` sections 5 and 6.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from claims.models import ClaimRecord, NotificationRequest
from claims.policy_client import PolicyLookupFailed, StubPolicyClient
from claims.repository import NotificationRepository
from claims.service import ValidationOutcome, submit_notification

app = FastAPI(title="Claims Intake Service")

repository = NotificationRepository()
policy_client = StubPolicyClient()

# Contract section 6.
STATUS_BY_CODE: dict[str, int] = {
    "MALFORMED_REQUEST": 400,
    "POLICY_NOT_FOUND": 422,
    "LOSS_BEFORE_INCEPTION": 422,
    "LOSS_AFTER_EXPIRY": 422,
    "AMOUNT_EXCEEDS_LIMIT": 422,
    "TYPE_NOT_COVERED": 422,
    "DUPLICATE_NOTIFICATION": 409,
    "POLICY_CANCELLED": 422,
    "POLICY_MASTER_UNAVAILABLE": 503,
    "POLICY_MASTER_TIMEOUT": 504,
    "POLICY_MASTER_UNREADABLE": 502,
}

# Contract section 5 messages (display text; callers branch on `code`).
MESSAGE_BY_CODE: dict[str, str] = {
    "MALFORMED_REQUEST": "The request could not be interpreted.",
    "POLICY_NOT_FOUND": "No policy exists for the submitted policy number.",
    "LOSS_BEFORE_INCEPTION": "Loss date precedes policy inception.",
    "LOSS_AFTER_EXPIRY": "Loss date falls after policy expiry.",
    "AMOUNT_EXCEEDS_LIMIT": "Estimated amount exceeds the policy limit.",
    "TYPE_NOT_COVERED": "Claim type is not covered on this product.",
    "DUPLICATE_NOTIFICATION": "A notification for this loss has already been recorded.",
    "POLICY_CANCELLED": "The policy was cancelled on or before the loss date.",
    "POLICY_MASTER_UNAVAILABLE": "The policy master could not be reached.",
    "POLICY_MASTER_TIMEOUT": "The policy master did not respond in time.",
    "POLICY_MASTER_UNREADABLE": "The policy master response could not be read.",
}

LOOKUP_CODE_BY_REASON: dict[str, str] = {
    "unreachable": "POLICY_MASTER_UNAVAILABLE",
    "timeout": "POLICY_MASTER_TIMEOUT",
    "unparsable": "POLICY_MASTER_UNREADABLE",
}


def _serialize_value(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def _error_response(code: str, detail: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        status_code=STATUS_BY_CODE[code],
        content={
            "code": code,
            "message": MESSAGE_BY_CODE[code],
            "detail": {key: _serialize_value(val) for key, val in detail.items()},
        },
    )


def _malformed(field: str | None = None) -> JSONResponse:
    detail: dict[str, Any] = {}
    if field is not None:
        detail["field"] = field
    return _error_response("MALFORMED_REQUEST", detail)


def _field_from_validation_error(exc: ValidationError) -> str | None:
    errors = exc.errors()
    if not errors:
        return None
    for part in errors[0].get("loc", ()):
        if isinstance(part, str):
            return part
    return None


@app.post("/notifications")
async def create_notification(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return _malformed()

    try:
        notification = NotificationRequest.model_validate(body)
    except ValidationError as exc:
        return _malformed(_field_from_validation_error(exc))

    try:
        result = submit_notification(notification, policy_client, repository)
    except PolicyLookupFailed as exc:
        code = LOOKUP_CODE_BY_REASON[exc.reason]
        return _error_response(code, {"policy_number": exc.policy_number})

    if isinstance(result, ClaimRecord):
        return JSONResponse(
            status_code=201,
            content={
                "claim_reference": result.claim_reference,
                "status": result.status,
            },
        )

    assert isinstance(result, ValidationOutcome)
    assert result.code is not None
    assert result.rule is not None
    return _error_response(result.code, {"rule": result.rule, **result.detail})
