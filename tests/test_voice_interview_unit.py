"""
语音访谈任务 — 单元测试
========================
结构化开放性问答，患者口头作答，全程麦克风录音由系统统一管理。

实验流程
--------
  [指导语屏 + AI 配音，自动进入]
  → [Q1 显示 60s] → [5s 过渡] → [Q2 显示 60s] → [5s 过渡] → [Q3 显示 60s]
  → [结束屏 + AI 配音]

问题依据
--------
  · Gratch et al. (2014) DAIC-WOZ Corpus — 抑郁症结构化语音访谈金标准
  · Lu et al. (2022) EATD-Corpus, ICASSP — 首个中文抑郁症音频文本数据集
  · PHQ-9 / HAMD 核心条目锚定

  Q1 → 整体情绪状态（PHQ-9 #1）
  Q2 → 快感缺失 Anhedonia（PHQ-9 #2，MDD 核心症状）
  Q3 → 认知偏向 + 语言流畅度（自由叙述）

运行
----
  python -X utf8 tests/test_voice_interview_unit.py
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
INTRO_SECS      = 10   # 指导语展示
ANSWER_SECS     = 60   # 每题作答时长
TRANSITION_SECS = 5    # 题间过渡

# ── 三个核心问题 ──────────────────────────────────────────────────
QUESTIONS = [
    {
        "idx":    1,
        "target": "情绪状态",
        "text":   "最近这段时间，\n\n你的整体心情和状态怎么样？",
    },
    {
        "idx":    2,
        "target": "快感缺失",
        "text":   "最近有什么事情，\n\n让你感到开心或者期待的吗？",
    },
    {
        "idx":    3,
        "target": "认知偏向",
        "text":   "如果用几个词来形容\n\n你最近的生活，你会选哪几个词？",
    },
]

# ── 配色 ─────────────────────────────────────────────────────────
BG    = "#0d0d0d"
WHITE = "#f0f0f0"
BLUE  = "#7ec8e3"
GRAY  = "#555555"
LGRAY = "#888888"
GOLD  = "#f5c842"


class VoiceInterviewWindow(QWidget):
    """语音访谈任务全屏窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("语音访谈任务")
        self.setStyleSheet(f"background:{BG};")
        self.showFullScreen()

        self.phase    = "intro"
        self.q_idx    = 0          # 当前题序（0-based）
        self._elapsed = 0
        self._target  = 0
        self._q_start_ts: float = 0.0
        self.results: list[dict] = []

        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)

        self._voice        = None
        self._voice_player = None
        self._init_voice()

        self._build_ui()
        QTimer.singleShot(200, self._show_intro)

    # ─────────────────────────────────── UI ────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(100, 60, 100, 40)
        lay.setSpacing(0)

        lay.addStretch(2)

        # 题号标签
        self._lbl_qnum = QLabel()
        self._lbl_qnum.setAlignment(Qt.AlignCenter)
        self._lbl_qnum.setStyleSheet(
            f"color:{LGRAY}; font-size:18px; font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_qnum)

        lay.addSpacing(20)

        # 问题正文
        self._lbl_question = QLabel()
        self._lbl_question.setAlignment(Qt.AlignCenter)
        self._lbl_question.setWordWrap(True)
        self._lbl_question.setStyleSheet(
            f"color:{WHITE}; font-size:36px; line-height:200%;"
            "font-family:'Microsoft YaHei'; font-weight:bold;"
        )
        lay.addWidget(self._lbl_question)

        lay.addSpacing(20)

        # 副提示（"请用语言回答"等）
        self._lbl_hint2 = QLabel()
        self._lbl_hint2.setAlignment(Qt.AlignCenter)
        self._lbl_hint2.setStyleSheet(
            f"color:{LGRAY}; font-size:18px; font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_hint2)

        lay.addSpacing(50)

        # 进度条
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setStyleSheet("""
            QProgressBar { background:#222; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#7ec8e3; border-radius:2px; }
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

        # 底部
        self._lbl_bottom = QLabel("按 Esc 退出")
        self._lbl_bottom.setAlignment(Qt.AlignCenter)
        self._lbl_bottom.setStyleSheet(
            f"color:{GRAY}; font-size:13px; font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_bottom)
        lay.addSpacing(12)

    # ─────────────────────────────────── 指导语 ─────────────────────

    def _show_intro(self):
        self.phase    = "intro"
        self._elapsed = 0
        self._target  = INTRO_SECS

        self._lbl_qnum.setText("")
        self._lbl_question.setStyleSheet(
            f"color:{WHITE}; font-size:22px; line-height:200%;"
            "font-family:'Microsoft YaHei'; font-weight:normal;"
        )
        self._lbl_question.setText(
            "接下来是语音访谈环节，共 3 个问题\n\n"
            "请用自然的语言回答，没有标准答案\n\n"
            "每个问题有 60 秒作答时间，倒计时结束后自动进入下一题\n\n"
            "保持放松，真实表达即可"
        )
        self._lbl_hint2.setText("")
        self._bar.setStyleSheet("""
            QProgressBar { background:#222; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#aaa; border-radius:2px; }
        """)
        self._lbl_bottom.setText("按 Esc 退出")
        self._update_display()
        self._tick.start()

        self._speak(
            "接下来是语音访谈环节，共三个问题。"
            "请用自然的语言回答，没有标准答案。"
            "每个问题有六十秒作答时间，倒计时结束后自动进入下一题。"
            "保持放松，真实表达即可。"
        )

    # ─────────────────────────────────── 问题展示 ───────────────────

    def _show_question(self):
        q = QUESTIONS[self.q_idx]
        self.phase        = "answering"
        self._elapsed     = 0
        self._target      = ANSWER_SECS
        self._q_start_ts  = time.time()

        self._lbl_qnum.setText(f"第  {q['idx']}  题  /  共 {len(QUESTIONS)} 题")
        self._lbl_question.setStyleSheet(
            f"color:{WHITE}; font-size:36px; line-height:200%;"
            "font-family:'Microsoft YaHei'; font-weight:bold;"
        )
        self._lbl_question.setText(q["text"])
        self._lbl_hint2.setText("请用语言回答，自然表达即可")
        self._bar.setStyleSheet("""
            QProgressBar { background:#222; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#7ec8e3; border-radius:2px; }
        """)
        self._lbl_bottom.setText(f"第 {q['idx']} / {len(QUESTIONS)} 题   ·   按 Esc 退出")
        self._update_display()
        self._tick.start()

        self._speak(q["text"].replace("\n\n", "，"))

    # ─────────────────────────────────── 题间过渡 ───────────────────

    def _show_transition(self):
        self.phase    = "transition"
        self._elapsed = 0
        self._target  = TRANSITION_SECS

        next_q = QUESTIONS[self.q_idx] if self.q_idx < len(QUESTIONS) else None

        self._lbl_qnum.setText("")
        self._lbl_question.setStyleSheet(
            f"color:{LGRAY}; font-size:26px; line-height:200%;"
            "font-family:'Microsoft YaHei'; font-weight:normal;"
        )
        self._lbl_question.setText(
            "下一题即将开始…" if next_q else "访谈即将结束…"
        )
        self._lbl_hint2.setText("")
        self._bar.setStyleSheet("""
            QProgressBar { background:#222; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#444; border-radius:2px; }
        """)
        self._update_display()
        self._tick.start()

    # ─────────────────────────────────── 结束 ───────────────────────

    def _show_end(self):
        self.phase = "end"
        self._tick.stop()
        self._save_results()

        self._lbl_qnum.setText("")
        self._lbl_question.setStyleSheet(
            f"color:{WHITE}; font-size:28px; line-height:200%;"
            "font-family:'Microsoft YaHei'; font-weight:normal;"
        )
        self._lbl_question.setText(
            "语音访谈任务已完成\n\n"
            "感谢您的配合，请稍作休息\n\n"
            "按  Esc  退出"
        )
        self._lbl_hint2.setText("")
        self._bar.setValue(100)
        self._lbl_timer.setText("")
        self._lbl_bottom.setText(f"共 {len(QUESTIONS)} 题  ·  结果已保存")

        self._speak("语音访谈任务已全部完成，感谢您的配合，请稍作休息。")

    # ─────────────────────────────────── 计时 ───────────────────────

    def _on_tick(self):
        self._elapsed += 1
        self._update_display()

        if self._elapsed < self._target:
            return

        self._tick.stop()

        if self.phase == "intro":
            self.q_idx = 0
            self._show_question()

        elif self.phase == "answering":
            # 保存本题记录
            q = QUESTIONS[self.q_idx]
            self.results.append({
                "q_idx":     q["idx"],
                "target":    q["target"],
                "question":  q["text"].replace("\n\n", " "),
                "answer_ms": round((time.time() - self._q_start_ts) * 1000),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            self.q_idx += 1
            if self.q_idx >= len(QUESTIONS):
                self._show_end()
            else:
                self._show_transition()

        elif self.phase == "transition":
            self._show_question()

    def _update_display(self):
        remaining = max(self._target - self._elapsed, 0)
        pct       = int(self._elapsed / max(self._target, 1) * 100)
        self._bar.setValue(pct)
        rm, rs = divmod(remaining, 60)
        self._lbl_timer.setText(f"剩余  {rm:02d}:{rs:02d}")

    # ─────────────────────────────────── 保存 ───────────────────────

    def _save_results(self):
        if not self.results:
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ts   = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(OUTPUT_DIR, f"voice_interview_{ts}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(self.results[0].keys()))
            w.writeheader()
            w.writerows(self.results)
        print(f"[VoiceInterview] 结果已保存：{path}")
        self._lbl_bottom.setText(f"结果已保存：{path}")

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
            self._save_results()
            QApplication.quit()


# ── 入口 ─────────────────────────────────────────────────────────
def main():
    total = INTRO_SECS + len(QUESTIONS) * ANSWER_SECS + (len(QUESTIONS) - 1) * TRANSITION_SECS

    print("=" * 55)
    print("  语音访谈任务  单元测试")
    print("  依据: DAIC-WOZ / EATD-Corpus / PHQ-9")
    print("=" * 55)
    for q in QUESTIONS:
        print(f"  Q{q['idx']}  [{q['target']}]  {q['text'].replace(chr(10)*2, ' ')[:30]}…")
    print()
    print(f"  指导语 {INTRO_SECS}s  · 每题 {ANSWER_SECS}s  · 过渡 {TRANSITION_SECS}s")
    print(f"  预计总时长: {total // 60} 分 {total % 60} 秒")
    print()
    print("  全程自动推进，Esc 随时退出")
    print()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = VoiceInterviewWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
