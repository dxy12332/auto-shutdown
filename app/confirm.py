"""关机确认窗：置顶居中，大号倒计时数字 + 环形进度。

点右上角 ✕ 等同于「取消」——安全优先，宁可漏关也不误关。
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.theme import color, stylesheet

ACTION_LABELS = {
    "shutdown": ("关机", "立即关机"),
    "restart": ("重启", "立即重启"),
    "sleep": ("睡眠", "立即睡眠"),
    "hibernate": ("休眠", "立即休眠"),
    "logoff": ("注销", "立即注销"),
}


class RingProgress(QWidget):
    """环形进度 + 中央文字。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(160, 160)
        self._ratio = 1.0
        self._text = ""
        self._ring_color = QColor("#4c8dff")
        self._track_color = QColor("#3a3d43")

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self.update()

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def set_ring_color(self, html: str) -> None:
        self._ring_color = QColor(html)
        self.update()

    def set_track_color(self, html: str) -> None:
        self._track_color = QColor(html)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height()) - 16
        rect = QRectF(
            (self.width() - side) / 2,
            (self.height() - side) / 2,
            side,
            side,
        )
        pen_width = max(8, side // 14)

        track_pen = QPen(self._track_color)
        track_pen.setWidth(pen_width)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        ring_pen = QPen(self._ring_color)
        ring_pen.setWidth(pen_width)
        ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(ring_pen)
        # 从 12 点方向顺时针减少
        painter.drawArc(rect, 90 * 16, int(-360 * 16 * self._ratio))

        font = QFont()
        font.setPointSize(max(14, side // 6))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class ConfirmDialog(QDialog):
    RESULT_CANCEL = "cancel"
    RESULT_NOW = "now"
    RESULT_TIMEOUT = "timeout"

    def __init__(
        self,
        action: str,
        grace_seconds: int,
        theme: str = "dark",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._action = action
        self._total = max(1, int(grace_seconds))
        self._remaining = self._total
        self._theme = theme
        self._result_value = self.RESULT_TIMEOUT

        verb, now_label = ACTION_LABELS.get(action, ("关机", "立即执行"))
        self._verb = verb

        self.setWindowTitle(f"{verb}提醒")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(True)
        self.resize(360, 420)
        self.setStyleSheet(stylesheet(theme))

        self._ring = RingProgress(self)
        self._ring.set_ring_color(color(theme, "accent"))
        self._ring.set_track_color(color(theme, "border"))

        self._caption = QLabel(f"电脑将在 {self._remaining} 秒后{verb}", self)
        self._caption.setObjectName("CountdownCaption")
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._cancel_button = QPushButton("取消" + verb, self)
        self._cancel_button.setObjectName("Primary")
        self._cancel_button.clicked.connect(self.cancel)

        self._now_button = QPushButton(now_label, self)
        self._now_button.clicked.connect(self.confirm_now)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addWidget(self._cancel_button)
        buttons.addWidget(self._now_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)
        layout.addStretch(1)
        layout.addWidget(self._ring, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._caption)
        layout.addStretch(1)
        layout.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._update_display()

        if parent is None:
            self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

    def _update_display(self) -> None:
        minutes, seconds = divmod(self._remaining, 60)
        self._ring.set_text(f"{minutes:02d}:{seconds:02d}")
        self._ring.set_ratio(self._remaining / self._total)
        self._caption.setText(f"电脑将在 {self._remaining} 秒后{self._verb}")

        # 最后 10 秒转成警示色
        if self._remaining <= 10:
            self._ring.set_ring_color(color(self._theme, "danger"))
        else:
            self._ring.set_ring_color(color(self._theme, "accent"))

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self._result_value = self.RESULT_TIMEOUT
            self.done(0)
            return
        self._update_display()

    def cancel(self) -> None:
        """公开方法：窗口上的按钮与外部（托盘菜单）都可以调。"""
        self._timer.stop()
        self._result_value = self.RESULT_CANCEL
        self.done(0)

    def confirm_now(self) -> None:
        self._timer.stop()
        self._result_value = self.RESULT_NOW
        self.done(0)

    def reject(self) -> None:
        """点 ✕ 或按 Esc 都视为取消，不视为超时。"""
        self._timer.stop()
        self._result_value = self.RESULT_CANCEL
        super().reject()

    def exec_modal(self) -> str:
        self._timer.start()
        self.exec()
        self._timer.stop()
        return self._result_value
