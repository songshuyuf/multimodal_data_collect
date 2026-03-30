"""
语音朗读任务 — 单元测试
========================
被试朗读屏幕上显示的正性文本，全程麦克风录音由系统统一管理，本模块不单独录音。

实验流程
--------
  [指导语屏 + AI 配音，10s 后自动进入]
  → [朗读屏：显示春节文本，90s 倒计时]
  → [结束屏 + AI 配音]

文本依据
--------
  Zhao et al. (2022) Frontiers in Psychiatry
  "Vocal Acoustic Features as Potential Biomarkers for Identifying/Diagnosing
   Depression: A Cross-Sectional Study"  DOI: 10.3389/fpsyt.2022.815678
  中文被试朗读正性、中性、负性文本（~200字/段），以 MFCC/F0/ZCR/HNR 为声学特征，
  抑郁患者 vs. 健康对照判别准确率 89.66%。

运行
----
  python -X utf8 tests/test_voice_reading_unit.py
"""

import os
import sys
import csv
import time

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QProgressBar
from PyQt5.QtCore    import Qt, QTimer, QUrl
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUTPUT_DIR = os.path.join(ROOT, "dataset", "results")

# ── 时序（秒） ────────────────────────────────────────────────────
INTRO_SECS = 10    # 指导语展示时长（AI 配音期间）
READ_SECS  = 90    # 朗读屏展示时长

# ── 朗读文本 ─────────────────────────────────────────────────────
PASSAGE = {
    "theme":   "春节团圆",
    "valence": "正性",
    "text": (
        "春节快到了，家家户户张灯结彩，空气中弥漫着年货的香气。"
        "孩子们穿着新衣，在院子里嬉笑玩耍，欢声笑语不断。"
        "厨房里飘出饺子和红烧肉的香味，令人垂涎欲滴。"
        "一家人围坐在一起，分享着过去一年的收获与喜悦，脸上洋溢着幸福的笑容。"
        "烟花在夜空中绽放，五彩斑斓，格外美丽。"
        "长辈们给孩子们发红包，祝福声此起彼伏，笑声连连。"
        "整个村庄沉浸在欢乐祥和的节日氛围之中，"
        "每个人都感到无比温暖与幸福，充满了对新一年的美好期盼。"
    ),
}

# ── 配色 ─────────────────────────────────────────────────────────
BG     = "#0d0d0d"
WHITE  = "#f0f0f0"
GOLD   = "#f5c842"
GRAY   = "#555555"
LGRAY  = "#888888"


class VoiceReadingWindow(QWidget):
    """语音朗读任务全屏窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("语音朗读任务")
        self.setStyleSheet(f"background:{BG};")
        self.showFullScreen()

        self.phase    = "intro"
        self._elapsed = 0
        self._target  = 0
        self._start_ts: float = 0.0
        self.result: dict = {}

        # 计时器
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)

        # 语音
        self._voice        = None
        self._voice_player = None
        self._init_voice()

        self._build_ui()
        QTimer.singleShot(200, self._show_intro)

    # ─────────────────────────────────── UI ────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(80, 60, 80, 40)
        lay.setSpacing(0)

        lay.addStretch(2)

        # 大标题
        self._lbl_title = QLabel()
        self._lbl_title.setAlignment(Qt.AlignCenter)
        self._lbl_title.setStyleSheet(
            f"color:{GOLD}; font-size:38px; font-weight:bold;"
            "font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_title)

        lay.addSpacing(30)

        # 正文区（指导语 / 朗读文本）
        self._lbl_body = QLabel()
        self._lbl_body.setAlignment(Qt.AlignCenter)
        self._lbl_body.setWordWrap(True)
        self._lbl_body.setStyleSheet(
            f"color:{WHITE}; font-size:26px; line-height:200%;"
            "font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_body)

        lay.addSpacing(50)

        # 进度条
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setStyleSheet("""
            QProgressBar { background:#222; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#f5c842; border-radius:2px; }
        """)
        lay.addWidget(self._bar)

        lay.addSpacing(12)

        # 倒计时
        self._lbl_timer = QLabel()
        self._lbl_timer.setAlignment(Qt.AlignCenter)
        self._lbl_timer.setStyleSheet(
            f"color:{LGRAY}; font-size:15px; font-family:monospace;"
        )
        lay.addWidget(self._lbl_timer)

        lay.addStretch(2)

        # 底部小提示
        self._lbl_hint = QLabel("按 Esc 退出")
        self._lbl_hint.setAlignment(Qt.AlignCenter)
        self._lbl_hint.setStyleSheet(
            f"color:{GRAY}; font-size:13px; font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_hint)
        lay.addSpacing(12)

    # ─────────────────────────────────── 指导语 ─────────────────────

    def _show_intro(self):
        self.phase    = "intro"
        self._elapsed = 0
        self._target  = INTRO_SECS

        self._lbl_title.setText("语音朗读任务")
        self._lbl_body.setStyleSheet(
            f"color:{WHITE}; font-size:22px; line-height:200%;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_body.setText(
            "接下来，屏幕上将显示一段文字\n\n"
            "请以平常的语速和语调，清晰地朗读出来\n\n"
            "朗读时保持自然放松，无需刻意控制语气\n\n"
            "倒计时结束后任务自动完成"
        )
        self._bar.setStyleSheet("""
            QProgressBar { background:#222; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#aaaaaa; border-radius:2px; }
        """)
        self._lbl_hint.setText("按 Esc 退出")
        self._update_timer_display()
        self._tick.start()

        self._speak(
            "接下来是语音朗读任务。屏幕上将显示一段文字，"
            "请以平常的语速和语调清晰地朗读出来，保持自然放松即可。"
        )

    # ─────────────────────────────────── 朗读屏 ─────────────────────

    def _show_reading(self):
        self.phase      = "reading"
        self._elapsed   = 0
        self._target    = READ_SECS
        self._start_ts  = time.time()

        self._lbl_title.setText(f"请朗读以下文字  ·  {PASSAGE['theme']}")
        self._lbl_body.setStyleSheet(
            f"color:{WHITE}; font-size:28px; line-height:200%;"
            "font-family:'Microsoft YaHei'; padding:0 40px;"
        )
        self._lbl_body.setText(PASSAGE["text"])
        self._bar.setStyleSheet("""
            QProgressBar { background:#222; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#f5c842; border-radius:2px; }
        """)
        self._lbl_hint.setText("请清晰朗读   |   按 Esc 退出")
        self._update_timer_display()
        self._tick.start()

        self._speak("请开始朗读。")

    # ─────────────────────────────────── 结束 ───────────────────────

    def _show_end(self):
        self.phase = "end"
        self._tick.stop()

        actual_ms = round((time.time() - self._start_ts) * 1000)
        self.result = {
            "theme":     PASSAGE["theme"],
            "valence":   PASSAGE["valence"],
            "char_count": len(PASSAGE["text"]),
            "read_ms":   actual_ms,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save_result()

        self._lbl_title.setText("朗读完成")
        self._lbl_body.setStyleSheet(
            f"color:{WHITE}; font-size:26px; line-height:200%;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_body.setText(
            "语音朗读任务已完成\n\n"
            "感谢您的配合，请稍作休息\n\n"
            "按  Esc  退出"
        )
        self._bar.setValue(100)
        self._lbl_timer.setText("")
        self._lbl_hint.setText(f"共 {PASSAGE['char_count']} 字  ·  结果已保存")

        self._speak("语音朗读任务已完成，感谢您的配合，请稍作休息。")

    # ─────────────────────────────────── 计时 ───────────────────────

    def _on_tick(self):
        self._elapsed += 1
        self._update_timer_display()

        if self._elapsed >= self._target:
            self._tick.stop()
            if self.phase == "intro":
                self._show_reading()
            elif self.phase == "reading":
                self._show_end()

    def _update_timer_display(self):
        remaining = max(self._target - self._elapsed, 0)
        pct       = int(self._elapsed / max(self._target, 1) * 100)
        self._bar.setValue(pct)
        rm, rs = divmod(remaining, 60)
        self._lbl_timer.setText(f"剩余  {rm:02d}:{rs:02d}")

    # ─────────────────────────────────── 保存 ───────────────────────

    def _save_result(self):
        if not self.result:
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ts   = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(OUTPUT_DIR, f"voice_reading_{ts}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(self.result.keys()))
            w.writeheader()
            w.writerow(self.result)
        print(f"[VoiceReading] 结果已保存：{path}")

    # ─────────────────────────────────── 语音 ───────────────────────

    def _init_voice(self):
        try:
            from engine.voice import VoiceGuidance
            self._voice = VoiceGuidance(parent=self)
            self._voice.play_signal.connect(self._on_play_voice)
        except Exception:
            pass

    def _speak(self, text: str):
        if self._voice:
            self._voice.speak(text)

    def _on_play_voice(self, filepath: str):
        try:
            if self._voice_player is None:
                self._voice_player = QMediaPlayer(self)
            self._voice_player.setMedia(QMediaContent(QUrl.fromLocalFile(filepath)))
            self._voice_player.play()
        except Exception:
            pass

    # ─────────────────────────────────── 键盘 ───────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._tick.stop()
            self._save_result()
            QApplication.quit()


# ── 入口 ─────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  语音朗读任务  单元测试")
    print("  依据: Zhao et al. (2022) Frontiers in Psychiatry")
    print("=" * 55)
    print(f"  文本主题 : {PASSAGE['theme']}  ({PASSAGE['valence']})")
    print(f"  字数     : {len(PASSAGE['text'])} 字")
    print(f"  指导语   : {INTRO_SECS}s  朗读时长 : {READ_SECS}s")
    print()
    print("  流程：指导语(自动) → 朗读屏(自动) → 结束")
    print("  Esc 随时退出")
    print()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = VoiceReadingWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
