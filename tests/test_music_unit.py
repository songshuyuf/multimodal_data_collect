"""
音乐聆听任务 — 单元测试
========================
被动聆听范式，患者无需按键，AI 配音引导。

实验流程
--------
  [说明屏 + AI 配音]
  → [第1段 45s] → [休息 10s + AI 提示]
  → [第2段 45s] → [休息 10s + AI 提示]
  → ... × 6 段
  → [结束屏 + AI 配音]

选曲方案（方案 A，固定 6 首）
------------------------------
  正性/高唤醒 × 2   01_DEAM_Q1_HA_HV  20_Emotify_Q1_HA_HV
  正性/低唤醒 × 1   23_Emotify_Q3_LA_HV
  负性/高唤醒 × 2   17_DEAM_Q4_LA_LV  18_DEAM_Q4_LA_LV
  负性/低唤醒 × 1   16_DEAM_Q4_LA_LV

展示顺序（正负交替）：正高 → 负高 → 正高 → 负高 → 正低 → 负低

运行
----
  python -X utf8 tests/test_music_unit.py
"""

import os
import sys
import csv
import time

from PyQt5.QtWidgets import (QApplication, QWidget, QLabel,
                             QVBoxLayout, QProgressBar)
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── 路径 ─────────────────────────────────────────────────────────
MUSIC_ROOT = os.path.join(ROOT, "dataset", "music")
OUTPUT_DIR = os.path.join(ROOT, "dataset", "results")

# ── 时序参数（秒） ────────────────────────────────────────────────
PLAY_SECS = 45    # 每段播放时长
REST_SECS = 10    # 段间休息

# ── 固定选曲（方案 A，正负交替顺序） ─────────────────────────────
PLAYLIST = [
    # (segment, group,      valence, arousal, filename)
    (1, "正性/高唤醒", "正", "高", "积极/高唤醒/01_DEAM_Q1_HA_HV.mp3"),
    (2, "负性/高唤醒", "负", "高", "负性/高唤醒/17_DEAM_Q4_LA_LV.mp3"),
    (3, "正性/高唤醒", "正", "高", "积极/高唤醒/20_Emotify_Q1_HA_HV.mp3"),
    (4, "负性/高唤醒", "负", "高", "负性/高唤醒/18_DEAM_Q4_LA_LV.mp3"),
    (5, "正性/低唤醒", "正", "低", "积极/低唤醒/23_Emotify_Q3_LA_HV.mp3"),
    (6, "负性/低唤醒", "负", "低", "负性/低唤醒/16_DEAM_Q4_LA_LV.mp3"),
]

# ── 颜色 ─────────────────────────────────────────────────────────
BG_COLOR   = "#0a0a0a"
FG_COLOR   = "white"
POS_COLOR  = "#7ec8e3"   # 正性段 — 蓝白
NEG_COLOR  = "#c8a4d4"   # 负性段 — 紫
REST_COLOR = "#888888"
HINT_COLOR = "#555555"


# ── 主窗口 ────────────────────────────────────────────────────────
class MusicWindow(QWidget):
    """音乐聆听任务全屏窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("音乐聆听任务")
        self.setStyleSheet(f"background-color:{BG_COLOR};")
        self.showFullScreen()

        # 验证文件存在
        self.playlist = []
        for seg, group, val, aro, rel in PLAYLIST:
            abs_path = os.path.join(MUSIC_ROOT, rel)
            if os.path.exists(abs_path):
                self.playlist.append({
                    "segment": seg, "group": group,
                    "valence": val, "arousal": aro,
                    "filename": os.path.basename(rel),
                    "abs_path": abs_path,
                })
            else:
                print(f"  [警告] 文件不存在：{abs_path}")

        self.idx     = 0
        self.phase   = "instruction"   # instruction / playing / rest / end
        self.results: list[dict] = []

        # 音频播放器
        self._player = QMediaPlayer(self)
        self._player.stateChanged.connect(self._on_player_state)

        # 计时器（每秒刷新进度）
        self._tick   = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)
        self._elapsed = 0     # 当前阶段已过秒数
        self._target  = 0     # 当前阶段目标秒数

        # 语音
        self._voice      = None
        self._voice_player = None
        self._init_voice()

        self._build_ui()
        QTimer.singleShot(200, self._show_instruction)

    # ─────────────────────────────────────── UI 构建 ────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addStretch(3)

        # 段序 / 状态大字
        self._lbl_seg = QLabel()
        self._lbl_seg.setAlignment(Qt.AlignCenter)
        self._lbl_seg.setStyleSheet(
            f"color:{FG_COLOR}; font-size:72px; font-weight:bold;"
        )
        root.addWidget(self._lbl_seg)

        root.addSpacing(20)

        # 情绪分组标签
        self._lbl_group = QLabel()
        self._lbl_group.setAlignment(Qt.AlignCenter)
        self._lbl_group.setStyleSheet(
            f"color:{HINT_COLOR}; font-size:22px; font-family:'Microsoft YaHei';"
        )
        root.addWidget(self._lbl_group)

        root.addSpacing(30)

        # 说明文字（多行）
        self._lbl_info = QLabel()
        self._lbl_info.setAlignment(Qt.AlignCenter)
        self._lbl_info.setWordWrap(True)
        self._lbl_info.setStyleSheet(
            f"color:{FG_COLOR}; font-size:21px; line-height:185%;"
            "font-family:'Microsoft YaHei';"
        )
        root.addWidget(self._lbl_info)

        root.addSpacing(40)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setStyleSheet("""
            QProgressBar {
                background-color: #222222;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #5599cc;
                border-radius: 3px;
            }
        """)
        root.addWidget(self._progress)

        root.addSpacing(12)

        # 倒计时
        self._lbl_timer = QLabel("00:00 / 00:45")
        self._lbl_timer.setAlignment(Qt.AlignCenter)
        self._lbl_timer.setStyleSheet(
            f"color:{HINT_COLOR}; font-size:16px; font-family:monospace;"
        )
        root.addWidget(self._lbl_timer)

        root.addStretch(3)

        # 底部提示
        self._lbl_hint = QLabel()
        self._lbl_hint.setAlignment(Qt.AlignCenter)
        self._lbl_hint.setStyleSheet(
            f"color:{HINT_COLOR}; font-size:13px; font-family:'Microsoft YaHei';"
        )
        root.addWidget(self._lbl_hint)
        root.addSpacing(16)

    # ─────────────────────────────────────── 说明屏 ────────────

    def _show_instruction(self):
        self.phase = "instruction"
        self._player.stop()
        self._tick.stop()
        self._progress.setValue(0)

        total_min = (PLAY_SECS * 6 + REST_SECS * 5) // 60
        self._set_seg_label("♪", FG_COLOR)
        self._lbl_group.setText("")
        self._lbl_info.setStyleSheet(
            f"color:{FG_COLOR}; font-size:21px; line-height:185%;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_info.setText(
            "【 音乐聆听任务 】\n\n"
            "接下来您将聆听 6 段音乐，每段约 45 秒\n\n"
            "聆听时请戴好耳机，保持放松\n"
            "请尽量闭上眼睛，减少头部运动\n"
            "每段结束后会自动休息 10 秒\n\n"
            f"整个过程约需 {total_min} 分钟，无需任何按键\n\n"
            "──────────────────────────────\n\n"
            "准备好后，请按   空格键   开始"
        )
        self._lbl_timer.setText("")
        self._lbl_hint.setText("按 空格键 开始   |   按 Esc 退出")

        self._speak(
            "接下来您将聆听六段音乐，每段约四十五秒。"
            "聆听时请戴好耳机，保持放松，尽量闭上眼睛，减少头部运动。"
            f"整个过程约需{total_min}分钟，无需任何按键操作。"
            "准备好后，请按空格键开始。"
        )

    # ─────────────────────────────────────── 播放阶段 ────────

    def _start_experiment(self):
        self.idx = 0
        self._speak("实验开始，请闭上眼睛，专注聆听。")
        QTimer.singleShot(2000, self._play_segment)

    def _play_segment(self):
        if self.idx >= len(self.playlist):
            self._show_end()
            return

        song   = self.playlist[self.idx]
        self.phase = "playing"

        # 配色：正性蓝，负性紫
        color = POS_COLOR if song["valence"] == "正" else NEG_COLOR

        self._set_seg_label(f"♪  {song['segment']} / {len(self.playlist)}", color)
        self._lbl_group.setText(f"{song['group']}  ·  {song['arousal']}唤醒")
        self._lbl_group.setStyleSheet(
            f"color:{color}; font-size:22px; font-family:'Microsoft YaHei';"
        )
        self._lbl_info.setStyleSheet(
            f"color:{HINT_COLOR}; font-size:18px; font-family:'Microsoft YaHei';"
        )
        self._lbl_info.setText("请闭上眼睛，专注聆听")
        self._lbl_hint.setText(f"第 {song['segment']} / {len(self.playlist)} 段   ·   按 Esc 退出")

        # 更新进度条颜色
        bar_color = "#5599cc" if song["valence"] == "正" else "#9966cc"
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #222222; border: none; border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color}; border-radius: 3px;
            }}
        """)

        # 播放音乐
        self._player.setMedia(QMediaContent(QUrl.fromLocalFile(song["abs_path"])))
        self._player.play()

        # 启动计时
        self._elapsed = 0
        self._target  = PLAY_SECS
        self._segment_start = time.time()
        self._update_progress()
        self._tick.start()

    def _on_tick(self):
        self._elapsed += 1
        self._update_progress()

        if self._elapsed >= self._target:
            if self.phase == "playing":
                self._end_segment()
            elif self.phase == "rest":
                self._after_rest()

    def _update_progress(self):
        pct = int(self._elapsed / max(self._target, 1) * 100)
        self._progress.setValue(min(pct, 100))

        elapsed_s = self._elapsed
        target_s  = self._target
        em, es = divmod(elapsed_s, 60)
        tm, ts = divmod(target_s,  60)
        self._lbl_timer.setText(
            f"{em:02d}:{es:02d} / {tm:02d}:{ts:02d}"
        )

    def _end_segment(self):
        song = self.playlist[self.idx]
        actual_ms = round((time.time() - self._segment_start) * 1000)

        self._player.stop()
        self._tick.stop()

        # 记录结果
        self.results.append({
            "segment":    song["segment"],
            "filename":   song["filename"],
            "group":      song["group"],
            "valence":    song["valence"],
            "arousal":    song["arousal"],
            "play_ms":    actual_ms,
            "timestamp":  time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        self.idx += 1

        if self.idx >= len(self.playlist):
            self._show_end()
        else:
            self._start_rest()

    def _on_player_state(self, state):
        # 音乐自然播放完（短于45s时兜底）
        if state == QMediaPlayer.StoppedState and self.phase == "playing":
            if self._elapsed < self._target:
                # 等待计时器自然结束
                pass

    # ─────────────────────────────────────── 休息阶段 ────────

    def _start_rest(self):
        self.phase = "rest"
        next_song  = self.playlist[self.idx] if self.idx < len(self.playlist) else None

        self._set_seg_label("…", REST_COLOR)
        self._lbl_group.setText("休息片刻")
        self._lbl_group.setStyleSheet(
            f"color:{REST_COLOR}; font-size:22px; font-family:'Microsoft YaHei';"
        )
        hint = ""
        if next_song:
            hint = f"下一段：{next_song['group']}  ·  {next_song['arousal']}唤醒"
        self._lbl_info.setStyleSheet(
            f"color:{HINT_COLOR}; font-size:18px; font-family:'Microsoft YaHei';"
        )
        self._lbl_info.setText("请稍作休息，保持放松")
        self._lbl_hint.setText(hint)
        self._progress.setStyleSheet("""
            QProgressBar { background-color:#222; border:none; border-radius:3px; }
            QProgressBar::chunk { background-color:#555; border-radius:3px; }
        """)

        self._elapsed = 0
        self._target  = REST_SECS
        self._update_progress()
        self._tick.start()
        self._speak("请稍作休息，保持放松，马上继续。")

    def _after_rest(self):
        self._tick.stop()
        self._play_segment()

    # ─────────────────────────────────────── 结束屏 ────────────

    def _show_end(self):
        self.phase = "end"
        self._player.stop()
        self._tick.stop()
        self._save_results()

        self._set_seg_label("✓", FG_COLOR)
        self._lbl_group.setText("")
        self._lbl_info.setStyleSheet(
            f"color:{FG_COLOR}; font-size:24px; line-height:185%;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_info.setText(
            "音乐聆听任务已完成\n\n"
            "感谢您的配合，请稍作休息\n\n"
            "按   Esc   退出"
        )
        self._lbl_timer.setText("")
        self._lbl_hint.setText(f"共聆听 {len(self.results)} 段音乐  ·  结果已保存")
        self._speak("音乐聆听任务已完成，感谢您的配合，请稍作休息。")

    # ─────────────────────────────────────── 工具 ────────────

    def _set_seg_label(self, text: str, color: str):
        self._lbl_seg.setText(text)
        self._lbl_seg.setStyleSheet(
            f"color:{color}; font-size:72px; font-weight:bold;"
        )

    def _save_results(self):
        if not self.results:
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ts   = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(OUTPUT_DIR, f"music_{ts}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(self.results[0].keys()))
            w.writeheader()
            w.writerows(self.results)
        print(f"[Music] 结果已保存：{path}")
        self._lbl_hint.setText(f"结果已保存：{path}")

    # ─────────────────────────────────────── 语音 ────────────

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
            self._voice_player.setMedia(
                QMediaContent(QUrl.fromLocalFile(filepath))
            )
            self._voice_player.play()
        except Exception:
            pass

    # ─────────────────────────────────────── 键盘 ────────────

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key_Escape:
            self._player.stop()
            self._tick.stop()
            self._save_results()
            QApplication.quit()
            return

        if key == Qt.Key_Space and self.phase == "instruction":
            self._start_experiment()


# ── 入口 ─────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  音乐聆听任务  单元测试")
    print("=" * 55)

    # 预检文件
    all_ok = True
    for seg, group, val, aro, rel in PLAYLIST:
        path = os.path.join(MUSIC_ROOT, rel)
        ok   = os.path.exists(path)
        flag = "[OK]" if ok else "[缺失]"
        print(f"  {flag}  第{seg}段  {group:<12}  {os.path.basename(rel)}")
        if not ok:
            all_ok = False

    if not all_ok:
        print("\n  [错误] 有音频文件缺失，请检查路径后重试")
        return

    total_s = PLAY_SECS * 6 + REST_SECS * 5
    print(f"\n  每段时长 : {PLAY_SECS}s  间隔 : {REST_SECS}s")
    print(f"  预计总时长: {total_s // 60} 分 {total_s % 60} 秒")
    print()
    print("  空格键  → 开始")
    print("  Esc    → 随时退出并保存")
    print()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MusicWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
