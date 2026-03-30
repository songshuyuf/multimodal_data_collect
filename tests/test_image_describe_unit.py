"""
图像描述任务 — 单元测试
========================
全屏展示 4 张图片，患者口头描述所见内容，全程麦克风录音由系统统一管理。

实验流程
--------
  [指导语屏 + AI 配音，10s 自动进入]
  → [图1 正性 40s] → [5s 过渡]
  → [图2 中性 40s] → [5s 过渡]
  → [图3 正性 40s] → [5s 过渡]
  → [图4 中性 40s]
  → [结束屏 + AI 配音]
  总计约 3 分 5 秒

图片依据
--------
  Dan-Glauser, E.S. & Scherer, K.R. (2011).
  The Geneva affective picture database (GAPED): a new 730-picture database
  focusing on valence and normative significance.
  European Journal of Psychophysiology, 48, 395-411.

  P 类（正性）× 2：评估正性情绪反应（MDD 患者反应减弱）
  N 类（中性）× 2：评估负性认知偏向（MDD 患者对中性内容倾向负性解读）

运行
----
  python -X utf8 tests/test_image_describe_unit.py
"""

import os
import sys
import csv
import time

from PyQt5.QtWidgets import (QApplication, QWidget, QLabel,
                             QVBoxLayout, QStackedLayout)
from PyQt5.QtCore    import Qt, QTimer, QUrl
from PyQt5.QtGui     import QPixmap
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

IMG_DIR    = os.path.join(ROOT, "dataset", "picture", "description")
OUTPUT_DIR = os.path.join(ROOT, "dataset", "results")

# ── 时序（秒） ────────────────────────────────────────────────────
INTRO_SECS      = 10
DISPLAY_SECS    = 40
TRANSITION_SECS = 5

# ── 图片列表（从选图脚本生成的 selected_4.csv 读取） ──────────────
def _load_images():
    csv_path = os.path.join(IMG_DIR, "selected_4.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"未找到选图元数据，请先运行：python select_describe_images.py\n{csv_path}"
        )
    imgs = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            path = os.path.join(IMG_DIR, row["filename"])
            imgs.append({
                "order":    int(row["order"]),
                "filename": row["filename"],
                "original": row["original"],
                "valence":  row["valence"],
                "path":     path,
            })
    imgs.sort(key=lambda x: x["order"])
    return imgs

# ── 配色 ─────────────────────────────────────────────────────────
BG    = "#000000"
WHITE = "#f0f0f0"
GRAY  = "#444444"
LGRAY = "#888888"


class ImageDescribeWindow(QWidget):
    """图像描述任务全屏窗口"""

    def __init__(self, images: list):
        super().__init__()
        self.images   = images
        self.img_idx  = 0
        self.phase    = "intro"
        self._elapsed = 0
        self._target  = 0
        self._img_start_ts: float = 0.0
        self.results: list[dict] = []

        self.setWindowTitle("图像描述任务")
        self.setStyleSheet(f"background:{BG};")
        self.showFullScreen()

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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 图片占满全屏
        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignCenter)
        self._img_lbl.setStyleSheet(f"background:{BG};")
        outer.addWidget(self._img_lbl, stretch=1)

        # 底部信息条
        self._bar_lbl = QLabel()
        self._bar_lbl.setAlignment(Qt.AlignCenter)
        self._bar_lbl.setFixedHeight(44)
        self._bar_lbl.setStyleSheet(
            f"background:#111; color:{LGRAY}; font-size:14px;"
            "font-family:'Microsoft YaHei';"
        )
        outer.addWidget(self._bar_lbl)

    def _set_text_mode(self, title: str, body: str):
        """切换为文字模式（指导语/过渡/结束）"""
        self._img_lbl.setPixmap(QPixmap())
        self._img_lbl.setStyleSheet(f"background:{BG};")
        self._img_lbl.setText(
            f"<div style='color:#f0f0f0; font-size:26px; "
            f"font-family:Microsoft YaHei; line-height:200%; text-align:center;'>"
            f"<b style='color:#f5c842; font-size:32px;'>{title}</b><br><br>"
            f"{body}</div>"
        )

    def _set_image_mode(self, img_path: str):
        """切换为图片全屏模式"""
        self._img_lbl.setText("")
        pix = QPixmap(img_path)
        if pix.isNull():
            self._img_lbl.setStyleSheet(f"background:{BG};")
            self._img_lbl.setText(
                f"<div style='color:#888; font-size:20px;'>[图片加载失败]<br>{img_path}</div>"
            )
        else:
            screen = QApplication.primaryScreen().size()
            scaled = pix.scaled(screen.width(), screen.height() - 44,
                                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._img_lbl.setStyleSheet(f"background:{BG};")
            self._img_lbl.setPixmap(scaled)

    # ─────────────────────────────────── 指导语 ─────────────────────

    def _show_intro(self):
        self.phase    = "intro"
        self._elapsed = 0
        self._target  = INTRO_SECS

        self._set_text_mode(
            "图像描述任务",
            "接下来，屏幕会依次展示 4 张图片<br><br>"
            "请用语言描述您看到的内容，以及您的感受<br><br>"
            "每张图片展示 40 秒，倒计时结束后自动切换<br><br>"
            "保持自然，放松表达即可"
        )
        self._bar_lbl.setText("按 Esc 退出")
        self._update_bar()
        self._tick.start()

        self._speak(
            "接下来将展示四张图片，请用语言描述您看到的内容，以及您的感受。"
            "每张图片展示四十秒，倒计时结束后自动切换，保持自然放松即可。"
        )

    # ─────────────────────────────────── 图片展示 ───────────────────

    def _show_image(self):
        img = self.images[self.img_idx]
        self.phase        = "displaying"
        self._elapsed     = 0
        self._target      = DISPLAY_SECS
        self._img_start_ts = time.time()

        self._set_image_mode(img["path"])
        self._update_bar()
        self._tick.start()

        self._speak("请描述您看到的内容和感受。")

    # ─────────────────────────────────── 过渡 ───────────────────────

    def _show_transition(self):
        self.phase    = "transition"
        self._elapsed = 0
        self._target  = TRANSITION_SECS

        next_num = self.img_idx + 1
        self._set_text_mode("", f"下一张图片即将展示（第 {next_num + 1} / {len(self.images)} 张）…")
        self._update_bar()
        self._tick.start()

    # ─────────────────────────────────── 结束 ───────────────────────

    def _show_end(self):
        self.phase = "end"
        self._tick.stop()
        self._save_results()

        self._set_text_mode(
            "任务完成",
            "图像描述任务已完成<br><br>"
            "感谢您的配合，请稍作休息<br><br>"
            "按  Esc  退出"
        )
        self._bar_lbl.setText(f"共 {len(self.results)} 张  ·  结果已保存")
        self._speak("图像描述任务已完成，感谢您的配合，请稍作休息。")

    # ─────────────────────────────────── 计时 ───────────────────────

    def _on_tick(self):
        self._elapsed += 1
        self._update_bar()

        if self._elapsed < self._target:
            return

        self._tick.stop()

        if self.phase == "intro":
            self.img_idx = 0
            self._show_image()

        elif self.phase == "displaying":
            img = self.images[self.img_idx]
            self.results.append({
                "order":      img["order"],
                "filename":   img["filename"],
                "original":   img["original"],
                "valence":    img["valence"],
                "display_ms": round((time.time() - self._img_start_ts) * 1000),
                "timestamp":  time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            self.img_idx += 1
            if self.img_idx >= len(self.images):
                self._show_end()
            else:
                self._show_transition()

        elif self.phase == "transition":
            self._show_image()

    def _update_bar(self):
        remaining = max(self._target - self._elapsed, 0)
        rm, rs = divmod(remaining, 60)
        if self.phase == "displaying":
            img = self.images[self.img_idx] if self.img_idx < len(self.images) else {}
            val = img.get("valence", "")
            num = img.get("order", "")
            self._bar_lbl.setText(
                f"第 {num} / {len(self.images)} 张  [{val}]   剩余 {rm:02d}:{rs:02d}   |   按 Esc 退出"
            )
        elif self.phase == "intro":
            self._bar_lbl.setText(f"倒计时 {rm:02d}:{rs:02d}   |   按 Esc 退出")
        elif self.phase == "transition":
            self._bar_lbl.setText(f"稍候…  {rm:02d}:{rs:02d}")

    # ─────────────────────────────────── 保存 ───────────────────────

    def _save_results(self):
        if not self.results:
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ts   = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(OUTPUT_DIR, f"image_describe_{ts}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(self.results[0].keys()))
            w.writeheader()
            w.writerows(self.results)
        print(f"[ImageDescribe] 结果已保存：{path}")

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
    print("=" * 55)
    print("  图像描述任务  单元测试")
    print("  依据: GAPED — Dan-Glauser & Scherer (2011)")
    print("=" * 55)

    try:
        images = _load_images()
    except FileNotFoundError as e:
        print(f"\n[错误] {e}")
        return

    print()
    print("  图片列表：")
    all_ok = True
    for img in images:
        ok   = os.path.exists(img["path"])
        flag = "[OK]" if ok else "[缺失]"
        print(f"    {flag}  图{img['order']}  {img['filename']:<12}  {img['valence']}")
        if not ok:
            all_ok = False

    if not all_ok:
        print("\n  [错误] 有图片文件缺失，请重新运行 select_describe_images.py")
        return

    total = INTRO_SECS + len(images) * DISPLAY_SECS + (len(images) - 1) * TRANSITION_SECS
    print()
    print(f"  图片数: {len(images)} 张  · 每张 {DISPLAY_SECS}s  · 过渡 {TRANSITION_SECS}s")
    print(f"  预计总时长: {total // 60} 分 {total % 60} 秒")
    print()
    print("  全程自动推进，Esc 随时退出")
    print()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = ImageDescribeWindow(images)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
