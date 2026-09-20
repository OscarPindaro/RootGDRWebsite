from datetime import UTC, date, datetime

from backend.sessions.ordering import session_order_key

EARLY = datetime(2024, 1, 1, tzinfo=UTC)
LATE = datetime(2024, 6, 1, tzinfo=UTC)


def test_real_date_takes_precedence_over_creation_order() -> None:
    # A session created later but played earlier sorts first.
    played_early = session_order_key(date(2024, 3, 1), LATE, "b")
    played_late = session_order_key(date(2024, 4, 1), EARLY, "a")
    assert played_early < played_late


def test_sessions_without_a_real_date_fall_back_to_creation_order() -> None:
    first = session_order_key(None, EARLY, "z")
    second = session_order_key(None, LATE, "a")
    assert first < second


def test_id_breaks_ties_deterministically() -> None:
    same = datetime(2024, 5, 5, tzinfo=UTC)
    assert session_order_key(None, same, "a") < session_order_key(None, same, "b")


def test_a_real_date_is_compared_against_a_creation_date() -> None:
    # A real date in February beats a session with no date created in March.
    with_date = session_order_key(date(2024, 2, 1), LATE, "a")
    without_date = session_order_key(None, datetime(2024, 3, 1, tzinfo=UTC), "b")
    assert with_date < without_date
