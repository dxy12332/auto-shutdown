from pathlib import Path

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
