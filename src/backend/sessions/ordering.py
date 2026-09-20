"""Deterministic session ordering.

Real calendar date is used when present; ties and sessions without a real date
fall back to creation order and id, so previous/next navigation never depends on
the database's row order.
"""

from datetime import date, datetime

from .models import SessionModel


def session_order_key(
    real_date: date | None, created_at: datetime, session_id: object
) -> tuple[date, datetime, str]:
    """The total order used for the ledger and for previous/next navigation."""
    return (
        real_date or created_at.date(),
        created_at,
        str(session_id),
    )


def session_key(session: SessionModel) -> tuple[date, datetime, str]:
    return session_order_key(session.real_date, session.created_at, session.id)
