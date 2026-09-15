"""主窗口：状态卡片、快速定时、指定时刻、每天重复、动作与选项。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from PySide6.QtCore import QTime, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from app.autostart import Autostart
from app.config import GRACE_MAX, GRACE_MIN, ConfigStore
from app.formatting import format_remaining, format_trigger_time
from app.paths import ICON_PATH, LAUNCH_BAT, PROJECT_ROOT
from app.power import PowerExecutor, supports_system_abort
from app.scheduler import Scheduler
from app.theme import color, stylesheet

logger = logging.getLogger(__name__)

ACTION_OPTIONS = (
    ("shutdown", "关机"),
    ("restart", "重启"),
    ("sleep", "睡眠"),
    ("hibernate", "休眠"),
    ("logoff", "注销"),
)

ACTION_LABELS_CN = {value: label for value, label in ACTION_OPTIONS}

QUICK_MINUTES = ((30, "30 分钟"), (60, "1 小时"), (120, "2 小时"))

#: 自定义分钟的合法范围：1 分钟到 24 小时
MIN_CUSTOM_MINUTES = 1
MAX_CUSTOM_MINUTES = 1440


class MainWindow(QMainWindow):
    theme_changed = Signal(str)
    schedule_changed = Signal()
    cancel_requested = Signal()

    def __init__(
        self,
        store: ConfigStore,
        executor: PowerExecutor,
        scheduler: Scheduler,
        autostart: Autostart,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._store = store
        self._executor = executor
        self._scheduler = scheduler
        self._autostart = autostart
        self._theme = "dark"
        self._counting = False

        self.setWindowTitle("定时关机")
        self.setMinimumWidth(480)
        self._build_ui()
        self._load_from_config()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self.refresh_status)
        self._refresh_timer.start()
        self.refresh_status()

    # ---------- 构建界面 ----------

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)

        layout.addLayout(self._build_title_bar())
        layout.addWidget(self._build_status_card())
        layout.addWidget(self._section("快速定时"))
        layout.addLayout(self._build_quick_row())
        layout.addWidget(self._section("指定时刻"))
        layout.addLayout(self._build_oneoff_row())
        layout.addWidget(self._section("每天重复"))
        layout.addLayout(self._build_daily_row())
        layout.addWidget(self._section("到点执行"))
        layout.addLayout(self._build_action_row())
        layout.addLayout(self._build_options_row())
        layout.addStretch(1)
        layout.addWidget(self._build_cancel_button())

    def _build_title_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        title = QLabel("⏻  定时关机")
        title.setObjectName("TitleText")
        row.addWidget(title)
        row.addStretch(1)

        self._theme_button = QPushButton("☾")
        self._theme_button.setObjectName("IconButton")
        self._theme_button.setToolTip("切换暗色 / 亮色主题")
        self._theme_button.clicked.connect(self._toggle_theme)
        row.addWidget(self._theme_button)
        return row

    def _build_status_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(16, 14, 16, 14)
        inner.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        self._status_dot = QLabel("●")
        self._status_dot.setObjectName("StatusDot")
        self._status_text = QLabel("未排定")
        self._status_text.setObjectName("StatusText")
        top.addWidget(self._status_dot)
        top.addWidget(self._status_text)
        top.addStretch(1)

        self._status_detail = QLabel("当前无定时任务")
        self._status_detail.setObjectName("StatusDetail")

        inner.addLayout(top)
        inner.addWidget(self._status_detail)
        return card

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    def _build_quick_row(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(8)

        presets = QHBoxLayout()
        presets.setSpacing(8)
        for minutes, label in QUICK_MINUTES:
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, m=minutes: self._apply_quick(m))
            presets.addWidget(button)
        column.addLayout(presets)

        custom = QHBoxLayout()
        custom.setSpacing(8)
        custom.addWidget(QLabel("自定义"))
        self._custom_minutes = QSpinBox()
        self._custom_minutes.setRange(MIN_CUSTOM_MINUTES, MAX_CUSTOM_MINUTES)
        self._custom_minutes.setValue(15)
        self._custom_minutes.setSuffix(" 分钟")
        custom.addWidget(self._custom_minutes)

        custom_set = QPushButton("设定")
        custom_set.setObjectName("Primary")
        custom_set.clicked.connect(lambda: self._apply_quick(self._custom_minutes.value()))
        custom.addWidget(custom_set)
        custom.addStretch(1)
        column.addLayout(custom)

        return column

    def _build_oneoff_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._day_combo = QComboBox()
        self._day_combo.addItems(["今天", "明天"])
        row.addWidget(self._day_combo)

        self._oneoff_time = QTimeEdit()
        self._oneoff_time.setDisplayFormat("HH:mm")
        self._oneoff_time.setTime(QTime(23, 30))
        row.addWidget(self._oneoff_time, 1)

        set_button = QPushButton("设定")
        set_button.setObjectName("Primary")
        set_button.clicked.connect(self._apply_oneoff)
        row.addWidget(set_button)
        return row

    def _build_daily_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._daily_check = QCheckBox("每天")
        self._daily_check.toggled.connect(self._apply_daily)
        row.addWidget(self._daily_check)

        self._daily_time = QTimeEdit()
        self._daily_time.setDisplayFormat("HH:mm")
        self._daily_time.setTime(QTime(23, 30))
        self._daily_time.timeChanged.connect(self._apply_daily)
        row.addWidget(self._daily_time, 1)

        hint = QLabel("开机自启后长期生效")
        hint.setObjectName("Hint")
        row.addWidget(hint)
        return row

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self._action_group = QButtonGroup(self)
        for index, (value, label) in enumerate(ACTION_OPTIONS):
            radio = QRadioButton(label)
            radio.setProperty("action_value", value)
            self._action_group.addButton(radio, index)
            row.addWidget(radio)
        row.addStretch(1)

        self._action_group.buttonClicked.connect(self._apply_action)
        return row

    def _build_options_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        row.addWidget(QLabel("确认等待"))
        self._grace_spin = QSpinBox()
        self._grace_spin.setRange(GRACE_MIN, GRACE_MAX)
        self._grace_spin.setSuffix(" 秒")
        self._grace_spin.valueChanged.connect(self._apply_grace)
        row.addWidget(self._grace_spin)

        self._force_check = QCheckBox("强制结束未响应程序")
        self._force_check.toggled.connect(self._apply_force)
        row.addWidget(self._force_check)

        row.addStretch(1)

        self._autostart_check = QCheckBox("开机自启")
        self._autostart_check.toggled.connect(self._apply_autostart)
        row.addWidget(self._autostart_check)
        return row

    def _build_cancel_button(self) -> QPushButton:
        self._cancel_button = QPushButton("立即取消关机")
        self._cancel_button.setObjectName("Danger")
        # 只发信号，真正的取消逻辑由 main.py 的 AppController 接管
        self._cancel_button.clicked.connect(self.cancel_requested.emit)
        return self._cancel_button

    # ---------- 配置 <-> 界面 ----------

    def _load_from_config(self) -> None:
        cfg = self._store.load()

        for button in self._action_group.buttons():
            if button.property("action_value") == cfg.action:
                button.setChecked(True)
                break

        self._grace_spin.blockSignals(True)
        self._grace_spin.setValue(cfg.grace_seconds)
        self._grace_spin.blockSignals(False)

        self._force_check.blockSignals(True)
        self._force_check.setChecked(cfg.force)
        self._force_check.blockSignals(False)

        # 载入时屏蔽信号，避免触发写盘
        self._daily_check.blockSignals(True)
        self._daily_check.setChecked(cfg.daily.enabled)
        self._daily_check.blockSignals(False)

        self._daily_time.blockSignals(True)
        self._daily_time.setTime(QTime.fromString(cfg.daily.time, "HH:mm"))
        self._daily_time.blockSignals(False)

        self._autostart_check.blockSignals(True)
        self._autostart_check.setChecked(self._autostart.is_enabled())
        self._autostart_check.blockSignals(False)

        self.apply_theme(cfg.theme)

    def current_theme(self) -> str:
        return self._theme

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        self.setStyleSheet(stylesheet(theme))
        self._theme_button.setText("☀" if theme == "dark" else "☾")
        self.theme_changed.emit(theme)

    def _toggle_theme(self) -> None:
        new_theme = "light" if self._theme == "dark" else "dark"
        cfg = self._store.load()
        cfg.theme = new_theme
        self._store.save(cfg)
        self.apply_theme(new_theme)

    def _apply_quick(self, minutes: int) -> None:
        target = datetime.now() + timedelta(minutes=minutes)
        self._set_oneoff(target, f"{minutes} 分钟后")

    def _apply_oneoff(self) -> None:
        qt_time = self._oneoff_time.time()
        now = datetime.now()
        target = now.replace(
            hour=qt_time.hour(),
            minute=qt_time.minute(),
            second=0,
            microsecond=0,
        )
        if self._day_combo.currentIndex() == 1 or target <= now:
            target += timedelta(days=1)
        label = "今天" if target.date() == now.date() else "明天"
        self._set_oneoff(target, f"{label} {target.strftime('%H:%M')}")

    def _set_oneoff(self, target: datetime, label: str) -> None:
        cfg = self._store.load()

        # 若上一个排程已经下发给系统，必须先撤销：已有排程时再次 shutdown 会返回 1190
        if cfg.oneoff.enabled and supports_system_abort(cfg.action):
            self._executor.abort()

        cfg.oneoff.enabled = True
        cfg.oneoff.target = target.isoformat()
        cfg.oneoff.label = label
        self._store.save(cfg)
        self._scheduler.refresh()
        self.schedule_changed.emit()
        self.refresh_status()
        logger.info("已排定一次性%s: %s", label, target)

    def _apply_daily(self) -> None:
        cfg = self._store.load()
        cfg.daily.enabled = self._daily_check.isChecked()
        cfg.daily.time = self._daily_time.time().toString("HH:mm")
        self._store.save(cfg)
        self._scheduler.refresh()
        self.schedule_changed.emit()
        self.refresh_status()

    def _apply_action(self, button) -> None:
        cfg = self._store.load()
        cfg.action = button.property("action_value")
        self._store.save(cfg)
        logger.info("到点动作改为: %s", cfg.action)
        self.refresh_status()

    def _apply_grace(self, value: int) -> None:
        cfg = self._store.load()
        cfg.grace_seconds = value
        self._store.save(cfg)

    def _apply_force(self, checked: bool) -> None:
        cfg = self._store.load()
        cfg.force = checked
        self._store.save(cfg)

    def _apply_autostart(self, checked: bool) -> None:
        cfg = self._store.load()
        cfg.autostart = checked
        self._store.save(cfg)
        self._autostart.sync(
            checked,
            target=LAUNCH_BAT,
            workdir=PROJECT_ROOT,
            icon=ICON_PATH,
        )

    # ---------- 状态刷新 ----------

    def refresh_status(self) -> None:
        cfg = self._store.load()
        now = datetime.now()

        if self._counting:
            self._status_dot.setStyleSheet(f"color: {color(self._theme, 'warn')};")
            self._status_text.setText("即将执行")
            self._status_detail.setText(f"{cfg.grace_seconds} 秒后执行，倒计时进行中")
            self._cancel_button.setEnabled(True)
            return

        trigger = self._scheduler.next_trigger(now)

        if trigger is None:
            self._status_dot.setStyleSheet(f"color: {color(self._theme, 'idle')};")
            self._status_text.setText("未排定")
            self._status_detail.setText("当前无定时任务")
            self._cancel_button.setEnabled(False)
            return

        remaining = int((trigger.at - now).total_seconds())
        self._status_dot.setStyleSheet(f"color: {color(self._theme, 'ok')};")
        self._status_text.setText("已排定" + ACTION_LABELS_CN.get(cfg.action, "关机"))
        self._status_detail.setText(
            f"{format_trigger_time(trigger.at, now)} · 剩余 {format_remaining(remaining)}"
        )
        self._cancel_button.setEnabled(True)

    def set_counting(self, counting: bool) -> None:
        self._counting = counting
        self.refresh_status()

    # ---------- 窗口行为 ----------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        """关闭窗口只是隐藏，应用继续在托盘里跑定时。"""
        event.ignore()
        self.hide()
