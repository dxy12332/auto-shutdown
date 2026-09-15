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
    hibernate: bool = False


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
    return Command(
        argv=[],
        description=f"立即{label}",
        via_api=True,
        hibernate=(action == "hibernate"),
    )


def hibernate_available() -> bool:
    """查询系统是否启用了休眠。

    SetSuspendState 的 Hibernate 参数在未启用休眠时会失败，因此执行休眠前需先确认。
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
        # SetSuspendState 返回非零表示成功；参数为 (bHibernate, bForce, bWakeupEventsDisabled)
        result = powrprof.SetSuspendState(1 if hibernate else 0, 0, 0)
        return bool(result)
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
            result = _call_set_suspend_state(command.hibernate)
            logger.info("已执行: (Win32 API) | %s，结果=%s", command.description, result)
            return result

        shown = " ".join(command.argv)
        try:
            code = self._runner(command.argv)
        except Exception as exc:
            logger.error("执行 %s 失败: %s", shown, exc)
            return False

        if code != 0:
            logger.warning("命令 %s 退出码 %s", shown, code)
            return False

        # 成功也必须留痕：否则日志无法证明命令真的下达到了系统
        logger.info("已执行: %s | %s", shown, command.description)
        return True

    def arm(self, action: str, grace_seconds: int, force: bool) -> bool:
        return self.run(build_arm_command(action, grace_seconds, force))

    def abort(self) -> bool:
        return self.run(build_abort_command())

    def execute_now(self, action: str, force: bool) -> bool:
        return self.run(build_now_command(action, force))
