"""「立即取消关机」必须同时清掉一次性与每天重复两种排定。

回归测试：曾经只清了 oneoff，导致设了「每天重复」时点取消毫无反应——
界面状态不变，因为那条每日规则从未被取消。
"""
from datetime import datetime, timedelta

import pytest

from app.config import ConfigStore


@pytest.fixture
def store(tmp_path):
    return ConfigStore(tmp_path / "config.json")


def make_controller(qapp, store):
    import main

    # dry_run 保证测试绝不会真的调用 shutdown.exe
    return main.AppController(qapp, store, force_dry_run=True)


def teardown_controller(controller):
    controller.scheduler.stop()
    controller.tray.hide()


def test_cancel_clears_both_oneoff_and_daily(qapp, store):
    cfg = store.load()
    cfg.daily.enabled = True
    cfg.daily.time = "23:59"
    cfg.oneoff.enabled = True
    cfg.oneoff.target = (datetime.now() + timedelta(hours=1)).isoformat()
    cfg.oneoff.label = "一小时后"
    store.save(cfg)

    controller = make_controller(qapp, store)
    # 前置条件：确实有排定，否则这个测试证明不了任何事
    assert controller.scheduler.next_trigger() is not None

    controller.cancel_current()

    after = store.load()
    assert after.oneoff.enabled is False
    assert after.daily.enabled is False
    assert controller.scheduler.next_trigger() is None, "取消后不该再有任何排定"
    teardown_controller(controller)


def test_cancel_when_only_daily_enabled(qapp, store):
    """这正是用户实际遇到的情况：只设了「每天重复」。"""
    cfg = store.load()
    cfg.daily.enabled = True
    cfg.daily.time = "23:59"
    store.save(cfg)

    controller = make_controller(qapp, store)
    assert controller.scheduler.next_trigger() is not None

    controller.cancel_current()

    assert store.load().daily.enabled is False
    assert controller.scheduler.next_trigger() is None
    teardown_controller(controller)


def test_cancel_is_idempotent(qapp, store):
    """连点多次不该出错，也不该留下任何排定。"""
    cfg = store.load()
    cfg.daily.enabled = True
    store.save(cfg)

    controller = make_controller(qapp, store)
    for _ in range(3):
        controller.cancel_current()

    assert controller.scheduler.next_trigger() is None
    teardown_controller(controller)


def test_cancel_unchecks_daily_checkbox(qapp, store):
    """只改配置不够：界面上的「每天」复选框也必须回到未勾选状态。

    否则配置确实取消了，但用户看到复选框还勾着，仍然会认为「点了没反应」。
    """
    cfg = store.load()
    cfg.daily.enabled = True
    cfg.daily.time = "23:59"
    store.save(cfg)

    controller = make_controller(qapp, store)
    assert controller.window._daily_check.isChecked() is True

    controller.cancel_current()

    assert controller.window._daily_check.isChecked() is False
    teardown_controller(controller)
