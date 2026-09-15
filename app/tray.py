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

        cancel_action = QAction("取消关机", menu)
        cancel_action.triggered.connect(on_cancel)
        menu.addAction(cancel_action)

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
        # 托盘菜单由系统绘制，这里只调整菜单文字配色
        self._menu.setStyleSheet("" if theme == "dark" else "QMenu { color: #1f2328; }")
