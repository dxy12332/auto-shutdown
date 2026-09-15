"""应用入口：单实例锁、日志、部件组装、触发流程。"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

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
    # Windows 控制台默认是 GBK，中文日志会乱码。日志文件本身始终用 UTF-8。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="定时关机")
    parser.add_argument("--dry-run", action="store_true", help="只记录不执行，调试用")
    return parser.parse_known_args(argv)


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
        elif result == ConfirmDialog.RESULT_NOW:
            # 已有排程时再次 shutdown 会返回 1190，必须先撤销
            if supports_system_abort(action):
                self.executor.abort()
            self.executor.execute_now(action, force)
            logger.info("用户要求立即执行 %s", action)
        else:
            # 超时：关机/重启的系统排程继续跑；其余动作由应用补上
            if not supports_system_abort(action):
                self.executor.execute_now(action, force)
                logger.info("超时，执行 %s", action)
            else:
                logger.info("超时，交由系统排程执行 %s", action)

        # 无论走哪条分支都必须重排下一次：一次性定时已被消耗，
        # 而「每天重复」靠这一步才会滚动到明天的同一时刻。
        self.scheduler.refresh()
        self.window.refresh_status()

    def cancel_current(self) -> None:
        """主界面/托盘上的「取消关机」。"""
        if self._confirm_dialog is not None:
            self._confirm_dialog.cancel()
            return

        cfg = self.store.load()

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


def main() -> int:
    setup_logging()
    args, qt_argv = parse_args(sys.argv[1:])

    app = QApplication([sys.argv[0], *qt_argv])
    app.setQuitOnLastWindowClosed(False)  # 关窗口不退出，驻留托盘

    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    shared = QSharedMemory(SHARED_MEMORY_KEY)
    if not shared.create(1):
        logger.warning("应用已在运行，本次启动退出")
        QMessageBox.information(None, "定时关机", "应用已经在运行了，请查看系统托盘。")
        return 0

    controller = AppController(app, ConfigStore(CONFIG_PATH), force_dry_run=args.dry_run)
    controller.window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
