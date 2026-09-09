"""Boundary models for the claims intake service.

Everything that enters the service is parsed into one of these before any rule
runs. A payload that reaches the rule layer has already been proven well formed,
which is what keeps a shape problem and a content problem from arriving at the
caller as the same status code.

Day 2 assignment. Implement these against `docs/api-contract.md` sections 2 and 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal, NewType

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field

ClaimType = Literal["collision", "theft", "glass", "liability", "weather"]


def _reject_float(value: Any) -> Any:
    if type(value) is float:
        raise ValueError("must not be a float")
    return value


def _two_places_greater_than_zero(value: Decimal) -> Decimal:
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent != -2:
        raise ValueError("must have exactly two decimal places")
    if value <= 0:
        raise ValueError("must be greater than zero")
    return value


EstimatedAmount = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    AfterValidator(_two_places_greater_than_zero),
]


class NotificationRequest(BaseModel):
    """A first notice of loss as submitted by the claims portal.

    Fields and their constraints are specified in contract section 2.2. The model
    is responsible for the shape of the request and for nothing else. Whether the
    policy exists, whether the loss falls inside the term, and whether the amount
    is within the limit are rules, and rules live in `service.py`.
    """

    model_config = ConfigDict(extra="forbid")

    policy_number: str = Field(min_length=1)
    loss_date: date
    claim_type: ClaimType
    estimated_amount: EstimatedAmount
    description: str | None = None


class Policy(BaseModel):
    """A policy as this service works with it.

    Built from the `PolicyRecord` the policy client returns. The fields the rules
    compare against are the reason this model exists.
    """

    model_config = ConfigDict(extra="forbid")

    policy_number: str = Field(min_length=1)
    product: str = Field(min_length=1)
    effective_date: date
    expiry_date: date
    cancellation_date: date | None
    """Null means the policy was not cancelled (WI-0158, AC-3). A comparison
    against this field without a None check is a type error under mypy.
    """
    limit: EstimatedAmount
    permitted_claim_types: tuple[ClaimType, ...] = Field(min_length=1)


RuleId = NewType("RuleId", str)
ErrorCode = NewType("ErrorCode", str)


@dataclass(frozen=True)
class RuleFailure:
    """A rule that failed, named by its id and the contract code it maps to.

    `rule` and `code` are distinct types so a rule id cannot be passed where an
    error code belongs.
    """

    rule: RuleId
    code: ErrorCode


class ClaimRecord(BaseModel):
    """
    Duplicate matching (WI-0151) uses policy_number, loss_date, and claim_type.
    claim_reference and status are the success response in contract section 3.
    """

    model_config = ConfigDict(extra="forbid")

    claim_reference: str = Field(pattern=r"^CLM-\d{4}-\d{6}$")
    status: Literal["recorded"]
    policy_number: str = Field(min_length=1)
    loss_date: date
    claim_type: ClaimType
