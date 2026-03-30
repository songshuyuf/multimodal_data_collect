"""
Dot-probe 注意偏向任务 — 单元测试
==================================
完整演示标准 Dot-probe 范式，独立运行，不依赖主项目采集代码。

实验流程
--------
  [说明屏 + AI 配音]  →  [5 次练习（无反馈）]
  →  [200 次正式试次]  →  [结果保存 CSV]

单次试次流程
-----------
  注视点 (+)  500ms
  → 左右各一张图片    500ms
  → 图片消失，探针 ● 出现在左 / 右  最多 1500ms
  → 患者按 ← / → 方向键
  → 试次间隔 (ITI)    1000ms

运行
----
  python -X utf8 tests/test_dotprobe_unit.py
"""

import os
import sys
import csv
import time
import random

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QPixmap, QKeyEvent

# 把项目根目录加入 path，以便复用 voice_guidance
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── 路径 & 参数配置 ─────────────────────────────────────────────
STIM_BASE   = os.path.join(ROOT, "dataset", "picture", "Stimulation", "classified")
NEUTRAL_DIR = os.path.join(STIM_BASE, "neutral")
NEG_DIR     = os.path.join(STIM_BASE, "stimulus_neg")
POS_DIR     = os.path.join(STIM_BASE, "stimulus_pos")
OUTPUT_DIR  = os.path.join(ROOT, "dataset", "results")

# 实验时序（毫秒）
FIXATION_MS  = 500
IMAGE_MS     = 500
PROBE_MAX_MS = 1500
ITI_MS       = 1000

# 试次数
N_PRACTICE = 5
N_MAIN     = 200

# 图片显示尺寸（px）
IMG_W, IMG_H = 300, 300

# 颜色
BG_COLOR     = "#111111"
TEXT_COLOR   = "white"
HINT_COLOR   = "#999999"
CORRECT_FG   = "#88ff88"


# ── 工具函数 ────────────────────────────────────────────────────
def _imgs(folder: str) -> list[str]:
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.splitext(f.lower())[1] in exts]


def _make_trials(neutrals: list, stims: list, n: int) -> list[dict]:
    """生成 n 个试次（允许重复使用图片）"""
    neu_pool  = (neutrals * (n // max(len(neutrals), 1) + 2))[:n]
    stim_pool = (stims    * (n // max(len(stims),    1) + 2))[:n]
    random.shuffle(neu_pool)
    random.shuffle(stim_pool)

    trials = []
    for i in range(n):
        stim_side = random.choice(["left", "right"])
        stim_p    = stim_pool[i]
        neu_p     = neu_pool[i]
        trials.append({
            "neutral_path": neu_p,
            "stim_path":    stim_p,
            "stim_side":    stim_side,
            "left_path":    stim_p if stim_side == "left" else neu_p,
            "right_path":   neu_p  if stim_side == "left" else stim_p,
        })
    return trials


# ── 主窗口 ──────────────────────────────────────────────────────
class DotProbeWindow(QWidget):
    """Dot-probe 实验主窗口（全屏黑底）"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dot-probe 注意偏向任务")
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self.showFullScreen()

        # ── 加载图片 ──────────────────────────────────────────
        self._neutrals = _imgs(NEUTRAL_DIR)
        self._stims    = _imgs(NEG_DIR) + _imgs(POS_DIR)

        if not self._neutrals or not self._stims:
            self._fatal("找不到图片目录，请先运行 classify_images.py\n\n"
                        f"  neutral   : {NEUTRAL_DIR}\n"
                        f"  stimulus  : {NEG_DIR}\n             {POS_DIR}")
            return

        all_stims = self._stims[:]
        random.shuffle(self._neutrals)
        random.shuffle(all_stims)

        self._prac_trials = _make_trials(self._neutrals, all_stims, N_PRACTICE)
        self._main_trials = _make_trials(self._neutrals, all_stims, N_MAIN)

        # ── 状态 ──────────────────────────────────────────────
        self.phase        = "instruction"
        self.trial_idx    = 0
        self.results: list[dict] = []

        self._cur_trial   = {}
        self._probe_side  = None
        self._probe_ts    = None          # perf_counter() 探针出现时刻
        self._probe_timer = QTimer(self)
        self._probe_timer.setSingleShot(True)
        self._probe_timer.timeout.connect(self._on_timeout)

        # ── AI 语音 ───────────────────────────────────────────
        self._player = None
        self._voice  = None
        self._init_voice()

        # ── UI ────────────────────────────────────────────────
        self._build_ui()
        QTimer.singleShot(200, self._show_instruction)

    # ─────────────────────────────────────────── 布局构建 ──────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addStretch(2)

        # 中央说明 / 注视点文字
        self._lbl_center = QLabel()
        self._lbl_center.setAlignment(Qt.AlignCenter)
        self._lbl_center.setWordWrap(True)
        self._lbl_center.setStyleSheet(
            f"color:{TEXT_COLOR}; font-size:52px; font-weight:bold;"
            "font-family:'Microsoft YaHei';"
        )
        root.addWidget(self._lbl_center)

        root.addSpacing(30)

        # 图片行 + 探针共用同一位置（用 QLabel 叠加）
        img_row = QHBoxLayout()
        img_row.setAlignment(Qt.AlignCenter)
        img_row.setSpacing(100)

        self._lbl_left  = self._make_cell()
        self._lbl_right = self._make_cell()
        img_row.addWidget(self._lbl_left)
        img_row.addWidget(self._lbl_right)
        root.addLayout(img_row)

        root.addStretch(2)

        # 底部提示
        self._lbl_hint = QLabel()
        self._lbl_hint.setAlignment(Qt.AlignCenter)
        self._lbl_hint.setStyleSheet(
            f"color:{HINT_COLOR}; font-size:15px;"
            "font-family:'Microsoft YaHei';"
        )
        root.addWidget(self._lbl_hint)
        root.addSpacing(18)

    def _make_cell(self) -> QLabel:
        lbl = QLabel()
        lbl.setFixedSize(IMG_W, IMG_H)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background:transparent; color:white; font-size:60px;")
        return lbl

    # ─────────────────────────────────────────── 说明屏 ────────

    def _show_instruction(self):
        self.phase = "instruction"
        self._clear()

        self._lbl_center.setStyleSheet(
            f"color:{TEXT_COLOR}; font-size:21px; line-height:200%;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_center.setText(
            "【 注意力图片任务说明 】\n\n"
            "屏幕中央会先出现   +   注视点\n"
            "随后左右各出现一张图片（约 0.5 秒）\n\n"
            "图片消失后，其中一侧出现圆点   ●\n\n"
            "    圆点在  左边  →  请按   ←   方向键\n"
            "    圆点在  右边  →  请按   →   方向键\n\n"
            "请尽量   又快又准\n\n"
            "─────────────────────────────\n"
            "先进行几次练习，熟悉节奏\n\n"
            "准备好后，按   空格键   开始练习"
        )
        self._lbl_hint.setText("按 空格键 继续   |   按 Esc 退出")

        self._speak(
            "下面进行注意力图片任务。"
            "屏幕会先出现一个加号注视点，然后左右各出现一张图片。"
            "图片消失后，屏幕某一侧会出现一个圆点。"
            "圆点在左边，请按左方向键；圆点在右边，请按右方向键。"
            "请尽量又快又准。接下来先进行几次练习，熟悉节奏。"
            "准备好后，请按空格键。"
        )

    # ─────────────────────────────────────────── 练习阶段 ──────

    def _start_practice(self):
        self.phase     = "practice"
        self.trial_idx = 0
        self._clear()
        self._lbl_center.setStyleSheet(
            f"color:{CORRECT_FG}; font-size:30px; font-weight:bold;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_center.setText("练习开始")
        self._lbl_hint.setText(f"练习  1 / {N_PRACTICE}")
        QTimer.singleShot(1200, self._run_trial)

    # ─────────────────────────────────────────── 正式阶段 ──────

    def _start_main(self):
        self.phase     = "main"
        self.trial_idx = 0
        self._clear()
        self._lbl_center.setStyleSheet(
            f"color:{TEXT_COLOR}; font-size:28px; font-weight:bold;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_center.setText("正式实验开始\n\n请集中注意力")
        self._lbl_hint.setText(f"试次  1 / {N_MAIN}")
        self._speak("练习结束，正式实验现在开始，请集中注意力。")
        QTimer.singleShot(2200, self._run_trial)

    # ─────────────────────────────────────────── 试次核心 ──────

    def _run_trial(self):
        trials = self._prac_trials if self.phase == "practice" else self._main_trials
        if self.trial_idx >= len(trials):
            self._phase_done()
            return

        self._cur_trial = trials[self.trial_idx].copy()

        total = N_PRACTICE if self.phase == "practice" else N_MAIN
        label = "练习" if self.phase == "practice" else "试次"
        self._lbl_hint.setText(f"{label}  {self.trial_idx + 1} / {total}")

        # 注视点
        self._clear()
        self._lbl_center.setStyleSheet(
            f"color:{TEXT_COLOR}; font-size:60px; font-weight:bold;"
        )
        self._lbl_center.setText("+")
        QTimer.singleShot(FIXATION_MS, self._show_images)

    def _show_images(self):
        t = self._cur_trial
        self._lbl_center.setText("")
        self._set_img(self._lbl_left,  t["left_path"])
        self._set_img(self._lbl_right, t["right_path"])
        QTimer.singleShot(IMAGE_MS, self._show_probe)

    def _show_probe(self):
        # 清除图片
        self._lbl_left.clear()
        self._lbl_right.clear()
        self._lbl_center.setText("")

        # 探针位置：congruent（刺激侧）或 incongruent（对侧），各 50%
        stim_side = self._cur_trial["stim_side"]
        congruent = random.random() < 0.5
        probe_side = stim_side if congruent else (
            "right" if stim_side == "left" else "left"
        )
        self._probe_side = probe_side
        self._probe_ts   = time.perf_counter()
        self._cur_trial["probe_side"] = probe_side
        self._cur_trial["congruent"]  = congruent

        # 在对应 cell 显示探针
        if probe_side == "left":
            self._lbl_left.setText("●")
            self._lbl_right.setText("")
        else:
            self._lbl_left.setText("")
            self._lbl_right.setText("●")

        self._probe_timer.start(PROBE_MAX_MS)

    def _on_timeout(self):
        self._cur_trial["response"] = None
        self._cur_trial["rt_ms"]    = None
        self._cur_trial["correct"]  = False
        self._cur_trial["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._finish_trial()

    def _handle_key(self, side: str):
        """方向键响应"""
        if self._probe_ts is None:
            return
        if self._probe_timer.isActive():
            self._probe_timer.stop()

        rt_ms = round((time.perf_counter() - self._probe_ts) * 1000, 1)
        self._cur_trial["response"]  = side
        self._cur_trial["rt_ms"]     = rt_ms
        self._cur_trial["correct"]   = (side == self._probe_side)
        self._cur_trial["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
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
                f"color:{CORRECT_FG}; font-size:26px; font-weight:bold;"
                "font-family:'Microsoft YaHei';"
            )
            self._lbl_center.setText("练习完成！\n\n准备好后，按   空格键   开始正式实验")
            self._lbl_hint.setText("按 空格键 继续   |   按 Esc 退出")
            self.phase = "wait_main"
            self._speak("练习已完成。准备好后，请按空格键开始正式实验。")

        elif self.phase == "main":
            self._save_results()
            self._clear()
            self._lbl_center.setStyleSheet(
                f"color:{TEXT_COLOR}; font-size:26px;"
                "font-family:'Microsoft YaHei';"
            )
            self._lbl_center.setText("实验完成\n\n感谢您的参与！\n\n按 Esc 退出")
            self._lbl_hint.setText(f"结果已保存至：{OUTPUT_DIR}")
            self.phase = "end"
            self._speak("实验已完成，非常感谢您的配合！")

    # ─────────────────────────────────────────── 工具 ──────────

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
                px.scaled(IMG_W, IMG_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            lbl.setText("[?]")

    def _fatal(self, msg: str):
        self._lbl_center = QLabel(msg, self)
        self._lbl_center.setWordWrap(True)
        self._lbl_center.setAlignment(Qt.AlignCenter)
        self._lbl_center.setStyleSheet("color:red; font-size:20px; font-family:'Microsoft YaHei';")
        layout = QVBoxLayout(self)
        layout.addWidget(self._lbl_center)

    def _save_results(self):
        if not self.results:
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ts   = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(OUTPUT_DIR, f"dotprobe_{ts}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(self.results[0].keys()))
            writer.writeheader()
            writer.writerows(self.results)
        print(f"[Dot-probe] 结果已保存：{path}")

    # ─────────────────────────────────────────── 语音 ──────────

    def _init_voice(self):
        try:
            from engine.voice import VoiceGuidance
            self._voice = VoiceGuidance(parent=self)
            self._voice.play_signal.connect(self._on_play_audio)
        except Exception:
            pass

    def _speak(self, text: str):
        if self._voice:
            self._voice.speak(text)

    def _on_play_audio(self, filepath: str):
        try:
            from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
            if self._player is None:
                self._player = QMediaPlayer(self)
            self._player.setMedia(QMediaContent(QUrl.fromLocalFile(filepath)))
            self._player.play()
        except Exception:
            pass

    # ─────────────────────────────────────────── 键盘 ──────────

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key_Escape:
            self._probe_timer.stop()
            self._save_results()
            QApplication.quit()
            return

        if key == Qt.Key_Space:
            if self.phase == "instruction":
                self._start_practice()
            elif self.phase == "wait_main":
                self._start_main()
            return

        if self._probe_ts is not None:
            if key == Qt.Key_Left:
                self._handle_key("left")
            elif key == Qt.Key_Right:
                self._handle_key("right")


# ── 入口 ────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  Dot-probe 注意偏向任务  单元测试")
    print("=" * 55)

    for folder, label in [
        (NEUTRAL_DIR, "中性图"),
        (NEG_DIR,     "负性刺激"),
        (POS_DIR,     "正性刺激"),
    ]:
        n = len(_imgs(folder))
        print(f"  {label:8s}：{n:3d} 张  ({folder})")

    print()
    print("  空格键  → 继续/开始")
    print("  ← →    → 响应探针")
    print("  Esc    → 退出并保存")
    print()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = DotProbeWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
