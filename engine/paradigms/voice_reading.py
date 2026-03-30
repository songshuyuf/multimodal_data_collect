"""
语音朗读任务 Widget（集成版）
显示一段正性文本，患者以正常语速朗读，自动计时结束。
"""

import os, csv, time

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QProgressBar, QScrollArea, QWidget
from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtGui     import QFont

from engine.paradigms.base import BaseParadigmWidget

BG    = "#0a0a0a"
WHITE = "#f5f5f5"
GOLD  = "#d4a94a"
GRAY  = "#1a1a1a"
LGRAY = "#555555"

DEFAULT_INTRO_SECS  = 8
DEFAULT_READ_SECS   = 90

# 内置文本（春节团圆·正性，约200字，Zhao et al. 2022 标准）
BUILTIN_TEXT = (
    "新年的阳光照进了宽敞明亮的客厅，空气中弥漫着刚出锅的饺子\n"
    "香气。桌上摆满了一家人最爱的菜肴，孩子们在院子里放着烟花，\n"
    "笑声此起彼伏。\n\n"
    "父母坐在暖意融融的沙发上，脸上挂着满足而幸福的笑容。一家\n"
    "人围坐在一起，讲述着这一年里各自的故事——出行的见闻、工作\n"
    "的进步、孩子的成长。\n\n"
    "窗外，烟花次第绽放，五彩的光芒映照在每一张温暖的脸上。这\n"
    "一刻，时间仿佛静止了，所有的疲惫与烦恼都随着绚烂的礼花消\n"
    "散于天际。\n\n"
    "新的一年，充满希望与可能。家人在身边，便是最好的新年礼物。"
)


class VoiceReadingTask(BaseParadigmWidget):
    """
    text         : 朗读文本（为空时使用内置春节文本）
    params       : task params（read_duration: 秒, intro_duration: 秒）
    output_path  : 结果 CSV
    voice        : VoiceGuidance 实例
    """

    def __init__(self, text: str, params: dict,
                 output_path: str, voice=None, parent=None):
        super().__init__(output_path, parent)
        self._text       = text.strip() if text and text.strip() else BUILTIN_TEXT
        self._params     = params
        self._voice      = voice

        self._intro_secs = int(params.get('intro_duration', DEFAULT_INTRO_SECS))
        self._read_secs  = int(params.get('read_duration',
                                          params.get('duration', DEFAULT_READ_SECS)))

        self._phase      = "intro"
        self._elapsed    = 0
        self._start_ts   = 0.0
        self._results: list[dict] = []
        self._voice_player = None

        self.setStyleSheet(f"background:{BG};")
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 内容区
        self._content = QLabel()
        self._content.setAlignment(Qt.AlignCenter)
        self._content.setWordWrap(True)
        self._content.setStyleSheet(
            f"background:{BG}; color:{WHITE}; font-size:42px;"
            "font-family:'Microsoft YaHei'; padding:60px;"
        )
        lay.addWidget(self._content, stretch=1)

        # 进度条
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setStyleSheet(
            "QProgressBar{background:#111;border:none;}"
            "QProgressBar::chunk{background:#8899aa;}"
        )
        lay.addWidget(self._bar)

        # 底部状态栏
        bottom = QLabel()
        bottom.setFixedHeight(30)
        bottom.setStyleSheet(f"background:{GRAY};")
        bot_lay = QVBoxLayout(bottom)
        bot_lay.setContentsMargins(0, 0, 0, 0)
        self._lbl_hint = QLabel()
        self._lbl_hint.setAlignment(Qt.AlignCenter)
        self._lbl_hint.setStyleSheet(
            f"color:{LGRAY}; font-size:12px; font-family:'Microsoft YaHei';"
        )
        bot_lay.addWidget(self._lbl_hint)
        lay.addWidget(bottom)

    # ── 启动/停止 ────────────────────────────────────────────────

    def _do_start(self):
        self._show_intro()

    def _do_stop(self):
        if hasattr(self, '_tick'):
            self._tick.stop()
        self._save_results()

    # ── 流程 ────────────────────────────────────────────────────

    def _show_intro(self):
        self._phase   = "intro"
        self._elapsed = 0
        self._content.setStyleSheet(
            f"background:{BG}; color:{WHITE}; font-size:42px;"
            "font-family:'Microsoft YaHei'; padding:60px;"
        )
        self._content.setText(
            "【 语音朗读任务 】\n\n"
            "请以正常、自然的语速朗读屏幕上的文字\n\n"
            "不需要背诵，朗读时请保持声音清晰\n\n"
            "整个过程无需任何按键操作"
        )
        self._bar.setValue(0)
        self._lbl_hint.setText(f"朗读时长 {self._read_secs}s")

        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)

        self._speak_then(
            self._voice,
            "接下来是语音朗读任务。"
            "请以正常、自然的语速朗读屏幕上显示的文字，"
            "无需背诵，保持声音清晰即可。",
            self._show_reading,
        )

    def _show_reading(self):
        self._phase    = "reading"
        self._elapsed  = 0
        self._start_ts = time.time()
        self._send_marker("STIM_READING_ON")
        self._content.setStyleSheet(
            f"background:{BG}; color:{WHITE}; font-size:40px;"
            "line-height:200%; font-family:'Microsoft YaHei';"
            "padding:60px 100px;"
        )
        self._content.setText(self._text)
        self._lbl_hint.setText(f"剩余 {self._read_secs}s")
        self._tick.start()

    def _show_end(self):
        self._phase = "end"
        self._tick.stop()
        self._content.setStyleSheet(
            f"background:{BG}; color:{WHITE}; font-size:42px;"
            "font-family:'Microsoft YaHei'; padding:60px;"
        )
        self._content.setText(
            "语音朗读任务已完成\n\n感谢您的配合，请稍作休息"
        )
        self._bar.setValue(100)
        self._lbl_hint.setText("任务完成")
        self._speak_then(
            self._voice,
            "语音朗读任务已完成，感谢您的配合，请稍作休息。",
            self._force_finish,
        )

    def _on_tick(self):
        if self._phase != "reading":
            return
        self._elapsed += 1
        pct = int(self._elapsed / max(self._read_secs, 1) * 100)
        self._bar.setValue(min(pct, 100))

        rm, rs = divmod(max(self._read_secs - self._elapsed, 0), 60)
        self._lbl_hint.setText(f"剩余 {rm:02d}:{rs:02d}")

        if self._elapsed >= self._read_secs:
            self._tick.stop()
            self._send_marker("STIM_READING_OFF")
            self._results.append({
                "theme":       "positive",
                "char_count":  len(self._text.replace('\n', '')),
                "read_ms":     round((time.time() - self._start_ts) * 1000),
                "timestamp":   time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            self._show_end()

    # ── 保存 ─────────────────────────────────────────────────────

    def _save_results(self):
        if not self._results or not self._output_path:
            return
        os.makedirs(os.path.dirname(self._output_path) or ".", exist_ok=True)
        with open(self._output_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(self._results[0].keys()))
            w.writeheader()
            w.writerows(self._results)

    # ── 语音 ─────────────────────────────────────────────────────

    def _speak(self, text: str):
        self._speak_no_wait(self._voice, text)
