"""
Dot-probe 注意偏向任务 Widget
=============================
标准 Dot-probe 范式，全屏运行于主线程。
流程：说明屏(配音完自动进入) → 练习 → 正式试次 → 保存 → finished
"""

import os
import csv
import time
import random

from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QDesktopWidget
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QPixmap, QKeyEvent
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

FIXATION_MS  = 500
IMAGE_MS     = 500
PROBE_MAX_MS = 1500
ITI_MS       = 1000

BG_COLOR  = "#111111"
FG_COLOR  = "white"
HINT_COLOR = "#999999"
OK_COLOR  = "#88ff88"


def _screen_based_img_size() -> tuple:
    """根据屏幕分辨率计算图片显示尺寸（约屏幕高度的 45%）"""
    try:
        desk = QDesktopWidget()
        rect = desk.screenGeometry(desk.primaryScreen())
        h = int(rect.height() * 0.45)
        return h, h
    except Exception:
        return 500, 500


class DotProbeTask(QWidget):
    """标准 Dot-probe 任务窗口（全屏），配音完自动开始"""

    finished = pyqtSignal(str)

    def __init__(self, trials: list, practice_trials: list,
                 output_path: str, voice=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dot-probe 注意偏向任务")
        self.setStyleSheet(f"background-color:{BG_COLOR};")
        self.showFullScreen()

        self._img_w, self._img_h = _screen_based_img_size()

        self._trials    = trials
        self._practice  = practice_trials
        self._out_path  = output_path
        self._voice     = voice

        self.phase       = "instruction"
        self.trial_idx   = 0
        self.results: list[dict] = []

        self._cur_trial  = {}
        self._probe_side = None
        self._probe_ts   = None
        self._probe_timer = QTimer(self)
        self._probe_timer.setSingleShot(True)
        self._probe_timer.timeout.connect(self._on_timeout)

        self._player = None
        self._voice_pending_cb = None
        self._marker_mgr = None
        self._connect_voice()
        self._build_ui()
        QTimer.singleShot(200, self._show_instruction)

    def set_marker_manager(self, mgr):
        self._marker_mgr = mgr

    def _send_marker(self, name: str, **kwargs):
        if self._marker_mgr:
            self._marker_mgr.send_marker(name, **kwargs)

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addStretch(2)

        self._lbl_center = QLabel()
        self._lbl_center.setAlignment(Qt.AlignCenter)
        self._lbl_center.setWordWrap(True)
        self._lbl_center.setStyleSheet(
            f"color:{FG_COLOR}; font-size:52px; font-weight:bold;"
            "font-family:'Microsoft YaHei';"
        )
        root.addWidget(self._lbl_center)
        root.addSpacing(30)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignCenter)
        row.setSpacing(120)
        self._lbl_left  = self._cell()
        self._lbl_right = self._cell()
        row.addWidget(self._lbl_left)
        row.addWidget(self._lbl_right)
        root.addLayout(row)

        root.addStretch(2)

        self._lbl_hint = QLabel()
        self._lbl_hint.setAlignment(Qt.AlignCenter)
        self._lbl_hint.setStyleSheet(
            f"color:{HINT_COLOR}; font-size:15px;"
            "font-family:'Microsoft YaHei';"
        )
        root.addWidget(self._lbl_hint)
        root.addSpacing(18)

    def _cell(self) -> QLabel:
        lbl = QLabel()
        lbl.setFixedSize(self._img_w, self._img_h)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"background:transparent; color:{FG_COLOR}; font-size:60px;"
        )
        return lbl

    # ── 说明屏（配音完自动进入练习）─────────────────────────────

    def _show_instruction(self):
        self.phase = "instruction"
        self._clear()
        self._lbl_center.setStyleSheet(
            f"color:{FG_COLOR}; font-size:24px; line-height:200%;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_center.setText(
            "【 注意力图片任务说明 】\n\n"
            "屏幕中央会先出现   +   注视点\n"
            "随后左右各出现一张图片（约 0.5 秒）\n\n"
            "图片消失后，其中一侧出现圆点   ●\n\n"
            "  ●  出现在左侧  ——  请按  ←  左方向键\n"
            "  ●  出现在右侧  ——  请按  →  右方向键\n\n"
            "请尽量   又快又准\n\n"
            "─────────────────────────────\n"
            "先进行几次练习，熟悉节奏"
        )
        self._lbl_hint.setText("")
        self._speak_then_do("dotprobe_start", self._start_practice)

    # ── 练习 ────────────────────────────────────────────────────

    def _start_practice(self):
        self.phase     = "practice"
        self.trial_idx = 0
        self._clear()
        self._lbl_center.setStyleSheet(
            f"color:{OK_COLOR}; font-size:30px; font-weight:bold;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_center.setText("练习开始")
        self._lbl_hint.setText(f"练习  1 / {len(self._practice)}")
        QTimer.singleShot(1200, self._run_trial)

    # ── 正式（配音完自动开始）───────────────────────────────────

    def _start_main(self):
        self.phase     = "main"
        self.trial_idx = 0
        self._clear()
        self._lbl_center.setStyleSheet(
            f"color:{FG_COLOR}; font-size:28px; font-weight:bold;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_center.setText("正式实验开始\n\n请集中注意力")
        self._lbl_hint.setText(f"试次  1 / {len(self._trials)}")
        self._speak_then_do("dotprobe_main_start", self._run_trial)

    # ── 试次核心 ────────────────────────────────────────────────

    def _run_trial(self):
        pool  = self._practice if self.phase == "practice" else self._trials
        total = len(pool)
        if self.trial_idx >= total:
            self._phase_done()
            return

        self._cur_trial = pool[self.trial_idx].copy()
        label = "练习" if self.phase == "practice" else "试次"
        self._lbl_hint.setText(f"{label}  {self.trial_idx + 1} / {total}")

        self._clear()
        self._lbl_center.setStyleSheet(
            f"color:{FG_COLOR}; font-size:60px; font-weight:bold;"
        )
        self._lbl_center.setText("+")
        QTimer.singleShot(FIXATION_MS, self._show_images)

    def _show_images(self):
        t = self._cur_trial
        self._lbl_center.setText("")
        self._set_img(self._lbl_left,  t["left_path"])
        self._set_img(self._lbl_right, t["right_path"])
        self._send_marker("STIM_FACE_ON", trial=self.trial_idx + 1,
                          phase=self.phase)
        QTimer.singleShot(IMAGE_MS, self._show_probe)

    def _show_probe(self):
        self._lbl_left.clear()
        self._lbl_right.clear()
        self._lbl_center.setText("")

        stim_side  = self._cur_trial["stim_side"]
        congruent  = random.random() < 0.5
        probe_side = stim_side if congruent else (
            "right" if stim_side == "left" else "left"
        )

        self._probe_side = probe_side
        self._probe_ts   = time.perf_counter()
        self._cur_trial.update({
            "probe_side": probe_side, "congruent": congruent
        })

        self._send_marker("STIM_FACE_OFF", trial=self.trial_idx + 1)
        self._send_marker("STIM_PROBE_ON", trial=self.trial_idx + 1,
                          side=probe_side)

        if probe_side == "left":
            self._lbl_left.setText("●")
        else:
            self._lbl_right.setText("●")

        self._probe_timer.start(PROBE_MAX_MS)

    def _on_timeout(self):
        self._send_marker("RESP_TIMEOUT", trial=self.trial_idx + 1)
        self._cur_trial.update({
            "response": None, "rt_ms": None,
            "correct": False,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self._finish_trial()

    def _handle_key(self, side: str):
        if self._probe_ts is None:
            return
        if self._probe_timer.isActive():
            self._probe_timer.stop()

        resp_marker = "RESP_KEY_LEFT" if side == "left" else "RESP_KEY_RIGHT"
        self._send_marker(resp_marker, trial=self.trial_idx + 1)

        rt_ms = round((time.perf_counter() - self._probe_ts) * 1000, 1)
        self._cur_trial.update({
            "response": side,
            "rt_ms":    rt_ms,
            "correct":  (side == self._probe_side),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self._probe_ts = None
        self._finish_trial()

    def _finish_trial(self):
        self._lbl_left.clear()
        self._lbl_right.clear()

        if self.phase == "main":
            t = self._cur_trial
            self.results.append({
                "trial":      self.trial_idx + 1,
                "neutral":    os.path.basename(t["neutral_path"]),
                "stimulus":   os.path.basename(t["stim_path"]),
                "stim_side":  t["stim_side"],
                "probe_side": t.get("probe_side", ""),
                "congruent":  t.get("congruent", ""),
                "response":   t.get("response", ""),
                "rt_ms":      t.get("rt_ms", ""),
                "correct":    t.get("correct", ""),
                "timestamp":  t.get("timestamp", ""),
            })

        self.trial_idx += 1
        QTimer.singleShot(ITI_MS, self._run_trial)

    def _phase_done(self):
        if self.phase == "practice":
            self._clear()
            self._lbl_center.setStyleSheet(
                f"color:{OK_COLOR}; font-size:26px; font-weight:bold;"
                "font-family:'Microsoft YaHei';"
            )
            self._lbl_center.setText("练习完成！\n\n即将开始正式实验…")
            self._lbl_hint.setText("")
            self.phase = "wait_main"
            self._speak_then_do("dotprobe_practice_done", self._start_main)

        elif self.phase == "main":
            path = self._save_results()
            self._clear()
            self._lbl_center.setStyleSheet(
                f"color:{FG_COLOR}; font-size:26px;"
                "font-family:'Microsoft YaHei';"
            )
            self._lbl_center.setText("Dot-probe 任务完成\n\n请稍等…")
            self.phase = "end"
            self._speak_then_do("dotprobe_end",
                                lambda: self._emit_finished(path))

    def _emit_finished(self, path: str):
        self.hide()
        self.finished.emit(path or "")

    # ── 工具 ────────────────────────────────────────────────────

    def _clear(self):
        self._lbl_center.setText("")
        self._lbl_left.clear()
        self._lbl_right.clear()
        self._probe_side = None
        self._probe_ts   = None

    def _set_img(self, lbl: QLabel, path: str):
        px = QPixmap(path)
        if not px.isNull():
            lbl.setPixmap(
                px.scaled(self._img_w, self._img_h,
                          Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            lbl.setText("[?]")

    def _save_results(self) -> str:
        if not self.results:
            return ""
        os.makedirs(os.path.dirname(self._out_path) or ".", exist_ok=True)
        with open(self._out_path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(self.results[0].keys()))
            writer.writeheader()
            writer.writerows(self.results)
        print(f"[DotProbeTask] 结果已保存：{self._out_path}")
        return self._out_path

    # ── 语音同步 ────────────────────────────────────────────────

    def _connect_voice(self):
        if self._voice is None:
            return
        try:
            self._voice.play_signal.connect(self._on_play_audio)
        except Exception:
            pass

    def _speak_then_do(self, voice_key: str, callback):
        """播放指定语音脚本，播放完毕后调用 callback"""
        if self._voice is None:
            QTimer.singleShot(500, callback)
            return
        try:
            from engine.voice import VOICE_SCRIPTS
            text = VOICE_SCRIPTS.get(voice_key, "")
            if not text:
                QTimer.singleShot(500, callback)
                return

            self._voice_pending_cb = callback
            self._voice.speak(text)
            fallback_ms = max(len(text) * 400, 30000)
            self._voice_fallback = QTimer(self)
            self._voice_fallback.setSingleShot(True)
            self._voice_fallback.timeout.connect(self._on_voice_fallback)
            self._voice_fallback.start(fallback_ms)
        except Exception:
            QTimer.singleShot(500, callback)

    def _on_play_audio(self, filepath: str):
        try:
            if self._player is None:
                self._player = QMediaPlayer(self)
                self._player.stateChanged.connect(self._on_player_state)
            self._player.setMedia(
                QMediaContent(QUrl.fromLocalFile(filepath))
            )
            self._player.play()
        except Exception:
            pass

    def _on_player_state(self, state):
        if state == QMediaPlayer.StoppedState and self._voice_pending_cb:
            cb = self._voice_pending_cb
            self._voice_pending_cb = None
            if hasattr(self, '_voice_fallback'):
                self._voice_fallback.stop()
            QTimer.singleShot(300, cb)

    def _on_voice_fallback(self):
        if self._voice_pending_cb:
            cb = self._voice_pending_cb
            self._voice_pending_cb = None
            cb()

    # ── 键盘（仅方向键 + Ctrl+C/D） ──────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        key  = event.key()
        mods = event.modifiers()

        if key == Qt.Key_C and (mods & Qt.ControlModifier):
            self._probe_timer.stop()
            self._save_results()
            self._emit_finished(self._out_path)
            return

        if key == Qt.Key_D and (mods & Qt.ControlModifier):
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return

        if self._probe_ts is not None:
            if key == Qt.Key_Left:
                self._handle_key("left")
            elif key == Qt.Key_Right:
                self._handle_key("right")
