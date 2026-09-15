"""展示层的时间格式化。纯函数，便于单测。"""
from __future__ import annotations

from datetime import datetime


def format_remaining(seconds: int) -> str:
    """把剩余秒数表述成人类可读的粗略时长。"""
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    if days:
        return f"{days} 天 {hours} 小时"
    if hours:
        return f"{hours} 小时 {minutes} 分"
    if minutes:
        return f"{minutes} 分 {secs} 秒"
    return f"{secs} 秒"


def format_trigger_time(at: datetime, now: datetime) -> str:
    """把绝对时刻表述成「今天 23:30」「明天 02:00」或「09-20 23:30」。"""
    day_delta = (at.date() - now.date()).days
    hhmm = at.strftime("%H:%M")

    if day_delta == 0:
        return f"今天 {hhmm}"
    if day_delta == 1:
        return f"明天 {hhmm}"
    return at.strftime("%m-%d ") + hhmm
