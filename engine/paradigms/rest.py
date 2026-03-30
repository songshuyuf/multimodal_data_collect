"""
静息态 EEG 范式 Widget
=======================
闭眼 / 睁眼交替循环，QTimer 驱动，主线程运行。
"""

import time

from PyQt5.QtWidgets import QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer


from engine.paradigms.base import BaseParadigmWidget

BG    = "#000000"
WHITE = "#ffffff"
GRAY  = "#333333"
LGRAY = "#666666"

INTRO_SECS = 3


class RestParadigm(BaseParadigmWidget):
    """
    静息态 EEG 范式。

    params 来自 experiment_config.json，可选键：
        eyes_open_duration  — 睁眼秒数（默认 20）
        eyes_close_duration — 闭眼秒数（默认 40）
        cycles              — 循环次数（默认 5）
    """

    def __init__(self, params: dict, output_path: str = "",
                 voice=None, parent=None):
        super().__init__(output_path, parent)
        self._params = params
        self._voice = voice
        self._voice_player = None

        self._open_secs = int(params.get("eyes_open_duration", 20))
        self._close_secs = int(params.get("eyes_close_duration", 40))
        self._cycles = int(params.get("cycles", 5))

        self._cycle_idx = 0
        self._phase = "intro"  # intro → eyes_close → eyes_open → … → end
        self._elapsed = 0
        self._target = 0

        self.setStyleSheet(f"background:{BG};")
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch(2)

        self._lbl_main = QLabel()
        self._lbl_main.setAlignment(Qt.AlignCenter)
        self._lbl_main.setWordWrap(True)
        self._lbl_main.setStyleSheet(
            f"color:{WHITE}; font-size:52px; font-weight:bold;"
            "font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_main)

        lay.addStretch(2)

        self._lbl_cycle = QLabel()
        self._lbl_cycle.setAlignment(Qt.AlignCenter)
        self._lbl_cycle.setFixedHeight(36)
        self._lbl_cycle.setStyleSheet(
            f"background:{GRAY}; color:{LGRAY}; font-size:14px;"
            "font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_cycle)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    # ── 启动 / 停止 ──────────────────────────────────────────────

    def _do_start(self):
        self._show_intro()

    def _do_stop(self):
        self._timer.stop()

    # ── 流程 ────────────────────────────────────────────────────

    def _show_intro(self):
        self._phase = "intro"
        self._elapsed = 0
        self._target = INTRO_SECS
        self._lbl_main.setText(
            "【 静息态 EEG 】\n\n"
            "请按屏幕提示\n交替进行闭眼和睁眼"
        )
        self._lbl_cycle.setText(
            f"共 {self._cycles} 个周期"
        )
        self._speak_then(
            self._voice,
            "您好，接下来请您保持放松，自然呼吸。"
            "我们将交替进行睁眼和闭眼的静息测量，请按屏幕提示操作。",
            self._intro_done,
        )

    def _intro_done(self):
        self._cycle_idx = 0
        self._start_eyes_close()

    def _start_eyes_close(self):
        self._phase = "eyes_close"
        self._elapsed = 0
        self._target = self._close_secs
        self._lbl_main.setText("请闭眼放松")
        self._lbl_cycle.setText(
            f"第 {self._cycle_idx + 1}/{self._cycles} 周期 · 闭眼 {self._close_secs}s"
        )
        self._send_marker("STIM_REST_EYES_CLOSE", cycle=self._cycle_idx + 1)
        self._speak("请闭眼，保持放松。")
        self._timer.start()

    def _start_eyes_open(self):
        self._phase = "eyes_open"
        self._elapsed = 0
        self._target = self._open_secs
        self._lbl_main.setText("请睁眼，注视中央 +")
        self._lbl_cycle.setText(
            f"第 {self._cycle_idx + 1}/{self._cycles} 周期 · 睁眼 {self._open_secs}s"
        )
        self._send_marker("STIM_REST_EYES_OPEN", cycle=self._cycle_idx + 1)
        self._speak("请睁眼，注视屏幕中央的注视点。")
        self._timer.start()

    def _show_end(self):
        self._phase = "end"
        self._timer.stop()
        self._lbl_main.setText("静息态测量已完成\n\n感谢您的配合")
        self._lbl_cycle.setText("任务完成")
        self._speak_then(
            self._voice,
            "静息态测量已完成，感谢您的配合，请稍作休息。",
            self._force_finish,
        )

    # ── 计时 ────────────────────────────────────────────────────

    def _on_tick(self):
        self._elapsed += 1
        if self._elapsed < self._target:
            return

        self._timer.stop()

        if self._phase == "eyes_close":
            self._start_eyes_open()

        elif self._phase == "eyes_open":
            self._cycle_idx += 1
            if self._cycle_idx >= self._cycles:
                self._show_end()
            else:
                self._start_eyes_close()

    # ── 语音 ────────────────────────────────────────────────────

    def _speak(self, text: str):
        self._speak_no_wait(self._voice, text)
