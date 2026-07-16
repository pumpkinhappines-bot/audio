"""
Interfaz de chat estilo "Chat" con esfera animada + onda de voz, conectada a Qwen vía OpenRouter.

Requiere: pip install PySide6 requests

Configuración:
    Define la variable de entorno OPENROUTER_API_KEY con tu API key de OpenRouter
    antes de ejecutar, por ejemplo (Windows PowerShell):
        $env:OPENROUTER_API_KEY = "sk-or-..."
    o en Linux/Mac:
        export OPENROUTER_API_KEY="sk-or-..."

    Nunca escribas la API key directamente en este archivo si vas a compartirlo
    o subirlo a un repositorio.

Modelo:
    QWEN_MODEL define el slug exacto del modelo en OpenRouter. Verifica el nombre
    vigente en https://openrouter.ai/models antes de correr (los slugs cambian).
"""

import os
import sys
import math
import random
import requests

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import (
    QFont, QPainter, QRadialGradient, QLinearGradient, QColor, QPainterPath, QPen
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QGraphicsDropShadowEffect, QStackedLayout
)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
QWEN_MODEL = "qwen/qwen-2.5-72b-instruct"

DARK_BG = "#12141c"
PANEL_BG = "#1b1e29"
BUBBLE_BOT = "#262a38"
BUBBLE_USER_START = "#6c7fff"
BUBBLE_USER_END = "#8a5cff"
BORDER = "rgba(255,255,255,0.08)"
TEXT_PRIMARY = "#e8ecf5"
TEXT_MUTED = "#8a90a6"
ACCENT_START = "#3ad0c8"
ACCENT_END = "#6c7fff"


# ---------------------------------------------------------------------------
# Esfera animada (equivalente en Qt del componente HTML/canvas)
# ---------------------------------------------------------------------------

ORB_STATES = {
    "reposo":    dict(glass=1.0, swirl_op=0.12, swirl_speed=0.6,  glow=0.18, ring=0.0,  hue=222),
    "enfoque":   dict(glass=1.0, swirl_op=0.32, swirl_speed=1.2,  glow=0.40, ring=0.18, hue=228),
    "escritura": dict(glass=0.55,swirl_op=0.92, swirl_speed=3.0,  glow=1.00, ring=0.55, hue=250),
    "respuesta": dict(glass=0.15,swirl_op=1.00, swirl_speed=4.0,  glow=1.25, ring=0.85, hue=210),
}


class OrbWidget(QWidget):
    def __init__(self, diameter=34):
        super().__init__()
        self.setFixedSize(diameter, diameter)
        self.diameter = diameter
        self.t = 0.0
        self.current = dict(ORB_STATES["reposo"])
        self.target = ORB_STATES["reposo"]

        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(24)
        effect.setOffset(0, 0)
        effect.setColor(QColor(108, 127, 255, 160))
        self.setGraphicsEffect(effect)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    def set_state(self, name):
        self.target = ORB_STATES[name]

    def _tick(self):
        self.t += 0.033
        f = 0.08
        for k in self.current:
            self.current[k] += (self.target[k] - self.current[k]) * f
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 2

        c = self.current
        hue = int(c["hue"]) % 360

        if c["glow"] > 0.02:
            glow_r = r * 1.6
            grad = QRadialGradient(cx, cy, glow_r)
            col = QColor.fromHsv(hue, 200, 255)
            col.setAlphaF(0.35 * c["glow"])
            grad.setColorAt(0, col)
            transparent = QColor(col)
            transparent.setAlphaF(0)
            grad.setColorAt(1, transparent)
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2)

        if c["glass"] > 0.02:
            grad = QRadialGradient(cx - r * 0.3, cy - r * 0.35, r * 1.2)
            top = QColor(255, 255, 255)
            top.setAlphaF(0.9 * c["glass"])
            mid = QColor.fromHsv(hue, 60, 240)
            mid.setAlphaF(0.35 * c["glass"])
            bot = QColor.fromHsv(hue, 140, 90)
            bot.setAlphaF(0.18 * c["glass"])
            grad.setColorAt(0, top)
            grad.setColorAt(0.45, mid)
            grad.setColorAt(1, bot)
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        p.save()
        path = QPainterPath()
        path.addEllipse(cx - r * 0.97, cy - r * 0.97, r * 1.94, r * 1.94)
        p.setClipPath(path)

        swirl_count = 3
        rot = self.t * c["swirl_speed"]
        for i in range(swirl_count):
            ang = (i / swirl_count) * 2 * math.pi + rot
            p.save()
            p.translate(cx, cy)
            p.rotate(math.degrees(ang))
            pen_col = QColor.fromHsv((hue + i * 25) % 360, 200, 255)
            alpha = c["swirl_op"] * (0.5 + 0.5 * math.sin(self.t * 2 + i))
            pen_col.setAlphaF(max(0.0, min(1.0, alpha)))
            pen = QPen(pen_col, r * 0.22)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            curve = QPainterPath()
            curve.moveTo(-r * 0.85, 0)
            sign = 1 if i % 2 == 0 else -1
            curve.quadTo(0, r * 0.5 * sign, r * 0.85, 0)
            p.drawPath(curve)
            p.restore()
        p.restore()


# ---------------------------------------------------------------------------
# Onda de voz (equivalente en Qt del componente HTML/canvas)
# ---------------------------------------------------------------------------

class WaveWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(40)
        self.t = 0.0
        self.level = 0.0
        self.target_level = 0.0
        self.listening = False

        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(20)
        effect.setOffset(0, 0)
        effect.setColor(QColor(108, 140, 255, 140))
        self.setGraphicsEffect(effect)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

        self.mic_timer = QTimer(self)
        self.mic_timer.timeout.connect(self._simulate_level)

    def start_listening(self):
        self.listening = True
        self.mic_timer.start(200)

    def stop_listening(self):
        self.listening = False
        self.mic_timer.stop()
        self.target_level = 0.0

    def _simulate_level(self):
        # NOTA: aquí es donde conectarías el nivel real del micrófono
        # (por ejemplo con la librería 'sounddevice') en vez de un valor aleatorio.
        self.target_level = 0.35 + random.random() * 0.65

    def _tick(self):
        self.t += 0.033
        self.level += (self.target_level - self.level) * 0.15
        self.update()

    def _wave_y(self, x, amp, phase, seed):
        n = (math.sin(x * 0.02 + phase + seed) * 0.6
             + math.sin(x * 0.046 + phase * 1.7) * 0.25
             + math.sin(x * 0.012 - phase * 0.8) * 0.15)
        return n * amp

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        mid = h / 2

        if self.level < 0.02 and not self.listening:
            pen = QPen(QColor(140, 150, 190, 60), 2)
            p.setPen(pen)
            path = QPainterPath()
            for x in range(0, w, 4):
                y = mid + math.sin(x * 0.02 + self.t * 0.6) * 1.5
                path.moveTo(x, y) if x == 0 else path.lineTo(x, y)
            p.drawPath(path)
            return

        amp = h * 0.42 * self.level
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor(58, 208, 200))
        grad.setColorAt(0.45, QColor(80, 150, 240))
        grad.setColorAt(0.75, QColor(140, 120, 240))
        grad.setColorAt(1.0, QColor(190, 140, 235))

        pen = QPen(grad, 3.2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        path = QPainterPath()
        for x in range(0, w, 3):
            y = mid + self._wave_y(x, amp, self.t * 2.4, 0)
            path.moveTo(x, y) if x == 0 else path.lineTo(x, y)
        p.drawPath(path)

        pen2 = QPen(grad, 1.8)
        pen2_col_pen = pen2
        p.setOpacity(0.4)
        p.setPen(pen2_col_pen)
        path2 = QPainterPath()
        for x in range(0, w, 3):
            y = mid + self._wave_y(x, amp * 0.65, self.t * 2.4, 1.8)
            path2.moveTo(x, y) if x == 0 else path2.lineTo(x, y)
        p.drawPath(path2)
        p.setOpacity(1.0)


# ---------------------------------------------------------------------------
# Resto de la interfaz
# ---------------------------------------------------------------------------

class ChatBubble(QLabel):
    def __init__(self, text, is_user=False):
        super().__init__(text)
        self.setWordWrap(True)
        self.setMaximumWidth(420)
        self.setFont(QFont("Segoe UI", 10))
        bg = (f"qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {BUBBLE_USER_START}, stop:1 {BUBBLE_USER_END})"
              if is_user else BUBBLE_BOT)
        color = "#ffffff" if is_user else TEXT_PRIMARY
        self.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                color: {color};
                padding: 10px 14px;
                border-radius: 14px;
                font-size: 13px;
            }}
        """)


class SidebarItem(QPushButton):
    def __init__(self, text, active=False):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        bg = "rgba(255,255,255,0.06)" if active else "transparent"
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                background: {bg};
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.05); }}
        """)


class TrafficLights(QWidget):
    def __init__(self, on_close):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for color, handler in [("#ff5f57", on_close), ("#febc2e", None), ("#28c840", None)]:
            dot = QPushButton()
            dot.setFixedSize(12, 12)
            dot.setCursor(Qt.PointingHandCursor)
            dot.setStyleSheet(f"background:{color}; border-radius:6px; border:none;")
            if handler:
                dot.clicked.connect(handler)
            layout.addWidget(dot)


class TopBar(QWidget):
    def __init__(self, on_close):
        super().__init__()
        self.setFixedHeight(56)
        self.setStyleSheet(f"background:{PANEL_BG};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)

        layout.addWidget(TrafficLights(on_close))
        layout.addStretch()

        title = QLabel("Chat")
        title.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:15px; font-weight:600;")
        layout.addWidget(title)
        layout.addStretch()

        avatar = QLabel()
        avatar.setFixedSize(28, 28)
        avatar.setStyleSheet("""
            background: qradialgradient(cx:0.4, cy:0.3, radius:1,
                stop:0 #7f9cff, stop:1 #4a5a9c);
            border-radius: 14px;
        """)
        layout.addWidget(avatar)

        name = QLabel("Alejandro V.")
        name.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:13px; margin-left:8px;")
        layout.addWidget(name)

        settings = QLabel("\u2699")
        settings.setStyleSheet(f"color:{TEXT_MUTED}; font-size:16px; margin-left:14px;")
        layout.addWidget(settings)


class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(230)
        self.setStyleSheet(f"background:{PANEL_BG}; border-left: 1px solid {BORDER};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        label = QLabel("CONVERSATIONS")
        label.setStyleSheet(f"color:{TEXT_MUTED}; font-size:11px; letter-spacing:1px; margin-bottom:6px;")
        layout.addWidget(label)

        items = [
            ("Project Alpha Draft", True),
            ("Data Analysis Q2", False),
            ("Meeting Notes Summary", False),
            ("Meeting Notes Summary", False),
        ]
        for text, active in items:
            layout.addWidget(SidebarItem(text, active))

        layout.addStretch()

        new_chat = QPushButton("  +  New Chat")
        new_chat.setCursor(Qt.PointingHandCursor)
        new_chat.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {ACCENT_START}, stop:1 {ACCENT_END});
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px;
                font-size: 13px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(new_chat)


class ChatArea(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setStyleSheet(f"background:{DARK_BG}; border:none;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.container.setStyleSheet(f"background:{DARK_BG};")
        self.vbox = QVBoxLayout(self.container)
        self.vbox.setContentsMargins(24, 20, 24, 20)
        self.vbox.setSpacing(14)
        self.vbox.addStretch()
        self.setWidget(self.container)

    def add_message(self, text, is_user=False):
        row = QHBoxLayout()
        bubble = ChatBubble(text, is_user=is_user)
        if is_user:
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()

        wrapper = QWidget()
        wrapper.setLayout(row)
        self.vbox.insertWidget(self.vbox.count() - 1, wrapper)

        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())


class QwenWorker(QThread):
    """Ejecuta la llamada a OpenRouter (Qwen) en un hilo aparte para no congelar la UI."""
    finished_ok = Signal(str)
    finished_error = Signal(str)

    def __init__(self, messages):
        super().__init__()
        self.messages = messages

    def run(self):
        if not OPENROUTER_API_KEY:
            self.finished_error.emit(
                "No se encontró OPENROUTER_API_KEY. Define la variable de entorno antes de ejecutar."
            )
            return
        try:
            resp = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": QWEN_MODEL,
                    "messages": self.messages,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            self.finished_ok.emit(text)
        except Exception as e:
            self.finished_error.emit(f"Error al llamar a OpenRouter: {e}")


class InputBar(QWidget):
    def __init__(self, on_send, on_mic_toggle):
        super().__init__()
        self.on_send = on_send
        self.on_mic_toggle = on_mic_toggle
        self.listening = False

        self.setFixedHeight(74)
        self.setStyleSheet(f"background:{PANEL_BG}; border-top: 1px solid {BORDER};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(12)

        self.mic_btn = QPushButton("\U0001F3A4")
        self.mic_btn.setCursor(Qt.PointingHandCursor)
        self.mic_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none; color: {TEXT_MUTED}; font-size:16px; }}
            QPushButton:hover {{ color: {TEXT_PRIMARY}; }}
        """)
        self.mic_btn.clicked.connect(self._toggle_mic)
        layout.addWidget(self.mic_btn)

        self.orb = OrbWidget(34)
        layout.addWidget(self.orb)

        self.stack_holder = QWidget()
        self.stack = QStackedLayout(self.stack_holder)
        self.stack.setContentsMargins(0, 0, 0, 0)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a message...")
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background: {BUBBLE_BOT};
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: 18px;
                padding: 10px 16px;
                font-size: 13px;
            }}
        """)
        self.input.returnPressed.connect(self._send)

        self.wave = WaveWidget()

        self.stack.addWidget(self.input)
        self.stack.addWidget(self.wave)
        layout.addWidget(self.stack_holder, stretch=1)

        self.send_btn = QPushButton("\u27A4")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setFixedSize(34, 34)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_MUTED}; border: none; font-size:16px; }}
            QPushButton:hover {{ color: {TEXT_PRIMARY}; }}
        """)
        self.send_btn.clicked.connect(self._send)
        layout.addWidget(self.send_btn)

    def _toggle_mic(self):
        self.listening = not self.listening
        if self.listening:
            self.stack.setCurrentWidget(self.wave)
            self.wave.start_listening()
            self.orb.set_state("enfoque")
        else:
            self.stack.setCurrentWidget(self.input)
            self.wave.stop_listening()
            self.orb.set_state("reposo")
        self.on_mic_toggle(self.listening)

    def _send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.on_send(text)

    def set_locked(self, locked):
        self.input.setEnabled(not locked)
        self.send_btn.setEnabled(not locked)
        self.mic_btn.setEnabled(not locked)


class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.resize(1040, 620)
        self._drag_pos = None
        self.history = [
            {"role": "system", "content": "Eres un asistente útil y conciso."}
        ]

        root = QWidget()
        root.setStyleSheet(f"background:{DARK_BG}; border-radius:14px;")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.top_bar = TopBar(on_close=self.close)
        outer.addWidget(self.top_bar)

        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)

        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(0)

        self.chat_area = ChatArea()
        center.addWidget(self.chat_area, stretch=1)

        self.input_bar = InputBar(on_send=self.on_send, on_mic_toggle=self.on_mic_toggle)
        center.addWidget(self.input_bar)

        center_widget = QWidget()
        center_widget.setLayout(center)
        middle.addWidget(center_widget, stretch=1)

        self.sidebar = Sidebar()
        middle.addWidget(self.sidebar)

        middle_widget = QWidget()
        middle_widget.setLayout(middle)
        outer.addWidget(middle_widget, stretch=1)

        self.chat_area.add_message("Hello! How can I help you with your analysis today?", is_user=False)

        self._worker = None

    def on_mic_toggle(self, listening):
        # Aquí es donde conectarías tu motor de reconocimiento de voz real
        # (por ejemplo, un stream de audio -> texto) para llenar el input
        # cuando el usuario termine de hablar.
        pass

    def on_send(self, text):
        self.chat_area.add_message(text, is_user=True)
        self.history.append({"role": "user", "content": text})

        self.input_bar.orb.set_state("respuesta")
        self.input_bar.set_locked(True)

        self._worker = QwenWorker(list(self.history))
        self._worker.finished_ok.connect(self._on_ai_ok)
        self._worker.finished_error.connect(self._on_ai_error)
        self._worker.start()

    def _on_ai_ok(self, text):
        self.history.append({"role": "assistant", "content": text})
        self.chat_area.add_message(text, is_user=False)
        self.input_bar.orb.set_state("reposo")
        self.input_bar.set_locked(False)

    def _on_ai_error(self, message):
        self.chat_area.add_message(message, is_user=False)
        self.input_bar.orb.set_state("reposo")
        self.input_bar.set_locked(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() < 56:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


def main():
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()