"""
音乐聆听任务 Widget（集成版）
"""

import os, csv, time

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QProgressBar
from PyQt5.QtCore    import Qt, QTimer, QUrl
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

from engine.paradigms.base import BaseParadigmWidget

BG       = "#0a0a0a"
WHITE    = "#f0f0f0"
BLUE     = "#7ec8e3"
PURPLE   = "#c8a4d4"
REST_CLR = "#888888"
GRAY     = "#333333"
LGRAY    = "#666666"


class MusicTask(BaseParadigmWidget):
    """
    music_list : list of dict，每项含 {path, filename, group, valence, arousal}
    params     : experiment_config task params（clip_duration ms, isi ms）
    """

    def __init__(self, music_list: list, params: dict,
                 output_path: str, voice=None, parent=None):
        super().__init__(output_path, parent)
        self._music_list   = music_list
        self._params       = params
        self._voice        = voice
        self._voice_player = None

        self._play_ms  = params.get('clip_duration', 45000)
        self._rest_ms  = params.get('isi', 10000)

        self._idx      = 0
        self._phase    = "intro"
        self._elapsed  = 0
        self._target   = 0
        self._seg_start = 0.0
        self._results: list[dict] = []

        self.setStyleSheet(f"background:{BG};")
        self._build_ui()

        self._music_player = QMediaPlayer(self)
        self._music_player.stateChanged.connect(self._on_music_state)

        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)

    # ── UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch(2)

        self._lbl_seg = QLabel()
        self._lbl_seg.setAlignment(Qt.AlignCenter)
        self._lbl_seg.setStyleSheet(
            f"color:{WHITE}; font-size:72px; font-weight:bold;"
        )
        lay.addWidget(self._lbl_seg)

        lay.addSpacing(20)

        self._lbl_group = QLabel()
        self._lbl_group.setAlignment(Qt.AlignCenter)
        self._lbl_group.setStyleSheet(
            f"color:{LGRAY}; font-size:22px; font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_group)

        lay.addSpacing(30)

        self._lbl_info = QLabel()
        self._lbl_info.setAlignment(Qt.AlignCenter)
        self._lbl_info.setWordWrap(True)
        self._lbl_info.setStyleSheet(
            f"color:{WHITE}; font-size:21px; font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_info)

        lay.addSpacing(40)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        self._bar.setStyleSheet(
            "QProgressBar{background:#222;border:none;border-radius:3px;}"
            "QProgressBar::chunk{background:#5599cc;border-radius:3px;}"
        )
        lay.addWidget(self._bar)

        lay.addSpacing(12)

        self._lbl_timer = QLabel()
        self._lbl_timer.setAlignment(Qt.AlignCenter)
        self._lbl_timer.setStyleSheet(
            f"color:{LGRAY}; font-size:16px; font-family:monospace;"
        )
        lay.addWidget(self._lbl_timer)

        lay.addStretch(3)

        self._lbl_hint = QLabel()
        self._lbl_hint.setAlignment(Qt.AlignCenter)
        self._lbl_hint.setFixedHeight(30)
        self._lbl_hint.setStyleSheet(
            f"background:{GRAY}; color:{LGRAY}; font-size:12px;"
            "font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_hint)

    # ── 启动/停止 ────────────────────────────────────────────────

    def _do_start(self):
        self._show_intro()

    def _do_stop(self):
        self._tick.stop()
        self._music_player.stop()
        self._save_results()

    # ── 流程 ────────────────────────────────────────────────────

    def _show_intro(self):
        self._phase   = "intro"
        self._elapsed = 0
        self._target  = 5
        total_min = (self._play_ms // 1000 * len(self._music_list)
                     + self._rest_ms // 1000 * (len(self._music_list) - 1)) // 60
        self._lbl_seg.setText("♪")
        self._lbl_group.setText("")
        self._lbl_info.setText(
            f"【 音乐聆听任务 】\n\n"
            f"接下来您将聆听 {len(self._music_list)} 段音乐，每段约"
            f" {self._play_ms // 1000} 秒\n\n"
            "聆听时请戴好耳机，保持放松，尽量闭上眼睛\n\n"
            f"整个过程约需 {total_min} 分钟，无需任何按键操作"
        )
        self._lbl_hint.setText(f"共 {len(self._music_list)} 段")
        self._bar.setValue(0)
        self._lbl_timer.setText("")
        self._speak_then(
            self._voice,
            f"接下来您将聆听{len(self._music_list)}段音乐。"
            "请戴好耳机，保持放松，尽量闭上眼睛。"
            "整个过程无需任何按键操作。",
            self._begin_segments,
        )

    def _begin_segments(self):
        self._idx = 0
        self._start_segment()

    def _start_segment(self):
        if self._idx >= len(self._music_list):
            self._show_end()
            return

        m = self._music_list[self._idx]
        self._phase     = "playing"
        self._elapsed   = 0
        self._target    = self._play_ms // 1000
        self._seg_start = time.time()

        val   = m.get('valence', '')
        color = BLUE if str(val).startswith('正') or str(val) in ('高', 'H') else PURPLE
        self._lbl_seg.setText(
            f"<span style='color:{color};'>♪  {self._idx + 1} / {len(self._music_list)}</span>"
        )
        group = m.get('group', m.get('genre', ''))
        self._lbl_group.setText(group)
        self._lbl_group.setStyleSheet(
            f"color:{color}; font-size:22px; font-family:'Microsoft YaHei';"
        )
        self._lbl_info.setText("请闭上眼睛，专注聆听")
        self._lbl_hint.setText(f"第 {self._idx + 1} / {len(self._music_list)} 段")
        self._bar.setStyleSheet(
            "QProgressBar{background:#222;border:none;border-radius:3px;}"
            f"QProgressBar::chunk{{background:{color};border-radius:3px;}}"
        )

        self._send_marker("STIM_MUSIC_ON", segment=self._idx + 1,
                          group=m.get('group', ''))

        path = m.get('path', '')
        if os.path.exists(path):
            self._music_player.setMedia(
                QMediaContent(QUrl.fromLocalFile(os.path.abspath(path)))
            )
            self._music_player.play()
        else:
            print(f"  [Music] 文件不存在：{path}")

        self._tick.start()

    def _start_rest(self):
        self._phase   = "rest"
        self._elapsed = 0
        self._target  = self._rest_ms // 1000
        self._music_player.stop()

        self._lbl_seg.setText(f"<span style='color:{REST_CLR};'>…</span>")
        self._lbl_group.setText("休息片刻")
        self._lbl_group.setStyleSheet(
            f"color:{REST_CLR}; font-size:22px; font-family:'Microsoft YaHei';"
        )
        self._lbl_info.setText("请稍作休息，保持放松")
        self._bar.setStyleSheet(
            "QProgressBar{background:#222;border:none;border-radius:3px;}"
            "QProgressBar::chunk{background:#555;border-radius:3px;}"
        )
        self._speak("请稍作休息，保持放松，马上继续。")
        self._tick.start()

    def _show_end(self):
        self._phase = "end"
        self._tick.stop()
        self._music_player.stop()
        self._lbl_seg.setText("✓")
        self._lbl_group.setText("")
        self._lbl_info.setText("音乐聆听任务已完成\n\n感谢您的配合，请稍作休息")
        self._bar.setValue(100)
        self._lbl_timer.setText("")
        self._lbl_hint.setText(f"共 {len(self._results)} 段")
        self._speak_then(
            self._voice,
            "音乐聆听任务已完成，感谢您的配合，请稍作休息。",
            self._force_finish,
        )

    def _on_tick(self):
        self._elapsed += 1
        pct = int(self._elapsed / max(self._target, 1) * 100)
        self._bar.setValue(min(pct, 100))
        rm, rs = divmod(max(self._target - self._elapsed, 0), 60)
        tm, ts = divmod(self._target, 60)
        self._lbl_timer.setText(f"{rm:02d}:{rs:02d} / {tm:02d}:{ts:02d}")

        if self._elapsed < self._target:
            return
        self._tick.stop()

        if self._phase == "playing":
            self._send_marker("STIM_MUSIC_OFF", segment=self._idx + 1)
            self._results.append({
                "segment":   self._idx + 1,
                "filename":  os.path.basename(self._music_list[self._idx].get('path', '')),
                "group":     self._music_list[self._idx].get('group', ''),
                "valence":   self._music_list[self._idx].get('valence', ''),
                "arousal":   self._music_list[self._idx].get('arousal', ''),
                "play_ms":   round((time.time() - self._seg_start) * 1000),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            self._idx += 1
            if self._idx >= len(self._music_list):
                self._show_end()
            else:
                self._start_rest()

        elif self._phase == "rest":
            self._start_segment()

    def _on_music_state(self, state):
        pass   # 计时器控制时长，不依赖播放状态

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
