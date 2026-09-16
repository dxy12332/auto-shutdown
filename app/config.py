"""配置读写：JSON 序列化、默认值填充、非法值回退、原子写入。

本模块只保证「读出来的一定是合法配置」，不关心任何业务语义。
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

CONFIG_VERSION = 1
VALID_ACTIONS = ("shutdown", "restart", "sleep", "hibernate", "logoff")
VALID_THEMES = ("dark", "light")
GRACE_MIN = 10
GRACE_MAX = 300
DEFAULT_GRACE = 60
DEFAULT_DAILY_TIME = "23:30"


@dataclass
class Daily:
    enabled: bool = False
    time: str = DEFAULT_DAILY_TIME


@dataclass
class OneOff:
    enabled: bool = False
    target: str = ""
    label: str = ""


@dataclass
class Config:
    version: int = CONFIG_VERSION
    action: str = "shutdown"
    force: bool = False
    grace_seconds: int = DEFAULT_GRACE
    autostart: bool = True
    theme: str = "dark"
    dry_run: bool = False
    daily: Daily = field(default_factory=Daily)
    oneoff: OneOff = field(default_factory=OneOff)


def _as_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _as_choice(value: Any, choices: tuple[str, ...], default: str) -> str:
    return value if isinstance(value, str) and value in choices else default


def _as_int(value: Any, low: int, high: int, default: int) -> int:
    # bool 是 int 的子类，必须先排除，否则 True 会被当成 1
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(low, min(high, value))


def _as_time(value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    parts = value.split(":")
    if len(parts) != 2:
        return default
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return default
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return default
    return f"{hour:02d}:{minute:02d}"


def _as_str(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def normalize(raw: Any) -> Config:
    """把任意来源的数据规整成合法配置，非法字段一律回退到默认值。"""
    if not isinstance(raw, dict):
        return Config()

    daily_raw = raw.get("daily")
    daily_raw = daily_raw if isinstance(daily_raw, dict) else {}
    oneoff_raw = raw.get("oneoff")
    oneoff_raw = oneoff_raw if isinstance(oneoff_raw, dict) else {}

    return Config(
        version=CONFIG_VERSION,
        action=_as_choice(raw.get("action"), VALID_ACTIONS, "shutdown"),
        force=_as_bool(raw.get("force"), False),
        grace_seconds=_as_int(raw.get("grace_seconds"), GRACE_MIN, GRACE_MAX, DEFAULT_GRACE),
        autostart=_as_bool(raw.get("autostart"), True),
        theme=_as_choice(raw.get("theme"), VALID_THEMES, "dark"),
        dry_run=_as_bool(raw.get("dry_run"), False),
        daily=Daily(
            enabled=_as_bool(daily_raw.get("enabled"), False),
            time=_as_time(daily_raw.get("time"), DEFAULT_DAILY_TIME),
        ),
        oneoff=OneOff(
            enabled=_as_bool(oneoff_raw.get("enabled"), False),
            target=_as_str(oneoff_raw.get("target")),
            label=_as_str(oneoff_raw.get("label")),
        ),
    )


def clear_all_schedules(cfg: Config) -> Config:
    """清空所有排定的定时：一次性与每天重复都要清。

    「取消关机」的语义是把界面上显示的那条排定撤掉。只清其中一半，
    按钮看起来就会毫无反应——因为另一半规则仍然在生效。
    """
    cfg.oneoff.enabled = False
    cfg.oneoff.target = ""
    cfg.oneoff.label = ""
    cfg.daily.enabled = False
    return cfg


class ConfigStore:
    """配置文件读写。写入采用「临时文件 + 替换」，中途断电也不会损坏原配置。"""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def load(self) -> Config:
        if not self.path.exists():
            return Config()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            self._backup_corrupt()
            return Config()
        return normalize(raw)

    def save(self, cfg: Config) -> None:
        payload = asdict(cfg)
        payload["version"] = CONFIG_VERSION
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.parent / (self.path.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def _backup_corrupt(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            os.replace(self.path, self.path.with_name(f"{self.path.name}.corrupt-{stamp}"))
        except OSError:
            pass
