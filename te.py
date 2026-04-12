import sys
from PyQt6.QtGui import (
    QGuiApplication, QPainter, QColor,
    QSurfaceFormat, QBackingStore, QRegion
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QWindow


class TransparentWindow(QWindow):
    def __init__(self):
        super().__init__()

        fmt = QSurfaceFormat()
        fmt.setAlphaBufferSize(8)
        self.setFormat(fmt)

        self.setFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.resize(400, 400)

        self.backingStore = QBackingStore(self)

        self.show()

    def exposeEvent(self, event):
        if self.isExposed():
            self.render()

    def resizeEvent(self, event):
        self.backingStore.resize(self.size())

    def render(self):
        if not self.isExposed():
            return

        rect = QRect(0, 0, self.width(), self.height())
        region = QRegion(rect)  # ✅ FIX

        self.backingStore.beginPaint(region)

        device = self.backingStore.paintDevice()
        painter = QPainter(device)

        painter.fillRect(rect, Qt.GlobalColor.transparent)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(255, 0, 0, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(50, 50, 300, 300)

        painter.end()

        self.backingStore.endPaint()
        self.backingStore.flush(region)


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)

    w = TransparentWindow()

    sys.exit(app.exec())