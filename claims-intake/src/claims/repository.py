"""Persistence for recorded notifications.

An in-memory store is sufficient for Week 1 and is deliberate rather than a
shortcut. The rules do not know where a notification is stored, so replacing this
with a database in a later week is a change to one module.

The duplicate check that `WI-0151` describes is a query against what has been
recorded, which is why it belongs here rather than in the rule table.

Day 2 assignment. Implement against `docs/api-contract.md` section 3.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from claims.models import NotificationRequest, RecordedNotification


class NotificationRepository:
    """Stores recorded notifications and issues claim references."""

    def __init__(self) -> None:
        self._records: list[RecordedNotification] = []
        self._next_sequence = 1

    def record(self, notification: NotificationRequest) -> RecordedNotification:
        """Write a notification and return it with its issued claim reference.

        The reference format is fixed by contract section 3. References are unique
        and are never reissued.
        """
        claim_reference = f"CLM-{datetime.now(UTC).date().year}-{self._next_sequence:06d}"
        self._next_sequence += 1
        stored = RecordedNotification(
            notification=notification,
            claim_reference=claim_reference,
        )
        self._records.append(stored)
        return stored

    def find_matching(
        self,
        policy_number: str,
        loss_date: date,
        claim_type: str,
    ) -> RecordedNotification | None:
        """Return an existing recorded notification matching all three values.

        `WI-0151` AC-1 fixes which fields constitute a match. AC-3 is the reason
        this searches recorded notifications only: a submission that was refused
        was never written, so there is nothing for a later one to duplicate.
        """
        for stored in self._records:
            existing = stored.notification
            if (
                existing.policy_number == policy_number
                and existing.loss_date == loss_date
                and existing.claim_type == claim_type
            ):
                return stored
        return None
