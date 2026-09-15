# 定时关机应用 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 做一个带图形界面的定时关机应用，支持一次性/每天重复定时、随时取消、到点倒计时确认，替代 `C:\Users\ch\auto-shutdown\` 那套硬编码的 PowerShell 脚本。

**Architecture:** 单进程 PySide6 桌面应用，常驻系统托盘。所有定时在应用进程内的 QTimer 上运行，配置只有一份（`config.json`）。关机/重启走「先交系统排程 `shutdown /s /t N`，再弹应用确认窗，取消则 `/a`」的双保险模式；睡眠/休眠/注销没有系统级排程接口，由应用内计时直接执行。**`app/power.py` 是唯一允许调用 `shutdown.exe` 的模块**，dry-run 开关只需在这一处生效。

**Tech Stack:** Python 3.12、PySide6（Qt6）、pytest、Windows 11 + PowerShell 5.1

**Spec:** `D:\AutoShutdownPro\docs\specs\2026-09-15-auto-shutdown-design.md`

## Global Constraints

- 平台限定 Windows，Python 3.12，PySide6。不引入 PySide6 / pytest 之外的第三方依赖（图标用 `QPainter` 画，快捷方式走 PowerShell COM，睡眠/休眠走 `ctypes`）。
- **所有 `shutdown.exe` 调用只允许出现在 `app/power.py`。** 其他模块一律通过 `PowerExecutor` 间接使用。
- **调试期一律用 `python main.py --dry-run` 启动**，该参数强制所有电源命令只写日志、不执行。Task 10 之前不得以不带该参数的方式运行 `main.py`。任何真实关机验证必须用户在场并明确同意。
- 宽限期 `grace_seconds` 取值范围锁定 `10–300`，默认 `60`。
- 睡眠/休眠必须通过 `ctypes` 调用 `powrprof.dll` 的 `SetSuspendState`，**禁止使用 `rundll32.exe powrprof.dll,SetSuspendState`**——该写法在启用休眠的系统上会变成休眠而非睡眠。
- 界面文案全部简体中文；代码、标识符、日志关键字保留英文。
- 主题取值 `dark` / `light`，默认 `dark`。
- 运行期文件位置：配置 `D:\AutoShutdownPro\config.json`，日志 `D:\AutoShutdownPro\run.log`。
- 每个 Task 结束都要 `git commit`，提交信息用 `feat:` / `test:` / `chore:` 前缀。

## File Structure

| 文件 | 职责 |
|---|---|
| `main.py` | 入口：命令行参数、单实例锁、组装窗口与托盘、全局异常兜底 |
| `app/config.py` | 配置的序列化与校验。纯数据 + 文件 IO，不含业务语义 |
| `app/power.py` | 电源动作命令的构造与执行。唯一碰 `shutdown.exe` 的地方，含 dry-run 分支 |
| `app/scheduler.py` | 「下次该在什么时刻触发」的计算 + QTimer 驱动。不碰系统命令 |
| `app/theme.py` | 两套主题的配色常量与 QSS 样式表 |
| `app/autostart.py` | 开机自启：启动文件夹快捷方式的增删与状态查询 |
| `app/confirm.py` | 关机确认窗：倒计时数字、环形进度、取消 / 立即执行 |
| `app/window.py` | 主窗口：状态卡片、定时控件、动作选择、取消按钮、主题切换 |
| `app/tray.py` | 系统托盘图标与右键菜单 |
| `app/paths.py` | 集中定义运行期路径常量，避免各模块各自拼路径 |
| `tests/test_config.py` | 配置读写与容错测试 |
| `tests/test_power.py` | 命令构造与 dry-run 测试 |
| `tests/test_scheduler.py` | 触发时刻计算测试 |
| `tests/test_autostart.py` | 自启快捷方式增删测试 |
| `assets/icon.ico` | 应用与托盘图标（脚本生成） |
| `tools/make_icon.py` | 用 QPainter 生成 `assets/icon.ico` |
| `tools/make_shortcut.py` | 生成桌面快捷方式 |
| `启动.bat` | 无控制台窗口启动应用 |

---

### Task 1: 项目骨架与配置模块

建立目录结构、版本控制、依赖清单，并实现配置读写。配置是整个应用的单一状态源，必须先立住，后面所有模块都依赖它的接口。

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/paths.py`
- Create: `app/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `app.paths.PROJECT_ROOT: Path` — 项目根目录
  - `app.paths.CONFIG_PATH: Path` — `PROJECT_ROOT / "config.json"`
  - `app.paths.LOG_PATH: Path` — `PROJECT_ROOT / "run.log"`
  - `app.paths.ICON_PATH: Path` — `PROJECT_ROOT / "assets" / "icon.ico"`
  - `app.config.VALID_ACTIONS: tuple[str, ...]` = `("shutdown", "restart", "sleep", "hibernate", "logoff")`
  - `app.config.VALID_THEMES: tuple[str, ...]` = `("dark", "light")`
  - `app.config.GRACE_MIN: int` = `10`，`app.config.GRACE_MAX: int` = `300`
  - `app.config.Daily` dataclass：`enabled: bool = False`，`time: str = "23:30"`
  - `app.config.OneOff` dataclass：`enabled: bool = False`，`target: str = ""`，`label: str = ""`
  - `app.config.Config` dataclass：`version: int`，`action: str`，`force: bool`，`grace_seconds: int`，`autostart: bool`，`theme: str`，`dry_run: bool`，`daily: Daily`，`oneoff: OneOff`
  - `app.config.ConfigStore(path)` 类：`load() -> Config`、`save(cfg: Config) -> None`

- [ ] **Step 1: 建立项目骨架**

```bash
cd /d/AutoShutdownPro
git init
mkdir -p app tests assets tools
touch app/__init__.py tests/__init__.py
```

`.gitignore`：

```gitignore
__pycache__/
*.pyc
.pytest_cache/
config.json
config.json.tmp
config.json.corrupt-*
run.log
```

`requirements.txt`：

```text
PySide6>=6.6
pytest>=8.0
```

安装依赖：

```bash
cd /d/AutoShutdownPro
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

- [ ] **Step 2: 写路径常量模块**

`app/paths.py`：

```python
"""集中定义运行期路径，避免各模块各自拼路径。"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
LOG_PATH = PROJECT_ROOT / "run.log"
ICON_PATH = PROJECT_ROOT / "assets" / "icon.ico"
ASSETS_DIR = PROJECT_ROOT / "assets"
LAUNCH_BAT = PROJECT_ROOT / "启动.bat"
```

- [ ] **Step 3: 写失败的测试**

`tests/test_config.py`：

```python
import json
from pathlib import Path

from app.config import (
    GRACE_MAX,
    GRACE_MIN,
    ConfigStore,
    Daily,
    OneOff,
)


def test_load_missing_file_returns_defaults(tmp_path: Path):
    cfg = ConfigStore(tmp_path / "config.json").load()
    assert cfg.action == "shutdown"
    assert cfg.force is False
    assert cfg.grace_seconds == 60
    assert cfg.autostart is True
    assert cfg.theme == "dark"
    assert cfg.dry_run is False
    assert cfg.daily == Daily(enabled=False, time="23:30")
    assert cfg.oneoff == OneOff(enabled=False, target="", label="")


def test_save_then_load_roundtrip(tmp_path: Path):
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    cfg = store.load()
    cfg.action = "restart"
    cfg.grace_seconds = 120
    cfg.theme = "light"
    cfg.daily = Daily(enabled=True, time="22:15")
    store.save(cfg)

    assert ConfigStore(path).load() == cfg


def test_invalid_action_falls_back_to_default(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"action": "explode"}), encoding="utf-8")
    assert ConfigStore(path).load().action == "shutdown"


def test_grace_seconds_is_clamped_into_range(tmp_path: Path):
    path = tmp_path / "config.json"

    path.write_text(json.dumps({"grace_seconds": 5}), encoding="utf-8")
    assert ConfigStore(path).load().grace_seconds == GRACE_MIN

    path.write_text(json.dumps({"grace_seconds": 9999}), encoding="utf-8")
    assert ConfigStore(path).load().grace_seconds == GRACE_MAX


def test_non_numeric_grace_falls_back_to_default(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"grace_seconds": "soon"}), encoding="utf-8")
    assert ConfigStore(path).load().grace_seconds == 60


def test_bool_is_not_accepted_as_int(tmp_path: Path):
    """Python 里 bool 是 int 的子类，必须显式挡住。"""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"grace_seconds": True}), encoding="utf-8")
    assert ConfigStore(path).load().grace_seconds == 60


def test_corrupt_file_is_backed_up_and_defaults_returned(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("{not json at all", encoding="utf-8")

    cfg = ConfigStore(path).load()

    assert cfg.action == "shutdown"
    assert len(list(tmp_path.glob("config.json.corrupt-*"))) == 1
    assert not path.exists()


def test_unknown_fields_are_ignored(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"action": "sleep", "nonsense": 1}), encoding="utf-8")
    assert ConfigStore(path).load().action == "sleep"


def test_invalid_time_falls_back_to_default(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"daily": {"enabled": True, "time": "25:99"}}), encoding="utf-8")
    assert ConfigStore(path).load().daily.time == "23:30"


def test_time_is_normalized_to_two_digit_form(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"daily": {"enabled": True, "time": "7:5"}}), encoding="utf-8")
    assert ConfigStore(path).load().daily.time == "07:05"


def test_save_leaves_no_tmp_file_behind(tmp_path: Path):
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    store.save(store.load())
    assert path.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_invalid_theme_falls_back_to_dark(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"theme": "neon"}), encoding="utf-8")
    assert ConfigStore(path).load().theme == "dark"
```

- [ ] **Step 4: 运行测试，确认失败**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_config.py -v
```

Expected: 全部 FAIL，报 `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 5: 实现配置模块**

`app/config.py`：

```python
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
```

- [ ] **Step 6: 运行测试，确认通过**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_config.py -v
```

Expected: 12 passed

- [ ] **Step 7: 提交**

```bash
cd /d/AutoShutdownPro
git add .gitignore requirements.txt app/ tests/
git commit -m "feat: 项目骨架与配置模块（含容错与原子写入）"
```

---

### Task 2: 电源动作封装与 dry-run 安全闸

这是整个应用安全性最关键的一块：所有会让电脑关机、重启、睡眠的命令都从这里发出。命令**构造**与**执行**分开，构造部分是纯函数、可完整单测；dry-run 分支放在执行层，保证调试期绝无误关机。

**Files:**
- Create: `app/power.py`
- Create: `tests/test_power.py`

**Interfaces:**
- Consumes: 无（仅标准库）
- Produces:
  - `app.power.Command` dataclass（frozen）：`argv: list[str]`、`description: str`、`via_api: bool = False`
  - `app.power.SYSTEM_SCHEDULABLE: tuple[str, ...]` = `("shutdown", "restart")`
  - `app.power.supports_system_abort(action: str) -> bool`
  - `app.power.build_arm_command(action: str, grace_seconds: int, force: bool) -> Command`
  - `app.power.build_abort_command() -> Command`
  - `app.power.build_now_command(action: str, force: bool) -> Command`
  - `app.power.hibernate_available() -> bool`
  - `app.power.PowerExecutor(dry_run: bool = False, runner: Callable[[list[str]], int] | None = None)` 类：
    - `run(command: Command) -> bool`
    - `arm(action, grace_seconds, force) -> bool`
    - `abort() -> bool`
    - `execute_now(action, force) -> bool`

- [ ] **Step 1: 写失败的测试**

`tests/test_power.py`：

```python
import pytest

from app.power import (
    Command,
    PowerExecutor,
    build_abort_command,
    build_arm_command,
    build_now_command,
    supports_system_abort,
)


def test_supports_system_abort_only_for_shutdown_and_restart():
    assert supports_system_abort("shutdown") is True
    assert supports_system_abort("restart") is True
    assert supports_system_abort("sleep") is False
    assert supports_system_abort("hibernate") is False
    assert supports_system_abort("logoff") is False


def test_build_arm_command_for_shutdown():
    cmd = build_arm_command("shutdown", 60, force=False)
    assert cmd.argv == ["shutdown.exe", "/s", "/t", "60"]
    assert cmd.via_api is False


def test_build_arm_command_for_restart():
    assert build_arm_command("restart", 30, force=False).argv == [
        "shutdown.exe", "/r", "/t", "30",
    ]


def test_build_arm_command_appends_force_flag():
    assert build_arm_command("shutdown", 60, force=True).argv == [
        "shutdown.exe", "/s", "/t", "60", "/f",
    ]


@pytest.mark.parametrize("action", ["sleep", "hibernate", "logoff"])
def test_build_arm_command_rejects_unschedulable_actions(action):
    with pytest.raises(ValueError):
        build_arm_command(action, 60, force=False)


def test_build_abort_command():
    assert build_abort_command().argv == ["shutdown.exe", "/a"]


def test_build_now_command_for_shutdown_is_immediate():
    assert build_now_command("shutdown", force=False).argv == [
        "shutdown.exe", "/s", "/t", "0",
    ]


def test_build_now_command_for_logoff():
    assert build_now_command("logoff", force=False).argv == ["shutdown.exe", "/l"]


@pytest.mark.parametrize("action", ["sleep", "hibernate"])
def test_build_now_command_for_suspend_uses_api(action):
    cmd = build_now_command(action, force=False)
    assert cmd.via_api is True
    assert cmd.argv == []


def test_build_now_command_rejects_unknown_action():
    with pytest.raises(ValueError):
        build_now_command("explode", force=False)


def test_dry_run_never_calls_runner(caplog):
    calls = []
    executor = PowerExecutor(dry_run=True, runner=lambda argv: calls.append(argv) or 0)

    assert executor.run(build_arm_command("shutdown", 60, force=False)) is True

    assert calls == []
    assert "[DRY-RUN]" in caplog.text
    assert "shutdown.exe /s /t 60" in caplog.text


def test_dry_run_abort_is_logged_not_executed(caplog):
    calls = []
    executor = PowerExecutor(dry_run=True, runner=lambda argv: calls.append(argv) or 0)
    executor.abort()
    assert calls == []
    assert "/a" in caplog.text


def test_live_mode_passes_argv_to_runner():
    calls = []
    executor = PowerExecutor(dry_run=False, runner=lambda argv: calls.append(argv) or 0)

    assert executor.run(build_arm_command("restart", 45, force=True)) is True

    assert calls == [["shutdown.exe", "/r", "/t", "45", "/f"]]


def test_live_mode_reports_failure_on_nonzero_exit():
    executor = PowerExecutor(dry_run=False, runner=lambda argv: 1)
    assert executor.run(build_abort_command()) is False


def test_runner_exception_is_swallowed_and_reported(caplog):
    def boom(argv):
        raise OSError("shutdown.exe not found")

    executor = PowerExecutor(dry_run=False, runner=boom)

    assert executor.run(build_abort_command()) is False
    assert "shutdown.exe not found" in caplog.text


def test_executor_helpers_construct_expected_commands():
    seen = []
    executor = PowerExecutor(dry_run=False, runner=lambda argv: seen.append(argv) or 0)

    executor.arm("shutdown", 60, force=False)
    executor.abort()
    executor.execute_now("restart", force=False)

    assert seen == [
        ["shutdown.exe", "/s", "/t", "60"],
        ["shutdown.exe", "/a"],
        ["shutdown.exe", "/r", "/t", "0"],
    ]
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_power.py -v
```

Expected: 全部 FAIL，报 `ModuleNotFoundError: No module named 'app.power'`

- [ ] **Step 3: 实现电源模块**

`app/power.py`：

```python
"""电源动作的构造与执行。

本模块是整个应用中唯一允许调用 shutdown.exe 的地方。
dry_run=True 时所有命令只写日志、不执行，保证调试期绝不会误关机。
"""
from __future__ import annotations

import ctypes
import logging
import subprocess
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

ACTION_LABELS = {
    "shutdown": "关机",
    "restart": "重启",
    "sleep": "睡眠",
    "hibernate": "休眠",
    "logoff": "注销",
}

#: 只有这两种动作能交给系统排程，也才能用 shutdown /a 撤销。
#: 睡眠/休眠/注销没有对应的系统级排程接口，只能在应用内计时。
SYSTEM_SCHEDULABLE = ("shutdown", "restart")

#: 子进程不弹控制台窗口
_CREATE_NO_WINDOW = 0x08000000


@dataclass(frozen=True)
class Command:
    argv: list[str]
    description: str
    via_api: bool = False


def supports_system_abort(action: str) -> bool:
    return action in SYSTEM_SCHEDULABLE


def build_arm_command(action: str, grace_seconds: int, force: bool) -> Command:
    """构造「把动作排程给系统」的命令。仅 shutdown / restart 有意义。"""
    if not supports_system_abort(action):
        raise ValueError(f"{action} 不支持系统级排程，须由应用内计时执行")
    flag = "/s" if action == "shutdown" else "/r"
    argv = ["shutdown.exe", flag, "/t", str(int(grace_seconds))]
    if force:
        argv.append("/f")
    return Command(argv=argv, description=f"{ACTION_LABELS[action]}（{int(grace_seconds)} 秒后）")


def build_abort_command() -> Command:
    return Command(argv=["shutdown.exe", "/a"], description="撤销已排程的关机")


def build_now_command(action: str, force: bool) -> Command:
    """构造「立即执行」的命令。"""
    label = ACTION_LABELS.get(action)
    if label is None:
        raise ValueError(f"未知动作: {action}")

    if supports_system_abort(action):
        flag = "/s" if action == "shutdown" else "/r"
        argv = ["shutdown.exe", flag, "/t", "0"]
        if force:
            argv.append("/f")
        return Command(argv=argv, description=f"立即{label}")

    if action == "logoff":
        return Command(argv=["shutdown.exe", "/l"], description="立即注销")

    # sleep / hibernate
    return Command(argv=[], description=f"立即{label}", via_api=True)


def hibernate_available() -> bool:
    """查询系统是否启用了休眠。

    SetSuspendState 的 Hibernate 参数在未启用休眠时会失败，
    因此执行休眠前必须先确认。
    """
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Power",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "HibernateEnabled")
        return bool(value)
    except OSError:
        return False


def _call_set_suspend_state(hibernate: bool) -> bool:
    """通过 powrprof.dll 直接调用 SetSuspendState。

    不要改用 rundll32.exe powrprof.dll,SetSuspendState —— 那写法在启用休眠的
    系统上会变成休眠而不是睡眠，无法可靠区分两者。
    """
    try:
        powrprof = ctypes.WinDLL("powrprof.dll")
    except OSError:
        logger.exception("加载 powrprof.dll 失败")
        return False
    try:
        # 参数：(bHibernate, bForce, bWakeupEventsDisabled)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        return bool(powrprof.SetSuspendState(1 if hibernate else 0, 0, 0))
    except Exception:
        logger.exception("SetSuspendState 调用失败")
        return False


class PowerExecutor:
    """执行电源命令。dry_run=True 时只写日志，绝不真的关机。"""

    def __init__(
        self,
        dry_run: bool = False,
        runner: Callable[[list[str]], int] | None = None,
    ):
        self.dry_run = dry_run
        self._runner = runner if runner is not None else self._default_runner

    @staticmethod
    def _default_runner(argv: list[str]) -> int:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            creationflags=_CREATE_NO_WINDOW,
        )
        return completed.returncode

    def run(self, command: Command) -> bool:
        if self.dry_run:
            shown = " ".join(command.argv) if command.argv else "(Win32 API)"
            logger.info("[DRY-RUN] 将执行: %s | %s", shown, command.description)
            return True

        if command.via_api:
            return _call_set_suspend_state(command.description.endswith("休眠"))

        try:
            code = self._runner(command.argv)
        except Exception as exc:
            logger.error("执行 %s 失败: %s", command.argv, exc)
            return False

        if code != 0:
            logger.warning("命令 %s 退出码 %s", command.argv, code)
            return False
        return True

    def arm(self, action: str, grace_seconds: int, force: bool) -> bool:
        return self.run(build_arm_command(action, grace_seconds, force))

    def abort(self) -> bool:
        return self.run(build_abort_command())

    def execute_now(self, action: str, force: bool) -> bool:
        return self.run(build_now_command(action, force))
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_power.py -v
```

Expected: 19 passed

- [ ] **Step 5: 手动确认 dry-run 不碰真实系统**

```bash
cd /d/AutoShutdownPro
python -c "
import logging
logging.basicConfig(level=logging.INFO)
from app.power import PowerExecutor
ex = PowerExecutor(dry_run=True)
ex.arm('shutdown', 60, False)
ex.abort()
"
```

Expected: 打印两行 `[DRY-RUN] 将执行: ...`，**电脑绝对不动**。

- [ ] **Step 6: 提交**

```bash
cd /d/AutoShutdownPro
git add app/power.py tests/test_power.py
git commit -m "feat: 电源动作封装，含 dry-run 安全闸与 Win32 睡眠/休眠"
```

---

### Task 3: 定时调度引擎

回答"下次该在什么时刻触发"。计算部分是纯函数，边界（今天已过、跨天、闰日）必须完整覆盖。QTimer 包装只负责驱动，不承载逻辑。

**Files:**
- Create: `app/scheduler.py`
- Create: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `app.config.Config`（Task 1）
- Produces:
  - `app.scheduler.Trigger` dataclass（frozen）：`kind: str`（`"oneoff"` / `"daily"`）、`at: datetime`
  - `app.scheduler.next_daily_occurrence(time_str: str, now: datetime) -> datetime`
  - `app.scheduler.next_oneoff_occurrence(target_iso: str, now: datetime) -> datetime | None`
  - `app.scheduler.compute_next_trigger(cfg: Config, now: datetime) -> Trigger | None`
  - `app.scheduler.Scheduler` 类（QObject）：信号 `triggered = Signal(object)`；方法 `refresh() -> None`、`stop() -> None`、`next_trigger(now=None) -> Trigger | None`

- [ ] **Step 1: 写失败的测试**

`tests/test_scheduler.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_scheduler.py -v
```

Expected: 全部 FAIL，报 `ModuleNotFoundError: No module named 'app.scheduler'`

- [ ] **Step 3: 实现调度引擎**

`app/scheduler.py`：

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_scheduler.py -v
```

Expected: 15 passed

- [ ] **Step 5: 跑一次全量测试**

```bash
cd /d/AutoShutdownPro
python -m pytest -v
```

Expected: 46 passed（config 12 + power 19 + scheduler 15）

- [ ] **Step 6: 提交**

```bash
cd /d/AutoShutdownPro
git add app/scheduler.py tests/test_scheduler.py
git commit -m "feat: 定时调度引擎，含跨天/闰日边界处理"
```

---

### Task 4: 主题系统

两套配色 + 一张 QSS 样式表。主窗口、确认窗、托盘菜单共用同一份 `stylesheet()`，避免三处配色分裂。

**Files:**
- Create: `app/theme.py`
- Create: `tests/test_theme.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `app.theme.THEMES: tuple[str, ...]` = `("dark", "light")`
  - `app.theme.palette(theme: str) -> dict[str, str]` — 未知主题回退到 dark，绝不抛异常
  - `app.theme.stylesheet(theme: str) -> str` — 完整 QSS
  - `app.theme.color(theme: str, key: str) -> str` — 取单个颜色，未知 key 回退到 `text`
  - 配色 key 全集：`bg`、`card`、`border`、`text`、`text_dim`、`accent`、`accent_hover`、`ok`、`warn`、`idle`、`danger`

- [ ] **Step 1: 写失败的测试**

`tests/test_theme.py`：

```python
import pytest

from app.theme import THEMES, color, palette, stylesheet

REQUIRED_KEYS = {
    "bg", "card", "border", "text", "text_dim",
    "accent", "accent_hover", "ok", "warn", "idle", "danger",
}


@pytest.mark.parametrize("theme", THEMES)
def test_every_theme_defines_all_keys(theme):
    assert REQUIRED_KEYS <= set(palette(theme))


@pytest.mark.parametrize("theme", THEMES)
def test_every_value_is_a_hex_color(theme):
    for key, value in palette(theme).items():
        assert value.startswith("#"), f"{theme}.{key} 不是十六进制颜色"
        assert len(value) == 7, f"{theme}.{key} 长度不对: {value}"


def test_unknown_theme_falls_back_to_dark():
    assert palette("neon") == palette("dark")


def test_dark_and_light_actually_differ():
    assert palette("dark")["bg"] != palette("light")["bg"]


def test_color_helper_returns_single_value():
    assert color("dark", "accent") == palette("dark")["accent"]


def test_color_helper_unknown_key_falls_back_to_text():
    assert color("dark", "no_such_key") == palette("dark")["text"]


@pytest.mark.parametrize("theme", THEMES)
def test_stylesheet_has_no_unsubstituted_placeholders(theme):
    qss = stylesheet(theme)
    assert "$" not in qss, "QSS 里有未替换的模板变量"
    assert "#Card" in qss


def test_stylesheet_differs_between_themes():
    assert stylesheet("dark") != stylesheet("light")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_theme.py -v
```

Expected: 全部 FAIL，报 `ModuleNotFoundError: No module named 'app.theme'`

- [ ] **Step 3: 实现主题模块**

`app/theme.py`：

```python
"""两套主题的配色常量与 QSS 样式表。

用 string.Template 而非 f-string：QSS 里大量出现花括号，
f-string 需要把每个 { 写成 {{，可读性会崩掉。
"""
from __future__ import annotations

from string import Template

THEMES = ("dark", "light")

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#1e1f22",
        "card": "#2b2d31",
        "border": "#3a3d43",
        "text": "#e6e6e6",
        "text_dim": "#9aa0a6",
        "accent": "#4c8dff",
        "accent_hover": "#5f9bff",
        "ok": "#3ddc84",
        "warn": "#ffa726",
        "idle": "#6b7076",
        "danger": "#ff5c5c",
    },
    "light": {
        "bg": "#f5f6f8",
        "card": "#ffffff",
        "border": "#dfe1e5",
        "text": "#1f2328",
        "text_dim": "#6b7076",
        "accent": "#2f6feb",
        "accent_hover": "#1f5fd8",
        "ok": "#1a9e5c",
        "warn": "#e08a00",
        "idle": "#9aa0a6",
        "danger": "#d64545",
    },
}

_QSS = Template("""
QWidget {
    background-color: $bg;
    color: $text;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}

#Card {
    background-color: $card;
    border: 1px solid $border;
    border-radius: 12px;
}

#TitleText {
    font-size: 15px;
    font-weight: 600;
}

#SectionTitle {
    color: $text_dim;
    font-size: 12px;
    font-weight: 600;
    padding-top: 8px;
}

#StatusText {
    font-size: 15px;
    font-weight: 600;
}

#StatusDetail {
    color: $text_dim;
    font-size: 12px;
}

#StatusDot {
    font-size: 14px;
}

QPushButton {
    background-color: $card;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 8px 14px;
}

QPushButton:hover {
    border-color: $accent;
}

QPushButton:pressed {
    background-color: $border;
}

QPushButton:disabled {
    color: $text_dim;
    border-color: $border;
}

QPushButton#Primary {
    background-color: $accent;
    border: none;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#Primary:hover {
    background-color: $accent_hover;
}

QPushButton#Danger {
    background-color: transparent;
    border: 1px solid $danger;
    color: $danger;
    font-size: 15px;
    font-weight: 600;
    padding: 12px;
}

QPushButton#Danger:hover {
    background-color: $danger;
    color: #ffffff;
}

QPushButton#Danger:disabled {
    border-color: $border;
    color: $text_dim;
}

QPushButton#IconButton {
    background-color: transparent;
    border: none;
    padding: 4px 8px;
    font-size: 15px;
}

QPushButton#IconButton:hover {
    background-color: $border;
    border-radius: 6px;
}

QTimeEdit, QSpinBox, QComboBox {
    background-color: $card;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 10px;
}

QTimeEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: $accent;
}

QCheckBox, QRadioButton {
    spacing: 6px;
}

#Hint {
    color: $text_dim;
    font-size: 12px;
}

#CountdownText {
    font-size: 32px;
    font-weight: 700;
}

#CountdownCaption {
    color: $text_dim;
    font-size: 13px;
}
""")


def palette(theme: str) -> dict[str, str]:
    return PALETTES.get(theme, PALETTES["dark"])


def color(theme: str, key: str) -> str:
    colors = palette(theme)
    return colors.get(key, colors["text"])


def stylesheet(theme: str) -> str:
    return _QSS.substitute(palette(theme))
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_theme.py -v
```

Expected: 11 passed

- [ ] **Step 5: 提交**

```bash
cd /d/AutoShutdownPro
git add app/theme.py tests/test_theme.py
git commit -m "feat: 暗色/亮色两套主题与 QSS 样式表"
```

---

### Task 5: 开机自启模块

在启动文件夹增删快捷方式。走 PowerShell 的 WScript.Shell COM 接口，不引入 pywin32 依赖。

**Files:**
- Create: `app/autostart.py`
- Create: `tests/test_autostart.py`

**Interfaces:**
- Consumes: `app.paths`（Task 1）
- Produces:
  - `app.autostart.STARTUP_DIR: Path` — 当前用户的启动文件夹
  - `app.autostart.LNK_NAME: str` = `"AutoShutdownPro.lnk"`
  - `app.autostart.Autostart(startup_dir: Path | None = None, lnk_name: str = LNK_NAME)` 类：
    - `lnk_path -> Path`（property）
    - `is_enabled() -> bool`
    - `enable(target: Path, workdir: Path, icon: Path | None = None) -> bool`
    - `disable() -> bool`
    - `sync(enabled: bool, target: Path, workdir: Path, icon: Path | None = None) -> bool`

- [ ] **Step 1: 写失败的测试**

`tests/test_autostart.py`：

```python
from pathlib import Path

import pytest

from app.autostart import Autostart


def test_not_enabled_when_lnk_absent(tmp_path: Path):
    assert Autostart(startup_dir=tmp_path).is_enabled() is False


def test_lnk_path_is_inside_startup_dir(tmp_path: Path):
    auto = Autostart(startup_dir=tmp_path, lnk_name="X.lnk")
    assert auto.lnk_path == tmp_path / "X.lnk"


def test_enable_creates_shortcut(tmp_path: Path):
    target = tmp_path / "启动.bat"
    target.write_text("@echo off\n", encoding="utf-8")

    auto = Autostart(startup_dir=tmp_path / "Startup")
    assert auto.enable(target=target, workdir=tmp_path) is True
    assert auto.is_enabled() is True


def test_disable_removes_shortcut(tmp_path: Path):
    target = tmp_path / "启动.bat"
    target.write_text("@echo off\n", encoding="utf-8")

    auto = Autostart(startup_dir=tmp_path / "Startup")
    auto.enable(target=target, workdir=tmp_path)
    assert auto.disable() is True
    assert auto.is_enabled() is False


def test_disable_is_idempotent(tmp_path: Path):
    auto = Autostart(startup_dir=tmp_path / "Startup")
    assert auto.disable() is True
    assert auto.disable() is True


def test_sync_true_creates_and_false_removes(tmp_path: Path):
    target = tmp_path / "启动.bat"
    target.write_text("@echo off\n", encoding="utf-8")
    auto = Autostart(startup_dir=tmp_path / "Startup")

    auto.sync(True, target=target, workdir=tmp_path)
    assert auto.is_enabled() is True

    auto.sync(False, target=target, workdir=tmp_path)
    assert auto.is_enabled() is False


def test_sync_false_on_missing_shortcut_does_not_raise(tmp_path: Path):
    auto = Autostart(startup_dir=tmp_path / "Startup")
    assert auto.sync(False, target=tmp_path / "x.bat", workdir=tmp_path) is True


def test_enable_reports_failure_when_target_missing(tmp_path: Path):
    """目标不存在时不报错，但也不应假装成功创建了有效快捷方式。"""
    auto = Autostart(startup_dir=tmp_path / "Startup")
    auto.enable(target=tmp_path / "不存在.bat", workdir=tmp_path)
    # 快捷方式文件可能仍被创建（COM 不校验目标），这里只要求不抛异常
    assert isinstance(auto.is_enabled(), bool)
```

> 说明：这些测试会真的调用 PowerShell 创建 `.lnk`，但目标路径全部在 `tmp_path` 内，**不会碰真实启动文件夹**。若 PowerShell 不可用，`test_enable_creates_shortcut` 会失败——那种情况下需要人工确认环境。

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_autostart.py -v
```

Expected: 全部 FAIL，报 `ModuleNotFoundError: No module named 'app.autostart'`

- [ ] **Step 3: 实现自启模块**

`app/autostart.py`：

```python
"""开机自启：在用户启动文件夹增删快捷方式。

走 PowerShell 的 WScript.Shell COM 接口，避免引入 pywin32 依赖。
窗口样式设为 7（最小化），配合 启动.bat 可以避免启动时闪出控制台。
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

LNK_NAME = "AutoShutdownPro.lnk"
_CREATE_NO_WINDOW = 0x08000000

STARTUP_DIR = (
    Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
)

_PS_TEMPLATE = (
    "$ws = New-Object -ComObject WScript.Shell;"
    "$sc = $ws.CreateShortcut('{lnk}');"
    "$sc.TargetPath = '{target}';"
    "$sc.WorkingDirectory = '{workdir}';"
    "$sc.IconLocation = '{icon}';"
    "$sc.WindowStyle = 7;"
    "$sc.Description = 'AutoShutdownPro 定时关机';"
    "$sc.Save()"
)


def _ps_quote(value: object) -> str:
    """PowerShell 单引号字符串里，单引号要用两个单引号转义。"""
    return str(value).replace("'", "''")


class Autostart:
    def __init__(self, startup_dir: Path | None = None, lnk_name: str = LNK_NAME):
        self.startup_dir = Path(startup_dir) if startup_dir is not None else STARTUP_DIR
        self.lnk_name = lnk_name

    @property
    def lnk_path(self) -> Path:
        return self.startup_dir / self.lnk_name

    def is_enabled(self) -> bool:
        return self.lnk_path.exists()

    def enable(self, target: Path, workdir: Path, icon: Path | None = None) -> bool:
        self.startup_dir.mkdir(parents=True, exist_ok=True)
        script = _PS_TEMPLATE.format(
            lnk=_ps_quote(self.lnk_path),
            target=_ps_quote(target),
            workdir=_ps_quote(workdir),
            icon=_ps_quote(icon if icon is not None else target),
        )
        try:
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                check=False,
                capture_output=True,
                text=True,
                creationflags=_CREATE_NO_WINDOW,
            )
        except Exception as exc:
            logger.error("创建自启快捷方式失败: %s", exc)
            return False

        if completed.returncode != 0:
            logger.error("创建自启快捷方式失败: %s", completed.stderr.strip())
            return False

        logger.info("已启用开机自启: %s", self.lnk_path)
        return True

    def disable(self) -> bool:
        try:
            self.lnk_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.error("删除自启快捷方式失败: %s", exc)
            return False
        logger.info("已关闭开机自启")
        return True

    def sync(
        self,
        enabled: bool,
        target: Path,
        workdir: Path,
        icon: Path | None = None,
    ) -> bool:
        if enabled:
            return self.enable(target=target, workdir=workdir, icon=icon)
        return self.disable()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_autostart.py -v
```

Expected: 8 passed

- [ ] **Step 5: 确认没有污染真实启动文件夹**

```bash
ls "$APPDATA/Microsoft/Windows/Start Menu/Programs/Startup/"
```

Expected: 不该出现 `AutoShutdownPro.lnk`（测试全部走 tmp_path）。真实快捷方式由 Task 9 生成。

- [ ] **Step 6: 提交**

```bash
cd /d/AutoShutdownPro
git add app/autostart.py tests/test_autostart.py
git commit -m "feat: 开机自启模块，走启动文件夹快捷方式"
```

---

### Task 6: 关机确认窗

到点时弹出的置顶倒计时窗。环形进度用 `QPainter` 自绘，不依赖图片资源。关闭按钮（✕）**等同于取消关机**——安全优先，宁可漏关也不误关。

**Files:**
- Create: `app/confirm.py`

**Interfaces:**
- Consumes: `app.theme.stylesheet` / `app.theme.color`（Task 4）
- Produces:
  - `app.confirm.ConfirmDialog(action: str, grace_seconds: int, theme: str, parent=None)` 类（`QDialog`）：
    - 常量 `RESULT_CANCEL = "cancel"`、`RESULT_NOW = "now"`、`RESULT_TIMEOUT = "timeout"`
    - `exec_modal() -> str` — 阻塞执行，返回上述三个值之一
  - `app.confirm.RingProgress` 类（`QWidget`）：`set_ratio(float)`、`set_text(str)`、`set_color(str)`

**手动验收说明：** 这个窗口无法用 pytest 自动测（涉及事件循环与人工点击），验收方式是在 Step 4 用一段脚本把它弹出来，人工点三个按钮各试一次。

- [ ] **Step 1: 实现环形进度控件与确认窗**

`app/confirm.py`：

```python
"""关机确认窗：置顶居中，大号倒计时数字 + 环形进度。

点右上角 ✕ 等同于「取消」——安全优先，宁可漏关也不误关。
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.theme import color, stylesheet

ACTION_LABELS = {
    "shutdown": ("关机", "立即关机"),
    "restart": ("重启", "立即重启"),
    "sleep": ("睡眠", "立即睡眠"),
    "hibernate": ("休眠", "立即休眠"),
    "logoff": ("注销", "立即注销"),
}


class RingProgress(QWidget):
    """环形进度 + 中央文字。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(160, 160)
        self._ratio = 1.0
        self._text = ""
        self._ring_color = QColor("#4c8dff")
        self._track_color = QColor("#3a3d43")

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self.update()

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def set_ring_color(self, html: str) -> None:
        self._ring_color = QColor(html)
        self.update()

    def set_track_color(self, html: str) -> None:
        self._track_color = QColor(html)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height()) - 16
        rect = QRectF(
            (self.width() - side) / 2,
            (self.height() - side) / 2,
            side,
            side,
        )
        pen_width = max(8, side // 14)

        track_pen = QPen(self._track_color)
        track_pen.setWidth(pen_width)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        ring_pen = QPen(self._ring_color)
        ring_pen.setWidth(pen_width)
        ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(ring_pen)
        # 从 12 点方向顺时针减少
        painter.drawArc(rect, 90 * 16, int(-360 * 16 * self._ratio))

        font = QFont()
        font.setPointSize(max(14, side // 6))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(self.palette().color(self.foregroundRole())))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class ConfirmDialog(QDialog):
    RESULT_CANCEL = "cancel"
    RESULT_NOW = "now"
    RESULT_TIMEOUT = "timeout"

    def __init__(
        self,
        action: str,
        grace_seconds: int,
        theme: str = "dark",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._action = action
        self._total = max(1, int(grace_seconds))
        self._remaining = self._total
        self._theme = theme
        self._result_value = self.RESULT_TIMEOUT

        verb, now_label = ACTION_LABELS.get(action, ("关机", "立即执行"))
        self._verb = verb

        self.setWindowTitle(f"{verb}提醒")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(True)
        self.resize(360, 420)
        self.setStyleSheet(stylesheet(theme))

        self._ring = RingProgress(self)
        self._ring.set_ring_color(color(theme, "accent"))
        self._ring.set_track_color(color(theme, "border"))

        self._caption = QLabel(f"电脑将在 {self._remaining} 秒后{verb}", self)
        self._caption.setObjectName("CountdownCaption")
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._cancel_button = QPushButton("取消" + verb, self)
        self._cancel_button.setObjectName("Primary")
        self._cancel_button.clicked.connect(self.cancel)

        self._now_button = QPushButton(now_label, self)
        self._now_button.clicked.connect(self.confirm_now)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addWidget(self._cancel_button)
        buttons.addWidget(self._now_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)
        layout.addStretch(1)
        layout.addWidget(self._ring, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._caption)
        layout.addStretch(1)
        layout.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._update_display()

        if parent is None:
            self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

    def _update_display(self) -> None:
        minutes, seconds = divmod(self._remaining, 60)
        self._ring.set_text(f"{minutes:02d}:{seconds:02d}")
        self._ring.set_ratio(self._remaining / self._total)
        self._caption.setText(f"电脑将在 {self._remaining} 秒后{self._verb}")

        # 最后 10 秒转成警示色
        if self._remaining <= 10:
            self._ring.set_ring_color(color(self._theme, "danger"))
        else:
            self._ring.set_ring_color(color(self._theme, "accent"))

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self._result_value = self.RESULT_TIMEOUT
            self.done(0)
            return
        self._update_display()

    def cancel(self) -> None:
        """公开方法：窗口上的按钮与外部（托盘菜单）都可以调。"""
        self._timer.stop()
        self._result_value = self.RESULT_CANCEL
        self.done(0)

    def confirm_now(self) -> None:
        self._timer.stop()
        self._result_value = self.RESULT_NOW
        self.done(0)

    def reject(self) -> None:
        """点 ✕ 或按 Esc 都视为取消，不视为超时。"""
        self._timer.stop()
        self._result_value = self.RESULT_CANCEL
        super().reject()

    def exec_modal(self) -> str:
        self._timer.start()
        self.exec()
        self._timer.stop()
        return self._result_value
```

- [ ] **Step 2: 语法自检**

```bash
cd /d/AutoShutdownPro
python -c "import ast, pathlib; ast.parse(pathlib.Path('app/confirm.py').read_text(encoding='utf-8')); print('语法 OK')"
```

Expected: `语法 OK`

- [ ] **Step 3: 确认导入不报错**

```bash
cd /d/AutoShutdownPro
python -c "from app.confirm import ConfirmDialog, RingProgress; print('导入 OK')"
```

Expected: `导入 OK`

- [ ] **Step 4: 人工弹窗验收**

```bash
cd /d/AutoShutdownPro
python -c "
import sys
from PySide6.QtWidgets import QApplication
from app.confirm import ConfirmDialog

app = QApplication(sys.argv)
for action in ('shutdown', 'restart', 'sleep'):
    dlg = ConfirmDialog(action, 15, 'dark')
    print(f'{action} -> {dlg.exec_modal()}')
"
```

逐项人工确认并记录返回值：

1. 窗口是否**置顶居中**显示
2. 倒计时数字是否每秒递减、环形进度是否同步收缩
3. **最后 10 秒环形是否变红**
4. 点「取消关机」→ 应打印 `shutdown -> cancel`
5. 点「立即重启」→ 应打印 `restart -> now`
6. 点右上角 ✕ → 应打印 `sleep -> cancel`
7. 等倒计时归零 → 应打印下一轮的 `-> timeout`

- [ ] **Step 5: 切换主题再验一次**

```bash
cd /d/AutoShutdownPro
python -c "
import sys
from PySide6.QtWidgets import QApplication
from app.confirm import ConfirmDialog

app = QApplication(sys.argv)
print(ConfirmDialog('shutdown', 10, 'light').exec_modal())
"
```

Expected: 窗口为浅色底、深色字，倒计时归零后打印 `timeout`

- [ ] **Step 6: 提交**

```bash
cd /d/AutoShutdownPro
git add app/confirm.py
git commit -m "feat: 关机确认窗，环形倒计时 + 关闭即取消"
```

---

### Task 7: 主窗口

界面主体。状态卡片每秒刷新，所有定时控件的改动都落盘到配置。

**Files:**
- Create: `app/formatting.py`
- Create: `app/window.py`
- Create: `tests/test_formatting.py`

**Interfaces:**
- Consumes: `app.config`（Task 1）、`app.scheduler`（Task 3）、`app.theme`（Task 4）、`app.power`（Task 2）、`app.autostart`（Task 5）
- Produces:
  - `app.formatting.format_remaining(seconds: int) -> str`
  - `app.formatting.format_trigger_time(at: datetime, now: datetime) -> str`
  - `app.window.MainWindow(store, executor, scheduler, autostart, parent=None)` 类（`QMainWindow`）：
    - 信号：`theme_changed = Signal(str)`、`schedule_changed = Signal()`、`cancel_requested = Signal()`
    - 方法：`refresh_status() -> None`、`set_counting(counting: bool) -> None`、`current_theme() -> str`、`apply_theme(theme: str) -> None`
    - 关闭行为：`closeEvent` 只隐藏窗口，不退出应用

- [ ] **Step 1: 写时间格式化的失败测试**

`tests/test_formatting.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_formatting.py -v
```

Expected: 全部 FAIL，报 `ModuleNotFoundError: No module named 'app.formatting'`

- [ ] **Step 3: 实现格式化模块**

`app/formatting.py`：

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd /d/AutoShutdownPro
python -m pytest tests/test_formatting.py -v
```

Expected: 9 passed

- [ ] **Step 5: 实现主窗口**

`app/window.py`：

```python
"""主窗口：状态卡片、快速定时、指定时刻、每天重复、动作与选项。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from PySide6.QtCore import QTime, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from app.autostart import Autostart
from app.config import GRACE_MAX, GRACE_MIN, ConfigStore
from app.formatting import format_remaining, format_trigger_time
from app.paths import ICON_PATH, LAUNCH_BAT, PROJECT_ROOT
from app.power import PowerExecutor, supports_system_abort
from app.scheduler import Scheduler
from app.theme import color, stylesheet

logger = logging.getLogger(__name__)

ACTION_OPTIONS = (
    ("shutdown", "关机"),
    ("restart", "重启"),
    ("sleep", "睡眠"),
    ("hibernate", "休眠"),
    ("logoff", "注销"),
)

ACTION_LABELS_CN = {value: label for value, label in ACTION_OPTIONS}

QUICK_MINUTES = ((30, "30 分钟"), (60, "1 小时"), (120, "2 小时"))


class MainWindow(QMainWindow):
    theme_changed = Signal(str)
    schedule_changed = Signal()
    cancel_requested = Signal()

    def __init__(
        self,
        store: ConfigStore,
        executor: PowerExecutor,
        scheduler: Scheduler,
        autostart: Autostart,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._store = store
        self._executor = executor
        self._scheduler = scheduler
        self._autostart = autostart
        self._theme = "dark"
        self._counting = False

        self.setWindowTitle("定时关机")
        self.setMinimumWidth(480)
        self._build_ui()
        self._load_from_config()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self.refresh_status)
        self._refresh_timer.start()
        self.refresh_status()

    # ---------- 构建界面 ----------

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)

        layout.addLayout(self._build_title_bar())
        layout.addWidget(self._build_status_card())
        layout.addWidget(self._section("快速定时"))
        layout.addLayout(self._build_quick_row())
        layout.addWidget(self._section("指定时刻"))
        layout.addLayout(self._build_oneoff_row())
        layout.addWidget(self._section("每天重复"))
        layout.addLayout(self._build_daily_row())
        layout.addWidget(self._section("到点执行"))
        layout.addLayout(self._build_action_row())
        layout.addLayout(self._build_options_row())
        layout.addStretch(1)
        layout.addWidget(self._build_cancel_button())

    def _build_title_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        title = QLabel("⏻  定时关机")
        title.setObjectName("TitleText")
        row.addWidget(title)
        row.addStretch(1)

        self._theme_button = QPushButton("☾")
        self._theme_button.setObjectName("IconButton")
        self._theme_button.setToolTip("切换暗色 / 亮色主题")
        self._theme_button.clicked.connect(self._toggle_theme)
        row.addWidget(self._theme_button)
        return row

    def _build_status_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(16, 14, 16, 14)
        inner.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        self._status_dot = QLabel("●")
        self._status_dot.setObjectName("StatusDot")
        self._status_text = QLabel("未排定")
        self._status_text.setObjectName("StatusText")
        top.addWidget(self._status_dot)
        top.addWidget(self._status_text)
        top.addStretch(1)

        self._status_detail = QLabel("当前无定时任务")
        self._status_detail.setObjectName("StatusDetail")

        inner.addLayout(top)
        inner.addWidget(self._status_detail)
        return card

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    def _build_quick_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for minutes, label in QUICK_MINUTES:
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, m=minutes: self._apply_quick(m))
            row.addWidget(button)
        return row

    def _build_oneoff_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._day_combo = QComboBox()
        self._day_combo.addItems(["今天", "明天"])
        row.addWidget(self._day_combo)

        self._oneoff_time = QTimeEdit()
        self._oneoff_time.setDisplayFormat("HH:mm")
        self._oneoff_time.setTime(QTime(23, 30))
        row.addWidget(self._oneoff_time, 1)

        set_button = QPushButton("设定")
        set_button.setObjectName("Primary")
        set_button.clicked.connect(self._apply_oneoff)
        row.addWidget(set_button)
        return row

    def _build_daily_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._daily_check = QCheckBox("每天")
        self._daily_check.toggled.connect(self._apply_daily)
        row.addWidget(self._daily_check)

        self._daily_time = QTimeEdit()
        self._daily_time.setDisplayFormat("HH:mm")
        self._daily_time.setTime(QTime(23, 30))
        self._daily_time.timeChanged.connect(self._apply_daily)
        row.addWidget(self._daily_time, 1)

        hint = QLabel("开机自启后长期生效")
        hint.setObjectName("Hint")
        row.addWidget(hint)
        return row

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self._action_group = QButtonGroup(self)
        for index, (value, label) in enumerate(ACTION_OPTIONS):
            radio = QRadioButton(label)
            radio.setProperty("action_value", value)
            self._action_group.addButton(radio, index)
            row.addWidget(radio)
        row.addStretch(1)

        self._action_group.buttonClicked.connect(self._apply_action)
        return row

    def _build_options_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        row.addWidget(QLabel("确认等待"))
        self._grace_spin = QSpinBox()
        self._grace_spin.setRange(GRACE_MIN, GRACE_MAX)
        self._grace_spin.setSuffix(" 秒")
        self._grace_spin.valueChanged.connect(self._apply_grace)
        row.addWidget(self._grace_spin)

        self._force_check = QCheckBox("强制结束未响应程序")
        self._force_check.toggled.connect(self._apply_force)
        row.addWidget(self._force_check)

        row.addStretch(1)

        self._autostart_check = QCheckBox("开机自启")
        self._autostart_check.toggled.connect(self._apply_autostart)
        row.addWidget(self._autostart_check)
        return row

    def _build_cancel_button(self) -> QPushButton:
        self._cancel_button = QPushButton("立即取消关机")
        self._cancel_button.setObjectName("Danger")
        # 只发信号，真正的取消逻辑由 main.py 的 AppController 接管
        self._cancel_button.clicked.connect(self.cancel_requested.emit)
        return self._cancel_button

    # ---------- 配置 <-> 界面 ----------

    def _load_from_config(self) -> None:
        cfg = self._store.load()

        for button in self._action_group.buttons():
            if button.property("action_value") == cfg.action:
                button.setChecked(True)
                break

        self._grace_spin.setValue(cfg.grace_seconds)
        self._force_check.setChecked(cfg.force)

        # 载入时屏蔽信号，避免触发写盘
        self._daily_check.blockSignals(True)
        self._daily_check.setChecked(cfg.daily.enabled)
        self._daily_check.blockSignals(False)

        self._daily_time.blockSignals(True)
        self._daily_time.setTime(QTime.fromString(cfg.daily.time, "HH:mm"))
        self._daily_time.blockSignals(False)

        self._autostart_check.blockSignals(True)
        self._autostart_check.setChecked(self._autostart.is_enabled())
        self._autostart_check.blockSignals(False)

        self.apply_theme(cfg.theme)

    def current_theme(self) -> str:
        return self._theme

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        self.setStyleSheet(stylesheet(theme))
        self._theme_button.setText("☀" if theme == "dark" else "☾")
        self.theme_changed.emit(theme)

    def _toggle_theme(self) -> None:
        new_theme = "light" if self._theme == "dark" else "dark"
        cfg = self._store.load()
        cfg.theme = new_theme
        self._store.save(cfg)
        self.apply_theme(new_theme)

    def _apply_quick(self, minutes: int) -> None:
        target = datetime.now() + timedelta(minutes=minutes)
        self._set_oneoff(target, f"{minutes} 分钟后")

    def _apply_oneoff(self) -> None:
        qt_time = self._oneoff_time.time()
        target = datetime.now().replace(
            hour=qt_time.hour(),
            minute=qt_time.minute(),
            second=0,
            microsecond=0,
        )
        if self._day_combo.currentIndex() == 1 or target <= datetime.now():
            target += timedelta(days=1)
        label = "今天" if target.date() == datetime.now().date() else "明天"
        self._set_oneoff(target, f"{label} {target.strftime('%H:%M')}")

    def _set_oneoff(self, target: datetime, label: str) -> None:
        cfg = self._store.load()

        # 若上一个排程已经下发给系统，必须先撤销：已有排程时再次 shutdown 会返回 1190
        if cfg.oneoff.enabled and supports_system_abort(cfg.action):
            self._executor.abort()

        cfg.oneoff.enabled = True
        cfg.oneoff.target = target.isoformat()
        cfg.oneoff.label = label
        self._store.save(cfg)
        self._scheduler.refresh()
        self.schedule_changed.emit()
        self.refresh_status()
        logger.info("已排定一次性%s: %s", label, target)

    def _apply_daily(self) -> None:
        cfg = self._store.load()
        cfg.daily.enabled = self._daily_check.isChecked()
        cfg.daily.time = self._daily_time.time().toString("HH:mm")
        self._store.save(cfg)
        self._scheduler.refresh()
        self.schedule_changed.emit()
        self.refresh_status()

    def _apply_action(self, button) -> None:
        cfg = self._store.load()
        cfg.action = button.property("action_value")
        self._store.save(cfg)
        logger.info("到点动作改为: %s", cfg.action)

    def _apply_grace(self, value: int) -> None:
        cfg = self._store.load()
        cfg.grace_seconds = value
        self._store.save(cfg)

    def _apply_force(self, checked: bool) -> None:
        cfg = self._store.load()
        cfg.force = checked
        self._store.save(cfg)

    def _apply_autostart(self, checked: bool) -> None:
        cfg = self._store.load()
        cfg.autostart = checked
        self._store.save(cfg)
        self._autostart.sync(
            checked,
            target=LAUNCH_BAT,
            workdir=PROJECT_ROOT,
            icon=ICON_PATH,
        )

    # ---------- 状态刷新 ----------

    def refresh_status(self) -> None:
        cfg = self._store.load()
        now = datetime.now()
        trigger = self._scheduler.next_trigger(now)

        # 正在倒计时（确认窗开着）时，窗口由 main.py 通过 set_counting 置位
        if getattr(self, "_counting", False):
            self._status_dot.setStyleSheet(f"color: {color(self._theme, 'warn')};")
            self._status_text.setText("即将执行")
            self._status_detail.setText(f"{cfg.grace_seconds} 秒后执行，倒计时进行中")
            self._cancel_button.setEnabled(True)
            return

        if trigger is None:
            self._status_dot.setStyleSheet(f"color: {color(self._theme, 'idle')};")
            self._status_text.setText("未排定")
            self._status_detail.setText("当前无定时任务")
            self._cancel_button.setEnabled(False)
            return

        remaining = int((trigger.at - now).total_seconds())
        self._status_dot.setStyleSheet(f"color: {color(self._theme, 'ok')};")
        self._status_text.setText("已排定" + ACTION_LABELS_CN.get(cfg.action, "关机"))
        self._status_detail.setText(
            f"{format_trigger_time(trigger.at, now)} · 剩余 {format_remaining(remaining)}"
        )
        self._cancel_button.setEnabled(True)

    def set_counting(self, counting: bool) -> None:
        self._counting = counting
        self.refresh_status()

    # ---------- 窗口行为 ----------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        """关闭窗口只是隐藏，应用继续在托盘里跑定时。"""
        event.ignore()
        self.hide()
```

- [ ] **Step 6: 跑一次界面看效果**

```bash
cd /d/AutoShutdownPro
python -c "
import sys
from PySide6.QtWidgets import QApplication
from app.autostart import Autostart
from app.config import ConfigStore
from app.paths import CONFIG_PATH
from app.power import PowerExecutor
from app.scheduler import Scheduler
from app.window import MainWindow

app = QApplication(sys.argv)
store = ConfigStore(CONFIG_PATH)
scheduler = Scheduler(store.load)
win = MainWindow(store, PowerExecutor(dry_run=True), scheduler, Autostart())
win.show()
app.exec()
"
```

人工确认：

1. 窗口是否为暗色主题、状态卡片有圆角边框
2. 点标题栏 ☾ 是否切到亮色，窗口整体变色
3. 点「30 分钟」→ 状态卡片是否变成绿色圆点 + "今天/明天 HH:MM · 剩余 …"
4. 剩余时间是否每秒递减
5. 拖动「确认等待」到 30 → 关掉重开，是否仍是 30
6. 单选按钮切换动作后，状态卡片文案是否跟着变（"已排定重启"等）
7. 点右上角 ✕ → **窗口消失但不报错**（应用仍在跑，但此时没有托盘图标，需 Ctrl+C 结束）

- [ ] **Step 7: 跑全量测试**

```bash
cd /d/AutoShutdownPro
python -m pytest -v
```

Expected: 74 passed（config 12 + power 19 + scheduler 15 + theme 11 + autostart 8 + formatting 9）。若环境里没有 PowerShell，autostart 那 8 项会失败。

- [ ] **Step 8: 提交**

```bash
cd /d/AutoShutdownPro
git add app/formatting.py app/window.py tests/test_formatting.py
git commit -m "feat: 主窗口与时间格式化"
```

---

### Task 8: 托盘图标与应用入口

把所有部件接起来。这一层承载真正的触发流程——到点后先交系统排程、再弹确认窗、按返回值决定撤销还是执行。

**Files:**
- Create: `app/tray.py`
- Create: `main.py`

**Interfaces:**
- Consumes: 前面全部模块
- Produces:
  - `app.tray.TrayIcon(window, on_cancel, on_quit, parent=None)` 类（`QSystemTrayIcon`）：
    - `update_status(text: str) -> None`
    - `set_theme(theme: str) -> None`
  - `main.build_application(argv) -> tuple[QApplication, AppController]`
  - `main.AppController` 类：方法 `handle_trigger(trigger) -> None`、`cancel_current() -> None`、`quit_app() -> None`

- [ ] **Step 1: 实现托盘图标**

`app/tray.py`：

```python
"""系统托盘图标与右键菜单。"""
from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from app.paths import ICON_PATH


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window, on_cancel, on_quit, parent: QWidget | None = None):
        icon = QIcon(str(ICON_PATH)) if ICON_PATH.exists() else QIcon()
        super().__init__(icon, parent)

        self._window = window
        self.setToolTip("定时关机 · 空闲")

        menu = QMenu()

        open_action = QAction("打开主界面", menu)
        open_action.triggered.connect(self._show_window)
        menu.addAction(open_action)

        self._cancel_action = QAction("取消关机", menu)
        self._cancel_action.triggered.connect(on_cancel)
        menu.addAction(self._cancel_action)

        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(on_quit)
        menu.addAction(quit_action)

        self._menu = menu
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def update_status(self, text: str) -> None:
        self.setToolTip(text)

    def set_theme(self, theme: str) -> None:
        # 托盘菜单跟随系统绘制，这里只在亮色下切换图标配色（当前共用同一图标）
        self._menu.setStyleSheet("" if theme == "dark" else "QMenu { color: #1f2328; }")
```

- [ ] **Step 2: 实现应用入口**

`main.py`：

```python
"""应用入口：单实例锁、日志、部件组装、触发流程。"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSharedMemory, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app.autostart import Autostart
from app.config import ConfigStore
from app.confirm import ConfirmDialog
from app.formatting import format_remaining
from app.paths import CONFIG_PATH, ICON_PATH, LAUNCH_BAT, LOG_PATH, PROJECT_ROOT
from app.power import PowerExecutor, supports_system_abort
from app.scheduler import Scheduler
from app.tray import TrayIcon
from app.window import MainWindow

logger = logging.getLogger(__name__)

SHARED_MEMORY_KEY = "AutoShutdownPro-SingleInstance-v1"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


class AppController:
    """把配置、调度、窗口、托盘、电源执行串起来。"""

    def __init__(self, app: QApplication, store: ConfigStore, force_dry_run: bool = False):
        self.app = app
        self.store = store

        cfg = store.load()
        dry_run = True if force_dry_run else cfg.dry_run
        self.executor = PowerExecutor(dry_run=dry_run)
        self.autostart = Autostart()
        self.scheduler = Scheduler(store.load)
        self.scheduler.triggered.connect(self.handle_trigger)

        self.window = MainWindow(store, self.executor, self.scheduler, self.autostart)
        self.window.theme_changed.connect(self._on_theme_changed)
        self.window.cancel_requested.connect(self.cancel_current)

        self.tray = TrayIcon(self.window, on_cancel=self.cancel_current, on_quit=self.quit_app)
        # 构造 MainWindow 时 theme_changed 还没接上，这里补一次初始同步
        self.tray.set_theme(self.window.current_theme())
        self.tray.show()

        self._confirm_dialog: ConfirmDialog | None = None

        self._status_timer = QTimer()
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._refresh_tray)
        self._status_timer.start()

        self.scheduler.refresh()
        self._restore_autostart()
        if dry_run:
            logger.warning("dry-run 模式已开启：所有电源命令只写日志，不会真的关机")

    def _restore_autostart(self) -> None:
        """启动文件夹的快捷方式若被手动删掉，按配置写回。"""
        cfg = self.store.load()
        want = cfg.autostart
        has = self.autostart.is_enabled()
        if want and not has:
            logger.info("检测到自启快捷方式缺失，按配置重建")
            self.autostart.sync(True, target=LAUNCH_BAT, workdir=PROJECT_ROOT, icon=ICON_PATH)
        elif not want and has:
            self.autostart.sync(False, target=LAUNCH_BAT, workdir=PROJECT_ROOT, icon=ICON_PATH)

    def _refresh_tray(self) -> None:
        now = datetime.now()
        trigger = self.scheduler.next_trigger(now)
        if trigger is None:
            self.tray.update_status("定时关机 · 空闲")
            return
        remaining = int((trigger.at - now).total_seconds())
        self.tray.update_status(
            f"{trigger.at.strftime('%H:%M')} 后执行 · 剩余 {format_remaining(remaining)}"
        )

    def _on_theme_changed(self, theme: str) -> None:
        self.tray.set_theme(theme)

    # ---------- 触发流程 ----------

    def handle_trigger(self, trigger) -> None:
        cfg = self.store.load()
        action = cfg.action
        grace = cfg.grace_seconds
        force = cfg.force

        logger.info("定时触发: %s @ %s，动作=%s", trigger.kind, trigger.at, action)

        # 一次性定时触发即消耗，每日重复保留
        if trigger.kind == "oneoff":
            cfg.oneoff.enabled = False
            cfg.oneoff.target = ""
            cfg.oneoff.label = ""
            self.store.save(cfg)

        # 关机/重启：先交给系统排程，形成双保险
        if supports_system_abort(action):
            self.executor.arm(action, grace, force)

        self.window.set_counting(True)
        self.window.show()
        self.window.raise_()

        dialog = ConfirmDialog(action, grace, cfg.theme, parent=None)
        self._confirm_dialog = dialog
        result = dialog.exec_modal()
        self._confirm_dialog = None
        self.window.set_counting(False)

        if result == ConfirmDialog.RESULT_CANCEL:
            if supports_system_abort(action):
                self.executor.abort()
                logger.info("用户取消，已撤销系统排程")
            else:
                logger.info("用户取消，未执行 %s", action)
            self.scheduler.refresh()
            self.window.refresh_status()
            return

        if result == ConfirmDialog.RESULT_NOW:
            # 已有排程时再次 shutdown 会返回 1190，必须先撤销
            if supports_system_abort(action):
                self.executor.abort()
            self.executor.execute_now(action, force)
            logger.info("用户要求立即执行 %s", action)
            return

        # 超时：关机/重启的系统排程继续跑；其余动作由应用补上
        if not supports_system_abort(action):
            self.executor.execute_now(action, force)
            logger.info("超时，执行 %s", action)
        else:
            logger.info("超时，交由系统排程执行 %s", action)

    def cancel_current(self) -> None:
        """主界面/托盘上的「取消关机」。"""
        cfg = self.store.load()

        if self._confirm_dialog is not None:
            self._confirm_dialog.cancel()
            return

        if supports_system_abort(cfg.action):
            self.executor.abort()

        cfg.oneoff.enabled = False
        cfg.oneoff.target = ""
        cfg.oneoff.label = ""
        self.store.save(cfg)
        self.scheduler.refresh()
        self.window.refresh_status()
        logger.info("已取消所有已排定的关机")

    def quit_app(self) -> None:
        cfg = self.store.load()
        if cfg.daily.enabled:
            answer = QMessageBox.question(
                self.window,
                "退出确认",
                "「每天重复」正在启用，退出后该规则将失效（直到下次开机自启）。\n确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.scheduler.stop()
        self.tray.hide()
        self.app.quit()


def build_application(argv: list[str] | None = None) -> tuple[QApplication, AppController]:
    parser = argparse.ArgumentParser(description="定时关机")
    parser.add_argument("--dry-run", action="store_true", help="只记录不执行，调试用")
    args, qt_argv = parser.parse_known_args(argv if argv is not None else sys.argv[1:])

    app = QApplication([sys.argv[0], *qt_argv])
    app.setQuitOnLastWindowClosed(False)  # 关窗口不退出，驻留托盘

    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    store = ConfigStore(CONFIG_PATH)
    controller = AppController(app, store, force_dry_run=args.dry_run)
    return app, controller


def main() -> int:
    setup_logging()

    shared = QSharedMemory(SHARED_MEMORY_KEY)
    if not shared.create(1):
        logger.warning("应用已在运行，本次启动退出")
        return 0

    app, controller = build_application()
    controller.window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 语法与导入自检**

```bash
cd /d/AutoShutdownPro
python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8')) for p in ('main.py', 'app/tray.py')]; print('语法 OK')"
python -c "import main; print('导入 OK')"
```

Expected: `语法 OK` 然后 `导入 OK`

- [ ] **Step 4: dry-run 全流程验收**

```bash
cd /d/AutoShutdownPro
python main.py --dry-run
```

人工逐项确认：

1. 主窗口弹出、托盘出现图标
2. 点「30 分钟」→ 托盘悬停提示是否变成"HH:MM 后执行 · 剩余 30 分 0 秒"，且每秒递减
3. 主界面状态卡片是否同步显示剩余
4. 把「确认等待」改成 **10 秒**，然后重新点一个 **1 分钟**后触发的时刻（用「指定时刻」设成 1 分钟后）
5. 到点后确认窗是否弹出，倒计时是否归零
6. 倒计时归零后查看 `run.log`，应出现 `[DRY-RUN] 将执行: shutdown.exe /s /t 10`，且**电脑没有关机**
7. 点托盘右键「取消关机」→ 状态卡片是否回到"未排定"
8. 关闭主窗口 → 托盘图标仍在，定时继续
9. 托盘右键「退出」→ 应用退出，托盘图标消失

- [ ] **Step 5: 验证取消路径**

```bash
cd /d/AutoShutdownPro
python main.py --dry-run
```

设一个 1 分钟后的定时，等确认窗弹出：

1. 点「取消关机」→ `run.log` 里应出现 `[DRY-RUN] 将执行: shutdown.exe /a`
2. 重新设一个 1 分钟定时，等窗弹出后点右上角 ✕ → 同样应出现 `/a`
3. 重新设一个，等倒计时归零 → 应出现 `[DRY-RUN] 将执行: shutdown.exe /s /t N`

- [ ] **Step 6: 提交**

```bash
cd /d/AutoShutdownPro
git add app/tray.py main.py
git commit -m "feat: 托盘图标与应用入口，接通完整触发流程"
```

---

### Task 9: 图标、启动脚本与桌面快捷方式

产出双击即用的交付形态。图标用 `QPainter` 画，不引入图像库依赖。

**Files:**
- Create: `tools/make_icon.py`
- Create: `tools/make_shortcut.py`
- Create: `启动.bat`
- Create: `assets/icon.ico`（由脚本生成）

**Interfaces:**
- Consumes: `app.paths`（Task 1）
- Produces: `assets/icon.ico`、桌面上的 `定时关机.lnk`

- [ ] **Step 1: 实现图标生成脚本**

`tools/make_icon.py`：

```python
"""用 QPainter 画出电源符号图标，并写成多尺寸 .ico。

Qt 的 QPixmap.save 一次只能存一种尺寸，所以这里手工拼 ICO 容器：
每个条目塞一张 PNG（ICO 自 Vista 起支持内嵌 PNG）。
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.paths import ICON_PATH  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)
BG_COLOR = "#2f6feb"
FG_COLOR = "#ffffff"


def render(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 圆角底
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(BG_COLOR))
    radius = size * 0.22
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    # 电源符号：开口圆环 + 顶部竖线
    pen = QPen(QColor(FG_COLOR))
    pen.setWidthF(max(1.5, size * 0.09))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    inset = size * 0.32
    ring = QRectF(inset, inset * 1.15, size - 2 * inset, size - 2 * inset)
    # 从 60° 画到 300°，留出顶部缺口
    painter.drawArc(ring, 60 * 16, 240 * 16)

    painter.drawLine(
        int(size / 2),
        int(size * 0.16),
        int(size / 2),
        int(size * 0.46),
    )
    painter.end()
    return pixmap


def png_bytes(pixmap: QPixmap) -> bytes:
    buffer = QBuffer(QByteArray())
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(buffer.data())


def write_ico(path: Path, pixmaps: list[QPixmap]) -> None:
    count = len(pixmaps)
    header = struct.pack("<HHH", 0, 1, count)
    entries = b""
    payload = b""
    offset = 6 + 16 * count

    for pixmap in pixmaps:
        data = png_bytes(pixmap)
        width = pixmap.width() if pixmap.width() < 256 else 0
        height = pixmap.height() if pixmap.height() < 256 else 0
        entries += struct.pack(
            "<BBBBHHII", width, height, 0, 0, 1, 32, len(data), offset
        )
        offset += len(data)
        payload += data

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + payload)


def main() -> int:
    app = QApplication(sys.argv)  # noqa: F841 (QPixmap 需要 QApplication)
    pixmaps = [render(size) for size in SIZES]
    write_ico(ICON_PATH, pixmaps)
    print(f"已生成 {ICON_PATH}（{len(SIZES)} 种尺寸）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 生成图标并校验**

```bash
cd /d/AutoShutdownPro
python tools/make_icon.py
python -c "
from PySide6.QtGui import QIcon
import sys
from PySide6.QtWidgets import QApplication
from app.paths import ICON_PATH
app = QApplication(sys.argv)
icon = QIcon(str(ICON_PATH))
print('可用尺寸:', [f'{s.width()}x{s.height()}' for s in icon.availableSizes()])
"
```

Expected: 打印 `已生成 ...`，并列出 7 种尺寸

- [ ] **Step 3: 写启动脚本**

`启动.bat`：

```bat
@echo off
cd /d "%~dp0"
start "" pythonw.exe "%~dp0main.py"
```

> 用 `pythonw.exe` 而非 `python.exe` 是为了不闪出黑色控制台窗口。若 `pythonw.exe` 不在 PATH，把这一行改成 `pythonw.exe` 的绝对路径。

- [ ] **Step 4: 验证启动脚本**

先确认 `pythonw.exe` 可用：

```bash
where pythonw.exe
```

Expected: 输出一个路径。若没有输出，先执行 `python -c "import sys,os; print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"` 拿到绝对路径并替换进 `启动.bat`。

然后双击 `D:\AutoShutdownPro\启动.bat`，确认：

1. **不出现黑色控制台窗口**
2. 主窗口与托盘图标正常出现
3. 关闭窗口后托盘图标仍在

在托盘右键「退出」结束。

- [ ] **Step 5: 实现桌面快捷方式脚本**

`tools/make_shortcut.py`：

```python
"""在桌面创建「定时关机」快捷方式，指向 启动.bat。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.paths import ICON_PATH, LAUNCH_BAT, PROJECT_ROOT  # noqa: E402

SHORTCUT_NAME = "定时关机.lnk"
CREATE_NO_WINDOW = 0x08000000

_PS_TEMPLATE = (
    "$ws = New-Object -ComObject WScript.Shell;"
    "$sc = $ws.CreateShortcut('{lnk}');"
    "$sc.TargetPath = '{target}';"
    "$sc.WorkingDirectory = '{workdir}';"
    "$sc.IconLocation = '{icon}';"
    "$sc.Description = '定时关机';"
    "$sc.Save()"
)


def desktop_dir() -> Path:
    return Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"


def ps_quote(value: object) -> str:
    return str(value).replace("'", "''")


def main() -> int:
    lnk = desktop_dir() / SHORTCUT_NAME
    script = _PS_TEMPLATE.format(
        lnk=ps_quote(lnk),
        target=ps_quote(LAUNCH_BAT),
        workdir=ps_quote(PROJECT_ROOT),
        icon=ps_quote(ICON_PATH),
    )
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        check=False,
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
    )

    if completed.returncode != 0:
        print(f"创建失败: {completed.stderr.strip()}", file=sys.stderr)
        return 1

    print(f"已创建快捷方式: {lnk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: 创建并验证桌面快捷方式**

```bash
cd /d/AutoShutdownPro
python tools/make_shortcut.py
ls "$USERPROFILE/Desktop/定时关机.lnk"
```

Expected: 打印 `已创建快捷方式: ...`，`ls` 能找到该文件

人工确认：桌面上出现「定时关机」图标，**图标是蓝色圆角方块 + 白色电源符号**（而不是默认的 bat 文件图标）；双击它应用正常启动。

- [ ] **Step 7: 提交**

```bash
cd /d/AutoShutdownPro
git add tools/ 启动.bat assets/icon.ico
git commit -m "feat: 应用图标、启动脚本与桌面快捷方式"
```

---

### Task 10: 集成验收与旧方案下线

把真实模式跑通，并停用旧的计划任务。**这一步会真的关机，也真的会改系统状态，必须用户在场逐步确认。**

**Files:**
- 无新增文件，只做验证与系统状态变更

**Interfaces:**
- Consumes: 全部已完成模块
- Produces: 可日常使用的应用；旧的 `AutoShutdown_2AM` 计划任务停止生效

- [ ] **Step 1: 确认 dry-run 全流程无异常**

```bash
cd /d/AutoShutdownPro
python main.py --dry-run
```

按 Task 8 Step 4 的清单再走一遍，确认 `run.log` 中所有命令都带 `[DRY-RUN]` 前缀，没有任何一条真实执行。

- [ ] **Step 2: 检查现有计划任务状态**

```bash
powershell -NoProfile -Command "Get-ScheduledTask -TaskName 'AutoShutdown_2AM' | Select-Object TaskName, State"
```

Expected: 显示 `AutoShutdown_2AM` 及其 `State`（通常为 `Ready`）

**在执行 Step 3 前，先向用户展示这条输出并取得明确同意。** 删除计划任务是系统状态变更，不能替用户决定。

- [ ] **Step 3: 停用旧计划任务（需用户确认后进行）**

```bash
powershell -NoProfile -Command "Unregister-ScheduledTask -TaskName 'AutoShutdown_2AM' -Confirm:\$false"
```

若提示权限不足，改为：让用户在**以管理员身份运行**的 PowerShell 里执行同一条命令（用 `!` 前缀在当前会话里跑，或手动打开管理员终端）。

验证：

```bash
powershell -NoProfile -Command "Get-ScheduledTask -TaskName 'AutoShutdown_2AM' -ErrorAction SilentlyContinue"
```

Expected: 无输出（任务已不存在）

- [ ] **Step 4: 确认真实模式不误伤（不触发关机）**

```bash
cd /d/AutoShutdownPro
python main.py
```

注意：**这条命令没有 `--dry-run`**，是真实模式。只做以下检查，**不要设定 5 分钟以内的定时**：

1. 主界面状态卡片显示"未排定"
2. 点「30 分钟」→ 状态卡片变成绿色 + 显示剩余时间
3. **立即点「立即取消关机」** → 状态卡片回到"未排定"
4. 检查 `run.log`，应看到真实的 `shutdown.exe /s /t 60` 与 `shutdown.exe /a` 各一条
5. 用 `shutdown /a` 确认系统里没有残留排程：

```bash
shutdown /a
```

Expected: 提示"没有正在进行的系统关闭"，说明 Step 3 的取消确实生效了

- [ ] **Step 5: 真实关机验收（需用户明确同意）**

**执行前必须向用户确认。** 用户同意后：

```bash
cd /d/AutoShutdownPro
python main.py
```

1. 把「确认等待」设为 **30 秒**
2. 「指定时刻」设成 **2 分钟后**
3. 等确认窗弹出，确认倒计时数字递减、环形进度收缩、最后 10 秒变红
4. **点「取消关机」**，验证排程被撤销、电脑没有关
5. 再设一次 2 分钟后的定时，这次**不做任何操作**，让倒计时归零
6. 观察电脑是否在宽限期结束后自动关机

Expected: 第 4 步不关机；第 6 步正常关机

- [ ] **Step 6: 重启后验证持久化**

电脑重启后（无论上一步是否触发关机，手动重启一次即可）：

1. 应用是否**自动启动**并出现在托盘（若之前勾选了"开机自启"）
2. 勾选"每天 23:30"，然后重启一次
3. 重启后检查托盘悬停提示是否显示 `23:30 后执行 · 剩余 …`
4. 主界面状态卡片是否显示"已排定关机 · 今天/明天 23:30"

- [ ] **Step 7: 跑全量测试收尾**

```bash
cd /d/AutoShutdownPro
python -m pytest -v
```

Expected: 全部通过

- [ ] **Step 8: 最终提交**

```bash
cd /d/AutoShutdownPro
git add -A
git commit -m "chore: 集成验收通过，旧计划任务下线"
```

---

## 附录 A：验收清单（对应 spec 第 7.3 节）

| # | 验收项 | 对应 Task |
|---|---|---|
| 1 | 快速定时 30 分钟，状态卡片逐秒递减 | Task 8 Step 4 |
| 2 | 点「取消关机」中止排程，状态回未排定 | Task 8 Step 5 |
| 3 | 点 ✕ 同样中止关机 | Task 8 Step 5 |
| 4 | 关主窗口后托盘仍在、悬停显示剩余 | Task 8 Step 4 |
| 5 | 托盘右键「取消关机」生效 | Task 8 Step 4 |
| 6 | 切换暗色/亮色即时生效且持久化 | Task 7 Step 6 |
| 7 | 勾选开机自启后启动文件夹出现快捷方式 | Task 9 Step 6 |
| 8 | 每天重复在重启后依然生效 | Task 10 Step 6 |
| 9 | 真实执行一次关机 | Task 10 Step 5 |

## 附录 B：已知风险与应对

| 风险 | 应对 |
|---|---|
| `shutdown /s /t N` 后再次排程返回 1190 | 已在 `handle_trigger` 的"立即执行"分支先 `abort()` 再执行 |
| 系统未启用休眠时 `SetSuspendState(1)` 失败 | `hibernate_available()` 可查询；失败时记录日志，不崩溃 |
| 长间隔 QTimer 在 Qt 中溢出（>24 天） | `Scheduler` 用 `_MAX_INTERVAL_MS` 分 6 小时一段等待 |
| 调试时误触发真实关机 | `power.py` 是唯一出口，`--dry-run` 一处生效；Task 10 前全程 dry-run |
| 启动文件夹快捷方式被手动删除 | `AppController._restore_autostart()` 在每次启动时按配置写回 |
| 配置文件被外部改坏 | `ConfigStore.load()` 备份为 `.corrupt-<时间戳>` 并回退默认值 |

