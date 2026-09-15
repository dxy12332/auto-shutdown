"""在桌面创建「定时关机」快捷方式，指向 启动.bat。

用 PowerShell 的 WScript.Shell COM 接口，不引入 pywin32 依赖。
这里用 -Command 传内联命令，不涉及 .ps1 文件加载，因此无需改动 ExecutionPolicy。
"""
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
