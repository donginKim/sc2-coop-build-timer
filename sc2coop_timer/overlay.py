"""반투명·항상 위·클릭 통과 오버레이 창."""

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .overlay_model import View

WIDTH = 280
MARGIN = 16
COLORS = {
    "normal": "#e6e6e6",
    "due": "#7CFC00",
    "wave": "#ff6b6b",
    "objective": "#ffd166",
    "done": "#8a8a8a",
}


class Overlay(QWidget):
    def __init__(self, opacity: float):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # macOS는 Tool 창을 앱 비활성 시 숨긴다 — Mac 데모용 (Windows에는 영향 없음)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setWindowOpacity(opacity)
        self.setFixedWidth(WIDTH)

        self._label = QLabel(self)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            "QLabel { background: rgba(0, 0, 0, 170); color: #e6e6e6;"
            " padding: 8px; border-radius: 6px; font-size: 13px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def render(self, view: View) -> None:
        badge = f" <span style='color:#ffd166'>{escape(view.badge)}</span>" if view.badge else ""
        head = (
            "<table width='100%'><tr>"
            f"<td><b>{escape(view.title)}</b>{badge}</td>"
            f"<td align='right'>[{view.clock}]</td>"
            "</tr></table>"
        )
        rows = []
        for row in view.rows:
            color = COLORS.get(row.style, COLORS["normal"])
            marker = "▶" if row.style == "due" else "&nbsp;&nbsp;"
            weight = "bold" if row.style == "due" else "normal"
            rows.append(
                f"<tr style='color:{color}; font-weight:{weight}'>"
                f"<td>{marker} {row.time}</td><td>&nbsp;{escape(row.text)}</td></tr>"
            )
        self._label.setText(head + "<table>" + "".join(rows) + "</table>")
        self.adjustSize()

    def place(self, x: int | None, y: int | None) -> None:
        if x is None or y is None:
            geo = QGuiApplication.primaryScreen().availableGeometry()
            x = geo.right() - WIDTH - MARGIN
            y = geo.top() + MARGIN
        self.move(x, y)
