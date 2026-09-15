"""集中定义运行期路径，避免各模块各自拼路径。"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
LOG_PATH = PROJECT_ROOT / "run.log"
ICON_PATH = PROJECT_ROOT / "assets" / "icon.ico"
ASSETS_DIR = PROJECT_ROOT / "assets"
LAUNCH_BAT = PROJECT_ROOT / "启动.bat"
