"""
语音访谈任务 Widget（集成版）
逐题展示 3 个核心问题，每题独立计时，自动推进，无需按键。
"""

import os, csv, time

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QProgressBar
from PyQt5.QtCore    import Qt, QTimer

from engine.paradigms.base import BaseParadigmWidget

BG    = "#0a0a0a"
WHITE = "#f5f5f5"
BLUE  = "#7ec8e3"
GRAY  = "#1a1a1a"
LGRAY = "#555555"

DEFAULT_INTRO_SECS   = 8
DEFAULT_ANS_SECS     = 60
DEFAULT_TRANSIT_SECS = 5

DEFAULT_QUESTIONS = [
    "最近这段时间，您的心情总体上是怎么样的？\n有什么让您感到开心或烦恼的事情吗？",
    "在日常生活中，您最喜欢做什么活动？\n这些活动能让您感到快乐吗？",
    "当您遇到压力或困难的时候，\n通常会怎么做来调节自己的状态？",
]


class VoiceInterviewTask(BaseParadigmWidget):
    """
    questions   : list of str（为空时使用内置默认问题）
    params      : task params（n_questions, per_question_duration, transit_duration）
    output_path : 结果 CSV
    voice       : VoiceGuidance 实例
    """

    def __init__(self, questions: list, params: dict,
                 output_path: str, voice=None, parent=None):
        super().__init__(output_path, parent)
        self._questions  = questions if questions else DEFAULT_QUESTIONS
        self._params     = params
        self._voice      = voice

        self._intro_secs   = int(params.get('intro_duration', DEFAULT_INTRO_SECS))
        self._ans_secs     = int(params.get('per_question_duration', DEFAULT_ANS_SECS))
        self._transit_secs = int(params.get('transit_duration', DEFAULT_TRANSIT_SECS))

        self._idx      = 0
        self._phase    = "intro"
        self._elapsed  = 0
        self._q_start  = 0.0
        self._results: list[dict] = []
        self._voice_player = None

        self.setStyleSheet(f"background:{BG};")
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch(2)

        self._lbl_no = QLabel()
        self._lbl_no.setAlignment(Qt.AlignCenter)
        self._lbl_no.setStyleSheet(
            f"color:{BLUE}; font-size:16px; font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_no)

        lay.addSpacing(20)

        self._lbl_q = QLabel()
        self._lbl_q.setAlignment(Qt.AlignCenter)
        self._lbl_q.setWordWrap(True)
        self._lbl_q.setStyleSheet(
            f"color:{WHITE}; font-size:40px; font-family:'Microsoft YaHei';"
            "padding:0 80px;"
        )
        lay.addWidget(self._lbl_q)

        lay.addSpacing(40)

        self._lbl_info = QLabel()
        self._lbl_info.setAlignment(Qt.AlignCenter)
        self._lbl_info.setStyleSheet(
            f"color:{LGRAY}; font-size:18px; font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_info)

        lay.addSpacing(30)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setStyleSheet(
            "QProgressBar{background:#111;border:none;}"
            "QProgressBar::chunk{background:#7ec8e3;}"
        )
        lay.addWidget(self._bar)

        lay.addStretch(3)

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
        self._lbl_no.setText("")
        self._lbl_q.setStyleSheet(
            f"color:{WHITE}; font-size:38px; font-family:'Microsoft YaHei';"
            "padding:0 80px;"
        )
        self._lbl_q.setText(
            "【 语音访谈任务 】\n\n"
            f"接下来将向您提出 {len(self._questions)} 个问题\n\n"
            "请用自然语言回答，无需顾虑，说出真实感受即可\n\n"
            "每个问题回答时长约一分钟，系统会自动切换，无需按键"
        )
        self._lbl_info.setText(f"共 {len(self._questions)} 个问题，每题约 {self._ans_secs} 秒")
        self._bar.setValue(0)
        self._lbl_hint.setText("")

        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)

        self._speak_then(
            self._voice,
            f"接下来是语音访谈任务，共有{len(self._questions)}个问题。"
            "请用自然语言回答，说出真实感受即可。"
            "每个问题约一分钟，系统会自动切换。",
            lambda: self._show_question(0),
        )

    def _show_question(self, idx: int):
        self._phase   = "answer"
        self._idx     = idx
        self._elapsed = 0
        self._q_start = time.time()
        self._send_marker("STIM_QUESTION_ON", question=idx + 1)

        q = self._questions[idx]
        self._lbl_no.setText(f"问题  {idx + 1}  /  {len(self._questions)}")
        self._lbl_q.setStyleSheet(
            f"color:{WHITE}; font-size:40px; font-family:'Microsoft YaHei';"
            "padding:0 80px;"
        )
        self._lbl_q.setText(q)
        self._lbl_info.setText("请用自然语言回答，说出真实感受即可")
        self._bar.setValue(0)
        self._bar.setStyleSheet(
            "QProgressBar{background:#111;border:none;}"
            "QProgressBar::chunk{background:#7ec8e3;}"
        )
        self._lbl_hint.setText(f"第 {idx + 1}/{len(self._questions)} 题")
        self._speak(f"第{idx + 1}题：{q.replace(chr(10), '')}")
        self._tick.start()

    def _show_transit(self):
        self._phase   = "transit"
        self._elapsed = 0
        self._lbl_no.setText("")
        self._lbl_q.setStyleSheet(
            f"color:{LGRAY}; font-size:22px; font-family:'Microsoft YaHei';"
            "padding:0 80px;"
        )
        self._lbl_q.setText("稍作休息…")
        self._lbl_info.setText(f"下一个问题即将出现")
        self._bar.setValue(0)
        self._bar.setStyleSheet(
            "QProgressBar{background:#111;border:none;}"
            "QProgressBar::chunk{background:#555;}"
        )
        self._tick.start()

    def _show_end(self):
        self._phase = "end"
        self._tick.stop()
        self._lbl_no.setText("")
        self._lbl_q.setStyleSheet(
            f"color:{WHITE}; font-size:40px; font-family:'Microsoft YaHei';"
            "padding:0 80px;"
        )
        self._lbl_q.setText("语音访谈任务已完成\n\n感谢您的配合，请稍作休息")
        self._lbl_info.setText("")
        self._bar.setValue(100)
        self._lbl_hint.setText("任务完成")
        self._speak_then(
            self._voice,
            "语音访谈任务已完成，感谢您的配合，请稍作休息。",
            self._force_finish,
        )

    def _on_tick(self):
        self._elapsed += 1
        target = {
            "answer":  self._ans_secs,
            "transit": self._transit_secs,
        }.get(self._phase, 5)

        pct = int(self._elapsed / max(target, 1) * 100)
        self._bar.setValue(min(pct, 100))

        if self._phase == "answer":
            rm, rs = divmod(max(self._ans_secs - self._elapsed, 0), 60)
            self._lbl_hint.setText(
                f"第 {self._idx + 1}/{len(self._questions)} 题   剩余 {rm:02d}:{rs:02d}"
            )

        if self._elapsed >= target:
            self._tick.stop()
            if self._phase == "answer":
                self._send_marker("STIM_QUESTION_OFF",
                                  question=self._idx + 1)
                self._results.append({
                    "q_idx":      self._idx + 1,
                    "question":   self._questions[self._idx].replace('\n', ''),
                    "answer_ms":  round((time.time() - self._q_start) * 1000),
                    "timestamp":  time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                next_idx = self._idx + 1
                if next_idx >= len(self._questions):
                    self._show_end()
                else:
                    self._show_transit()

            elif self._phase == "transit":
                self._show_question(self._idx + 1)

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
