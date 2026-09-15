from datetime import datetime

from app.formatting import format_remaining, format_trigger_time

NOW = datetime(2026, 9, 15, 20, 0, 0)


def test_format_remaining_seconds_only():
    assert format_remaining(45) == "45 秒"


def test_format_remaining_minutes_and_seconds():
    assert format_remaining(125) == "2 分 5 秒"


def test_format_remaining_hours():
    assert format_remaining(2 * 3600 + 13 * 60) == "2 小时 13 分"


def test_format_remaining_days():
    assert format_remaining(2 * 86400 + 3 * 3600) == "2 天 3 小时"


def test_format_remaining_zero():
    assert format_remaining(0) == "0 秒"


def test_format_remaining_negative_clamps_to_zero():
    assert format_remaining(-5) == "0 秒"


def test_format_trigger_time_today():
    assert format_trigger_time(datetime(2026, 9, 15, 23, 30), NOW) == "今天 23:30"


def test_format_trigger_time_tomorrow():
    assert format_trigger_time(datetime(2026, 9, 16, 2, 0), NOW) == "明天 02:00"


def test_format_trigger_time_further_out_shows_date():
    assert format_trigger_time(datetime(2026, 9, 20, 23, 30), NOW) == "09-20 23:30"
