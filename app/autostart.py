"""开机自启：在用户启动文件夹增删快捷方式。

走 PowerShell 的 WScript.Shell COM 接口，避免引入 pywin32 依赖。
窗口样式设为 7（最小化），配合 启动.bat 可以避免启动时闪出控制台。

注：这里用 `-Command` 传入内联命令，而非执行 .ps1 文件，因此不需要也不应
改动 ExecutionPolicy —— 执行策略只约束脚本文件的加载。
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
