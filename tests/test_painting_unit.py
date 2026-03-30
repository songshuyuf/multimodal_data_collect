"""
绘画欣赏任务 — 单元测试
========================
被动观看范式，患者无需按键，全程由 AI 配音引导。

实验流程
--------
  [说明屏 + AI 配音]  →  [30 张绘画逐一全屏展示]  →  [结束屏]

单张展示流程
-----------
  注视点(+)  1500ms → 画作全屏  6000ms → 画作消退(黑屏 500ms)

总时长约 4 分钟。

运行
----
  python -X utf8 tests/test_painting_unit.py

可选参数（直接修改文件顶部常量即可调整时序）：
  DISPLAY_MS  每张画的展示时长（默认 6000ms）
  FIXATION_MS 注视点时长（默认 1500ms）
  FADE_MS     黑屏过渡（默认 500ms）
"""

import os
import sys
import csv
import time

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QPixmap, QKeyEvent, QColor
from PyQt5.QtCore import pyqtSignal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── 路径 ─────────────────────────────────────────────────────────
IMG_DIR    = os.path.join(ROOT, "dataset", "painting", "emoart", "selected_30")
META_CSV   = os.path.join(ROOT, "dataset", "painting", "emoart", "selected_30.csv")
OUTPUT_DIR = os.path.join(ROOT, "dataset", "results")

# ── 时序参数（毫秒） ──────────────────────────────────────────────
FIXATION_MS = 1500   # 注视点
DISPLAY_MS  = 6000   # 画作展示
FADE_MS     = 500    # 画作消退黑屏

# ── 颜色 ─────────────────────────────────────────────────────────
BG_COLOR   = "#0a0a0a"
FG_COLOR   = "white"
HINT_COLOR = "#666666"
PROG_COLOR = "#aaaaaa"


# ── 加载元数据 ────────────────────────────────────────────────────
def load_paintings() -> list[dict]:
    paintings = []
    with open(META_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            path = os.path.join(IMG_DIR, row["dst_filename"])
            if os.path.exists(path):
                row["abs_path"] = path
                paintings.append(row)
            else:
                print(f"  [警告] 图片不存在：{path}")
    return sorted(paintings, key=lambda r: int(r["display_order"]))


# ── 主窗口 ────────────────────────────────────────────────────────
class PaintingWindow(QWidget):
    """绘画欣赏任务全屏窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("绘画欣赏任务")
        self.setStyleSheet(f"background-color:{BG_COLOR};")
        self.showFullScreen()

        self.paintings  = load_paintings()
        self.idx        = 0
        self.phase      = "instruction"
        self.results: list[dict] = []
        self._player    = None

        # 计时
        self._display_start = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)

        # 语音
        self._voice = None
        self._init_voice()

        self._build_ui()
        QTimer.singleShot(200, self._show_instruction)

    # ─────────────────────────────────────── UI 构建 ────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addStretch(1)

        # 画作 / 注视点 / 说明文字（共用一个 QLabel）
        self._lbl_img = QLabel()
        self._lbl_img.setAlignment(Qt.AlignCenter)
        self._lbl_img.setWordWrap(True)
        self._lbl_img.setStyleSheet(
            f"color:{FG_COLOR}; font-size:22px; line-height:190%;"
            "font-family:'Microsoft YaHei'; background:transparent;"
        )
        root.addWidget(self._lbl_img, stretch=10)

        root.addStretch(1)

        # 进度 / 提示条
        self._lbl_hint = QLabel()
        self._lbl_hint.setAlignment(Qt.AlignCenter)
        self._lbl_hint.setStyleSheet(
            f"color:{HINT_COLOR}; font-size:14px;"
            "font-family:'Microsoft YaHei';"
        )
        root.addWidget(self._lbl_hint)
        root.addSpacing(16)

    # ─────────────────────────────────────── 说明屏 ────────────

    def _show_instruction(self):
        self.phase = "instruction"
        self._timer.stop()
        self._lbl_img.setPixmap(QPixmap())   # 清空图片
        self._lbl_img.setText(
            "【 绘画欣赏任务 】\n\n"
            "接下来您将欣赏一系列绘画作品\n\n"
            "请放松心情，自然感受每一幅画带给您的感觉\n\n"
            "整个过程约需 4 分钟\n"
            "无需进行任何按键操作，只需专注欣赏\n\n"
            "──────────────────────────────\n\n"
            "准备好后，请按   空格键   开始"
        )
        self._lbl_hint.setText("按 空格键 开始   |   按 Esc 退出")

        self._speak(
            "接下来您将欣赏一系列绘画作品。"
            "请放松心情，自然感受每一幅画带给您的感觉。"
            "整个过程约需四分钟，无需进行任何按键操作，"
            "只需专注欣赏即可。"
            "准备好后，请按空格键开始。"
        )

    # ─────────────────────────────────────── 实验主流程 ────────

    def _start_experiment(self):
        self.phase = "running"
        self.idx   = 0
        self._speak("实验开始，请放松欣赏。")
        QTimer.singleShot(1800, self._run_painting)

    def _run_painting(self):
        if self.idx >= len(self.paintings):
            self._show_end()
            return

        p = self.paintings[self.idx]
        total = len(self.paintings)
        self._lbl_hint.setText(
            f"第  {self.idx + 1} / {total}  幅    "
            f"{p['group']}  ·  {p['emotion']}"
        )

        # 1. 注视点
        self._lbl_img.setPixmap(QPixmap())
        self._lbl_img.setStyleSheet(
            f"color:{FG_COLOR}; font-size:72px; font-weight:bold;"
            "background:transparent;"
        )
        self._lbl_img.setText("+")
        self._timer.timeout.disconnect() if self._timer.receivers(self._timer.timeout) else None
        self._timer.timeout.connect(lambda: self._show_painting(p))
        self._timer.start(FIXATION_MS)

    def _show_painting(self, p: dict):
        self._timer.stop()
        try:
            self._timer.timeout.disconnect()
        except Exception:
            pass

        # 加载并全屏缩放图片
        px = QPixmap(p["abs_path"])
        if not px.isNull():
            screen = QApplication.primaryScreen().geometry()
            scaled = px.scaled(
                screen.width(), screen.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._lbl_img.setText("")
            self._lbl_img.setStyleSheet("background:transparent;")
            self._lbl_img.setPixmap(scaled)
        else:
            self._lbl_img.setPixmap(QPixmap())
            self._lbl_img.setStyleSheet(f"color:{FG_COLOR}; font-size:24px;")
            self._lbl_img.setText(f"[图片加载失败]\n{p['dst_filename']}")

        self._display_start = time.perf_counter()

        self._timer.timeout.connect(lambda: self._after_painting(p))
        self._timer.start(DISPLAY_MS)

    def _after_painting(self, p: dict):
        self._timer.stop()
        try:
            self._timer.timeout.disconnect()
        except Exception:
            pass

        # 记录结果
        elapsed = round((time.perf_counter() - self._display_start) * 1000)
        self.results.append({
            "trial":         self.idx + 1,
            "filename":      p["dst_filename"],
            "group":         p["group"],
            "emotion":       p["emotion"],
            "valence":       p["valence"],
            "arousal":       p["arousal"],
            "style":         p["style"],
            "artist":        p["artist"],
            "display_ms":    elapsed,
            "timestamp":     time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # 黑屏过渡
        self._lbl_img.setPixmap(QPixmap())
        self._lbl_img.setText("")
        self.idx += 1
        self._timer.timeout.connect(self._run_painting)
        self._timer.start(FADE_MS)

    # ─────────────────────────────────────── 结束屏 ────────────

    def _show_end(self):
        self.phase = "end"
        self._save_results()
        self._lbl_img.setPixmap(QPixmap())
        self._lbl_img.setStyleSheet(
            f"color:{FG_COLOR}; font-size:26px; line-height:190%;"
            "font-family:'Microsoft YaHei'; background:transparent;"
        )
        self._lbl_img.setText(
            "绘画欣赏任务已完成\n\n"
            "感谢您的配合，请稍等片刻…\n\n"
            "按   Esc   退出"
        )
        self._lbl_hint.setText(f"共欣赏 {len(self.paintings)} 幅画作  ·  结果已保存")
        self._speak("绘画欣赏任务已完成，感谢您的配合，请稍作休息。")

    # ─────────────────────────────────────── 工具 ────────────

    def _save_results(self):
        if not self.results:
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ts   = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(OUTPUT_DIR, f"painting_{ts}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(self.results[0].keys()))
            w.writeheader()
            w.writerows(self.results)
        print(f"[Painting] 结果已保存：{path}")
        self._lbl_hint.setText(f"结果已保存：{path}")

    # ─────────────────────────────────────── 语音 ────────────

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

    # ─────────────────────────────────────── 键盘 ────────────

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key_Escape:
            self._timer.stop()
            self._save_results()
            QApplication.quit()
            return

        if key == Qt.Key_Space and self.phase == "instruction":
            self._start_experiment()


# ── 入口 ─────────────────────────────────────────────────────────
def main():
    paintings = load_paintings()

    print("=" * 55)
    print("  绘画欣赏任务  单元测试")
    print("=" * 55)
    print(f"  画作数量  : {len(paintings)} 张")
    print(f"  每张时长  : {DISPLAY_MS // 1000} 秒")
    print(f"  预计总时长: ~{len(paintings) * (DISPLAY_MS + FIXATION_MS + FADE_MS) // 60000} 分钟")
    print()

    from collections import Counter
    groups = Counter(p["group"] for p in paintings)
    for g, n in groups.items():
        print(f"  {g:<14} : {n} 张")
    print()
    print("  空格键  → 开始")
    print("  Esc    → 随时退出并保存")
    print()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = PaintingWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
