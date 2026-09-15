"""两套主题的配色常量与 QSS 样式表。

用 string.Template 而非 f-string：QSS 里大量出现花括号，
f-string 需要把每个 { 写成 {{，可读性会崩掉。
"""
from __future__ import annotations

from string import Template

THEMES = ("dark", "light")

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#1e1f22",
        "card": "#2b2d31",
        "border": "#3a3d43",
        "text": "#e6e6e6",
        "text_dim": "#9aa0a6",
        "accent": "#4c8dff",
        "accent_hover": "#5f9bff",
        "ok": "#3ddc84",
        "warn": "#ffa726",
        "idle": "#6b7076",
        "danger": "#ff5c5c",
    },
    "light": {
        "bg": "#f5f6f8",
        "card": "#ffffff",
        "border": "#dfe1e5",
        "text": "#1f2328",
        "text_dim": "#6b7076",
        "accent": "#2f6feb",
        "accent_hover": "#1f5fd8",
        "ok": "#1a9e5c",
        "warn": "#e08a00",
        "idle": "#9aa0a6",
        "danger": "#d64545",
    },
}

_QSS = Template("""
QWidget {
    background-color: $bg;
    color: $text;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}

#Card {
    background-color: $card;
    border: 1px solid $border;
    border-radius: 12px;
}

#TitleText {
    font-size: 15px;
    font-weight: 600;
}

#SectionTitle {
    color: $text_dim;
    font-size: 12px;
    font-weight: 600;
    padding-top: 8px;
}

#StatusText {
    font-size: 15px;
    font-weight: 600;
}

#StatusDetail {
    color: $text_dim;
    font-size: 12px;
}

#StatusDot {
    font-size: 14px;
}

QPushButton {
    background-color: $card;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 8px 14px;
}

QPushButton:hover {
    border-color: $accent;
}

QPushButton:pressed {
    background-color: $border;
}

QPushButton:disabled {
    color: $text_dim;
    border-color: $border;
}

QPushButton#Primary {
    background-color: $accent;
    border: none;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#Primary:hover {
    background-color: $accent_hover;
}

QPushButton#Danger {
    background-color: transparent;
    border: 1px solid $danger;
    color: $danger;
    font-size: 15px;
    font-weight: 600;
    padding: 12px;
}

QPushButton#Danger:hover {
    background-color: $danger;
    color: #ffffff;
}

QPushButton#Danger:disabled {
    border-color: $border;
    color: $text_dim;
}

QPushButton#IconButton {
    background-color: transparent;
    border: none;
    padding: 4px 8px;
    font-size: 15px;
}

QPushButton#IconButton:hover {
    background-color: $border;
    border-radius: 6px;
}

QTimeEdit, QSpinBox, QComboBox {
    background-color: $card;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 10px;
}

QTimeEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: $accent;
}

QCheckBox, QRadioButton {
    spacing: 6px;
}

#Hint {
    color: $text_dim;
    font-size: 12px;
}

#CountdownText {
    font-size: 32px;
    font-weight: 700;
}

#CountdownCaption {
    color: $text_dim;
    font-size: 13px;
}
""")


def palette(theme: str) -> dict[str, str]:
    return PALETTES.get(theme, PALETTES["dark"])


def color(theme: str, key: str) -> str:
    colors = palette(theme)
    return colors.get(key, colors["text"])


def stylesheet(theme: str) -> str:
    return _QSS.substitute(palette(theme))
