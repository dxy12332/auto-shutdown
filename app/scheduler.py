"""定时调度：计算下次触发时刻，并驱动 QTimer。

计算部分是纯函数，与 Qt 无关，便于完整单测。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QTimer, Signal

from app.config import Config

logger = logging.getLogger(__name__)

#: 单次 QTimer 的最大等待毫秒数。Qt 的定时器是 32 位毫秒，
#: 超过约 24 天会溢出，所以长等待要分段。
_MAX_INTERVAL_MS = 6 * 60 * 60 * 1000  # 6 小时


@dataclass(frozen=True)
class Trigger:
    kind: str  # "oneoff" | "daily"
    at: datetime


def next_daily_occurrence(time_str: str, now: datetime) -> datetime:
    """给定 HH:MM，返回今天该时刻；若已过（含正好相等）则返回明天。"""
    hour, minute = (int(part) for part in time_str.split(":"))
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def next_oneoff_occurrence(target_iso: str, now: datetime) -> datetime | None:
    """解析 ISO 时刻；为空、非法或已过去都返回 None。"""
    if not target_iso:
        return None
    try:
        target = datetime.fromisoformat(target_iso)
    except ValueError:
        return None
    return target if target > now else None


def compute_next_trigger(cfg: Config, now: datetime) -> Trigger | None:
    """在启用的一次性/每日定时中，取最近的一个。"""
    candidates: list[Trigger] = []

    if cfg.oneoff.enabled:
        oneoff_at = next_oneoff_occurrence(cfg.oneoff.target, now)
        if oneoff_at is not None:
            candidates.append(Trigger("oneoff", oneoff_at))

    if cfg.daily.enabled:
        candidates.append(Trigger("daily", next_daily_occurrence(cfg.daily.time, now)))

    if not candidates:
        return None
    return min(candidates, key=lambda item: item.at)


class Scheduler(QObject):
    """按配置驱动触发。到点时发出 triggered 信号，由上层决定做什么。"""

    triggered = Signal(object)

    def __init__(self, cfg_provider, parent: QObject | None = None):
        super().__init__(parent)
        self._cfg_provider = cfg_provider
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._pending: Trigger | None = None

    def next_trigger(self, now: datetime | None = None) -> Trigger | None:
        return compute_next_trigger(self._cfg_provider(), now or datetime.now())

    def refresh(self) -> None:
        """配置变化后重新计算下次触发。"""
        self._timer.stop()
        now = datetime.now()
        trigger = self.next_trigger(now)
        self._pending = trigger
        if trigger is None:
            logger.info("当前无排定的定时")
            return

        delay_ms = int((trigger.at - now).total_seconds() * 1000)
        delay_ms = max(0, min(delay_ms, _MAX_INTERVAL_MS))
        self._timer.start(delay_ms)
        logger.info("下次触发: %s %s（%s 毫秒后）", trigger.kind, trigger.at, delay_ms)

    def stop(self) -> None:
        self._timer.stop()
        self._pending = None

    def _on_timeout(self) -> None:
        trigger = self._pending
        if trigger is None:
            return

        remaining_ms = int((trigger.at - datetime.now()).total_seconds() * 1000)
        if remaining_ms > 1000:
            # 分段等待尚未走完（长时间定时的中间一跳），继续等
            self._timer.start(min(remaining_ms, _MAX_INTERVAL_MS))
            return

        self._pending = None
        logger.info("触发: %s @ %s", trigger.kind, trigger.at)
        self.triggered.emit(trigger)
