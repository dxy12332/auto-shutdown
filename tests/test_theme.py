import pytest

from app.theme import THEMES, color, palette, stylesheet

REQUIRED_KEYS = {
    "bg", "card", "border", "text", "text_dim",
    "accent", "accent_hover", "ok", "warn", "idle", "danger",
}


@pytest.mark.parametrize("theme", THEMES)
def test_every_theme_defines_all_keys(theme):
    assert REQUIRED_KEYS <= set(palette(theme))


@pytest.mark.parametrize("theme", THEMES)
def test_every_value_is_a_hex_color(theme):
    for key, value in palette(theme).items():
        assert value.startswith("#"), f"{theme}.{key} 不是十六进制颜色"
        assert len(value) == 7, f"{theme}.{key} 长度不对: {value}"


def test_unknown_theme_falls_back_to_dark():
    assert palette("neon") == palette("dark")


def test_dark_and_light_actually_differ():
    assert palette("dark")["bg"] != palette("light")["bg"]


def test_color_helper_returns_single_value():
    assert color("dark", "accent") == palette("dark")["accent"]


def test_color_helper_unknown_key_falls_back_to_text():
    assert color("dark", "no_such_key") == palette("dark")["text"]


@pytest.mark.parametrize("theme", THEMES)
def test_stylesheet_has_no_unsubstituted_placeholders(theme):
    qss = stylesheet(theme)
    assert "$" not in qss, "QSS 里有未替换的模板变量"
    assert "#Card" in qss


def test_stylesheet_differs_between_themes():
    assert stylesheet("dark") != stylesheet("light")
