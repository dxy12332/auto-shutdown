"""路径解析测试。

resolve_paths 是纯函数，所有环境因素都从参数传入，
因此可以完整测试打包与源码两种运行环境，而不必真的打包。
"""
from pathlib import Path

from app.paths import APP_DIR_NAME, resolve_paths

PROJECT = Path("D:/proj")
EXE = Path("E:/Share/定时关机.exe")
APPDATA = Path("C:/Users/someone/AppData/Roaming")
MEIPASS = Path("C:/Temp/_MEI123456")


def source_paths():
    return resolve_paths(
        frozen=False,
        project_root=PROJECT,
        executable=Path("C:/Python312/python.exe"),
        appdata=APPDATA,
        meipass=None,
    )


def frozen_paths(meipass=MEIPASS):
    return resolve_paths(
        frozen=True,
        project_root=PROJECT,
        executable=EXE,
        appdata=APPDATA,
        meipass=meipass,
    )


def test_source_mode_keeps_data_in_project_dir():
    r = source_paths()
    assert r.data_dir == PROJECT
    assert r.config_path == PROJECT / "config.json"
    assert r.log_path == PROJECT / "run.log"


def test_source_mode_launches_the_bat():
    r = source_paths()
    assert r.launch_target == PROJECT / "启动.bat"
    assert r.launch_workdir == PROJECT


def test_source_mode_reads_resources_from_project_dir():
    r = source_paths()
    assert r.resource_dir == PROJECT
    assert r.icon_path == PROJECT / "assets" / "icon.ico"


def test_frozen_mode_puts_data_under_appdata():
    r = frozen_paths()
    assert r.data_dir == APPDATA / APP_DIR_NAME
    assert r.config_path == APPDATA / APP_DIR_NAME / "config.json"
    assert r.log_path == APPDATA / APP_DIR_NAME / "run.log"


def test_frozen_mode_launches_the_exe_itself():
    r = frozen_paths()
    assert r.launch_target == EXE
    assert r.launch_workdir == EXE.parent


def test_frozen_mode_reads_resources_from_meipass():
    r = frozen_paths()
    assert r.resource_dir == MEIPASS
    assert r.icon_path == MEIPASS / "assets" / "icon.ico"


def test_frozen_mode_without_meipass_falls_back_to_exe_dir():
    """onedir 模式没有 _MEIPASS，资源就在 exe 旁边。"""
    r = frozen_paths(meipass=None)
    assert r.resource_dir == EXE.parent


def test_frozen_mode_ignores_project_dir_entirely():
    """打包后不该再碰开发机的项目目录。"""
    r = frozen_paths()
    assert PROJECT not in r.data_dir.parents
    assert PROJECT not in r.resource_dir.parents


def test_the_two_modes_never_share_a_config_file():
    """整个改造的意义所在：两种运行环境的配置必须完全隔离。"""
    assert source_paths().config_path != frozen_paths().config_path
    assert source_paths().data_dir != frozen_paths().data_dir


def test_app_dir_name_is_stable():
    assert APP_DIR_NAME == "AutoShutdownPro"
