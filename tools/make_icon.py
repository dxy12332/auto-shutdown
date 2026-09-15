"""用 QPainter 画出电源符号图标，并写成多尺寸 .ico。

Qt 的 QPixmap.save 一次只能存一种尺寸，所以这里手工拼 ICO 容器：
每个条目塞一张 PNG（ICO 自 Vista 起支持内嵌 PNG）。
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.paths import ICON_PATH  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)
BG_COLOR = "#2f6feb"
FG_COLOR = "#ffffff"


def render(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 圆角底
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(BG_COLOR))
    radius = size * 0.22
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    # 电源符号：开口圆环 + 顶部竖线
    pen = QPen(QColor(FG_COLOR))
    pen.setWidthF(max(1.5, size * 0.09))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    inset = size * 0.32
    ring = QRectF(inset, inset * 1.15, size - 2 * inset, size - 2 * inset)
    # 从 60° 画到 300°，留出顶部缺口
    painter.drawArc(ring, 60 * 16, 240 * 16)

    painter.drawLine(
        int(size / 2),
        int(size * 0.16),
        int(size / 2),
        int(size * 0.46),
    )
    painter.end()
    return pixmap


def png_bytes(pixmap: QPixmap) -> bytes:
    # QByteArray 必须具名持有：写成 QBuffer(QByteArray()) 会让临时对象
    # 被立刻回收，QBuffer 拿到悬空引用，随后段错误。
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(byte_array)


def write_ico(path: Path, pixmaps: list[QPixmap]) -> None:
    count = len(pixmaps)
    header = struct.pack("<HHH", 0, 1, count)
    entries = b""
    payload = b""
    offset = 6 + 16 * count

    for pixmap in pixmaps:
        data = png_bytes(pixmap)
        width = pixmap.width() if pixmap.width() < 256 else 0
        height = pixmap.height() if pixmap.height() < 256 else 0
        entries += struct.pack(
            "<BBBBHHII", width, height, 0, 0, 1, 32, len(data), offset
        )
        offset += len(data)
        payload += data

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + payload)


def main() -> int:
    # QPixmap 需要一个存活的 QGuiApplication，不能提前回收
    app = QApplication(sys.argv)  # noqa: F841

    pixmaps = [render(size) for size in SIZES]
    write_ico(ICON_PATH, pixmaps)
    print(f"已生成 {ICON_PATH}（{len(SIZES)} 种尺寸）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
