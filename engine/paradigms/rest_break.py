"""
休息间隔范式 Widget
===================
在实验任务之间插入倒计时休息，全屏显示，QTimer 驱动。
"""

from PyQt5.QtWidgets import QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer


from engine.paradigms.base import BaseParadigmWidget

BG    = "#000000"
WHITE = "#ffffff"
BLUE  = "#5599ee"
GRAY  = "#333333"
LGRAY = "#666666"


class RestBreakParadigm(BaseParadigmWidget):
    """
    休息间隔。显示提示消息 + 倒计时，duration 秒后自动结束。
    """

    def __init__(self, message: str, duration: int,
                 output_path: str = "", voice=None,
                 voice_text: str = "", parent=None):
        super().__init__(output_path, parent)
        self._message = message
        self._voice_text = voice_text or message
        self._duration = max(duration, 1)
        self._voice = voice
        self._voice_player = None
        self._remaining = self._duration

        self.setStyleSheet(f"background:{BG};")
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch(3)

        self._lbl_msg = QLabel()
        self._lbl_msg.setAlignment(Qt.AlignCenter)
        self._lbl_msg.setWordWrap(True)
        self._lbl_msg.setStyleSheet(
            f"color:{WHITE}; font-size:36px;"
            "font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_msg)

        lay.addSpacing(40)

        self._lbl_countdown = QLabel()
        self._lbl_countdown.setAlignment(Qt.AlignCenter)
        self._lbl_countdown.setStyleSheet(
            f"color:{BLUE}; font-size:72px; font-weight:bold;"
            "font-family:monospace;"
        )
        lay.addWidget(self._lbl_countdown)

        lay.addStretch(4)

        self._lbl_hint = QLabel("")
        self._lbl_hint.setAlignment(Qt.AlignCenter)
        self._lbl_hint.setFixedHeight(30)
        self._lbl_hint.setStyleSheet(
            f"background:{GRAY}; color:{LGRAY}; font-size:12px;"
            "font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_hint)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    # ── 启动 / 停止 ──────────────────────────────────────────────

    def _do_start(self):
        self._remaining = self._duration
        self._lbl_msg.setText(self._message)
        self._lbl_countdown.setText(str(self._remaining))
        self._speak(self._voice_text)
        self._timer.start()

    def _do_stop(self):
        self._timer.stop()

    # ── 计时 ────────────────────────────────────────────────────

    def _on_tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self._force_finish()
            return
        self._lbl_countdown.setText(str(self._remaining))

    # ── 语音 ────────────────────────────────────────────────────

    def _speak(self, text: str):
        self._speak_no_wait(self._voice, text)
