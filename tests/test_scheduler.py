from datetime import datetime

from app.config import Config, Daily, OneOff
from app.scheduler import (
    Trigger,
    compute_next_trigger,
    next_daily_occurrence,
    next_oneoff_occurrence,
)

NOW = datetime(2026, 9, 15, 20, 0, 0)


def test_daily_time_later_today_returns_today():
    assert next_daily_occurrence("23:30", NOW) == datetime(2026, 9, 15, 23, 30, 0)


def test_daily_time_already_passed_returns_tomorrow():
    assert next_daily_occurrence("02:00", NOW) == datetime(2026, 9, 16, 2, 0, 0)


def test_daily_time_exactly_now_returns_tomorrow():
    """正好等于当前时刻要顺延，否则会立刻触发。"""
    assert next_daily_occurrence("20:00", NOW) == datetime(2026, 9, 16, 20, 0, 0)


def test_daily_occurrence_crosses_month_boundary():
    assert next_daily_occurrence("02:00", datetime(2026, 9, 30, 23, 0, 0)) == datetime(
        2026, 10, 1, 2, 0, 0
    )


def test_daily_occurrence_crosses_leap_day():
    assert next_daily_occurrence("02:00", datetime(2028, 2, 28, 23, 0, 0)) == datetime(
        2028, 2, 29, 2, 0, 0
    )


def test_daily_occurrence_clears_seconds_and_microseconds():
    now = datetime(2026, 9, 15, 20, 0, 45, 123456)
    assert next_daily_occurrence("23:30", now).second == 0
    assert next_daily_occurrence("23:30", now).microsecond == 0


def test_oneoff_future_returns_that_moment():
    assert next_oneoff_occurrence("2026-09-15T23:30:00", NOW) == datetime(
        2026, 9, 15, 23, 30, 0
    )


def test_oneoff_past_returns_none():
    assert next_oneoff_occurrence("2026-09-14T23:30:00", NOW) is None


def test_oneoff_empty_returns_none():
    assert next_oneoff_occurrence("", NOW) is None


def test_oneoff_invalid_returns_none():
    assert next_oneoff_occurrence("tomorrow-ish", NOW) is None


def test_compute_returns_none_when_nothing_enabled():
    assert compute_next_trigger(Config(), NOW) is None


def test_compute_prefers_daily_when_only_daily_enabled():
    cfg = Config(daily=Daily(enabled=True, time="23:30"))
    assert compute_next_trigger(cfg, NOW) == Trigger("daily", datetime(2026, 9, 15, 23, 30, 0))


def test_compute_picks_earlier_of_two():
    cfg = Config(
        daily=Daily(enabled=True, time="23:30"),
        oneoff=OneOff(enabled=True, target="2026-09-15T21:00:00", label="今晚"),
    )
    assert compute_next_trigger(cfg, NOW).kind == "oneoff"


def test_compute_ignores_stale_oneoff_but_still_uses_daily():
    cfg = Config(
        daily=Daily(enabled=True, time="23:30"),
        oneoff=OneOff(enabled=True, target="2020-01-01T00:00:00", label="过期"),
    )
    result = compute_next_trigger(cfg, NOW)
    assert result.kind == "daily"


def test_compute_returns_none_when_only_stale_oneoff_enabled():
    cfg = Config(oneoff=OneOff(enabled=True, target="2020-01-01T00:00:00", label="过期"))
    assert compute_next_trigger(cfg, NOW) is None
