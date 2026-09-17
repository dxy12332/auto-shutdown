# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件 exe。

用法：
    pyinstaller build.spec --noconfirm

产物：dist/定时关机.exe

设计说明：
- console=False —— GUI 应用，不要弹控制台窗口。
- upx=False —— UPX 压缩会显著提高被杀毒软件误报的概率，不值得为省几兆冒这个险。
- datas 里带上图标：打包后 app/paths.py 从 sys._MEIPASS 读它。
"""
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH)

# 只排除确定用不到的大模块。
# 刻意不排除 QtNetwork / QtOpenGL / QtSvg —— Qt 内部可能间接依赖它们，
# 排错成本远高于省下的那点体积。
EXCLUDES = [
    # Web 引擎（最大的一块，动辄上百兆）
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    # QML / Quick 全家桶
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQml",
    # 3D
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    # 音视频
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    # 图表与数据可视化
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    # 数据库、文档、设计器
    "PySide6.QtSql",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtDesigner",
    "PySide6.QtUiTools",
    "PySide6.QtHelp",
    # 测试与状态机
    "PySide6.QtTest",
    "PySide6.QtStateMachine",
    "PySide6.QtScxml",
    # 硬件相关
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtSerialPort",
    "PySide6.QtSensors",
    "PySide6.QtRemoteObjects",
    # 标准库里确定用不到的
    "tkinter",
    "pydoc",
    "doctest",
    "setuptools",
    "pip",
]

a = Analysis(
    ["main.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[("assets/icon.ico", "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    # 用英文名：GitHub 的 Release 附件名不接受非 ASCII 字符，
    # 传中文名会被静默替换成 default.exe。本地就产出正确名字可省掉改名。
    name="AutoShutdown-v1.0.1",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
)
