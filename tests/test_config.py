import json
from pathlib import Path

from app.config import (
    GRACE_MAX,
    GRACE_MIN,
    ConfigStore,
    Daily,
    OneOff,
)


def test_load_missing_file_returns_defaults(tmp_path: Path):
    cfg = ConfigStore(tmp_path / "config.json").load()
    assert cfg.action == "shutdown"
    assert cfg.force is False
    assert cfg.grace_seconds == 60
    assert cfg.autostart is True
    assert cfg.theme == "dark"
    assert cfg.dry_run is False
    assert cfg.daily == Daily(enabled=False, time="23:30")
    assert cfg.oneoff == OneOff(enabled=False, target="", label="")


def test_save_then_load_roundtrip(tmp_path: Path):
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    cfg = store.load()
    cfg.action = "restart"
    cfg.grace_seconds = 120
    cfg.theme = "light"
    cfg.daily = Daily(enabled=True, time="22:15")
    store.save(cfg)

    assert ConfigStore(path).load() == cfg


def test_invalid_action_falls_back_to_default(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"action": "explode"}), encoding="utf-8")
    assert ConfigStore(path).load().action == "shutdown"


def test_grace_seconds_is_clamped_into_range(tmp_path: Path):
    path = tmp_path / "config.json"

    path.write_text(json.dumps({"grace_seconds": 5}), encoding="utf-8")
    assert ConfigStore(path).load().grace_seconds == GRACE_MIN

    path.write_text(json.dumps({"grace_seconds": 9999}), encoding="utf-8")
    assert ConfigStore(path).load().grace_seconds == GRACE_MAX


def test_non_numeric_grace_falls_back_to_default(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"grace_seconds": "soon"}), encoding="utf-8")
    assert ConfigStore(path).load().grace_seconds == 60


def test_bool_is_not_accepted_as_int(tmp_path: Path):
    """Python 里 bool 是 int 的子类，必须显式挡住。"""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"grace_seconds": True}), encoding="utf-8")
    assert ConfigStore(path).load().grace_seconds == 60


def test_corrupt_file_is_backed_up_and_defaults_returned(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("{not json at all", encoding="utf-8")

    cfg = ConfigStore(path).load()

    assert cfg.action == "shutdown"
    assert len(list(tmp_path.glob("config.json.corrupt-*"))) == 1
    assert not path.exists()


def test_unknown_fields_are_ignored(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"action": "sleep", "nonsense": 1}), encoding="utf-8")
    assert ConfigStore(path).load().action == "sleep"


def test_invalid_time_falls_back_to_default(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"daily": {"enabled": True, "time": "25:99"}}), encoding="utf-8")
    assert ConfigStore(path).load().daily.time == "23:30"


def test_time_is_normalized_to_two_digit_form(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"daily": {"enabled": True, "time": "7:5"}}), encoding="utf-8")
    assert ConfigStore(path).load().daily.time == "07:05"


def test_save_leaves_no_tmp_file_behind(tmp_path: Path):
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    store.save(store.load())
    assert path.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_invalid_theme_falls_back_to_dark(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"theme": "neon"}), encoding="utf-8")
    assert ConfigStore(path).load().theme == "dark"
