"""运行期路径解析。

同一份代码要在两种环境下工作：

- **源码运行**：配置、日志、图标资源都放项目目录，一切照旧。
- **打包成 exe**：配置与日志改到 %APPDATA%，图标从 PyInstaller 的解压目录读，
  开机自启指向 exe 自身。

两种模式的路径必须完全隔离——否则打包版会读到开发机上的配置，
而分享给别人后对方根本没有那个目录，程序会写不进去。
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_DIR_NAME = "AutoShutdownPro"
LAUNCH_BAT_NAME = "启动.bat"


@dataclass(frozen=True)
class Paths:
    resource_dir: Path    # 随程序分发的只读资源（图标等）
    data_dir: Path        # 可写的配置与日志目录
    launch_target: Path   # 开机自启要指向的对象
    launch_workdir: Path  # 自启快捷方式的工作目录

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "run.log"

    @property
    def icon_path(self) -> Path:
        return self.resource_dir / "assets" / "icon.ico"

    @property
    def assets_dir(self) -> Path:
        return self.resource_dir / "assets"


def resolve_paths(
    *,
    frozen: bool,
    project_root: Path,
    executable: Path,
    appdata: Path,
    meipass: Path | None,
) -> Paths:
    """按运行环境算出各路径。

    所有外部因素（是否打包、exe 位置、APPDATA、解压目录）都由参数传入，
    这样纯函数可测，不必真的打包一次。
    """
    if frozen:
        resource_dir = Path(meipass) if meipass is not None else Path(executable).parent
        return Paths(
            resource_dir=resource_dir,
            data_dir=Path(appdata) / APP_DIR_NAME,
            launch_target=Path(executable),
            launch_workdir=Path(executable).parent,
        )

    root = Path(project_root)
    return Paths(
        resource_dir=root,
        data_dir=root,
        launch_target=root / LAUNCH_BAT_NAME,
        launch_workdir=root,
    )


def _default_appdata() -> Path:
    raw = os.environ.get("APPDATA")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Roaming"


_RUNTIME = resolve_paths(
    frozen=getattr(sys, "frozen", False),
    project_root=Path(__file__).resolve().parent.parent,
    executable=Path(sys.executable),
    appdata=_default_appdata(),
    meipass=Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else None,
)

RESOURCE_DIR = _RUNTIME.resource_dir
DATA_DIR = _RUNTIME.data_dir
CONFIG_PATH = _RUNTIME.config_path
LOG_PATH = _RUNTIME.log_path
ICON_PATH = _RUNTIME.icon_path
ASSETS_DIR = _RUNTIME.assets_dir
LAUNCH_TARGET = _RUNTIME.launch_target
LAUNCH_WORKDIR = _RUNTIME.launch_workdir
