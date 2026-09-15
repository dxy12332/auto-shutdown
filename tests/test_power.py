import logging

import pytest

from app.power import (
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
    caplog.set_level(logging.INFO)
    calls = []
    executor = PowerExecutor(dry_run=True, runner=lambda argv: calls.append(argv) or 0)

    assert executor.run(build_arm_command("shutdown", 60, force=False)) is True

    assert calls == []
    assert "[DRY-RUN]" in caplog.text
    assert "shutdown.exe /s /t 60" in caplog.text


def test_dry_run_abort_is_logged_not_executed(caplog):
    caplog.set_level(logging.INFO)
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


def test_live_mode_logs_successful_command(caplog):
    """真实模式成功时也必须留痕，否则日志无法证明命令真的下达了。"""
    caplog.set_level(logging.INFO)
    executor = PowerExecutor(dry_run=False, runner=lambda argv: 0)

    assert executor.run(build_abort_command()) is True

    assert "已执行" in caplog.text
    assert "shutdown.exe /a" in caplog.text


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
