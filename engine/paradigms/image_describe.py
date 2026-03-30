"""
图像描述任务 Widget（集成版）
逐张展示 4 幅图片，患者口头描述感受，自动计时推进。
"""

import os, csv, time

import cv2
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QProgressBar
from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtGui     import QImage, QPixmap
from engine.paradigms.base import BaseParadigmWidget

BG    = "#0a0a0a"
WHITE = "#f5f5f5"
GOLD  = "#d4a94a"
GRAY  = "#1a1a1a"
LGRAY = "#555555"
GREEN = "#66bb6a"

DEFAULT_INTRO_SECS   = 8
DEFAULT_PER_IMG_SECS = 40
DEFAULT_TRANSIT_SECS = 3


class ImageDescribeTask(BaseParadigmWidget):
    """
    images      : list of dict，每项含 {path, valence, arousal, filename}
    params      : task params（per_image_duration: 秒, transit_duration: 秒）
    output_path : 结果 CSV
    voice       : VoiceGuidance 实例
    """

    def __init__(self, images: list, params: dict,
                 output_path: str, voice=None, parent=None):
        super().__init__(output_path, parent)
        self._images   = images
        self._params   = params
        self._voice    = voice

        self._intro_secs   = int(params.get('intro_duration', DEFAULT_INTRO_SECS))
        self._per_secs     = int(params.get('per_image_duration', DEFAULT_PER_IMG_SECS))
        self._transit_secs = int(params.get('transit_duration', DEFAULT_TRANSIT_SECS))

        self._idx      = 0
        self._phase    = "intro"
        self._elapsed  = 0
        self._img_start = 0.0
        self._results: list[dict] = []
        self._voice_player = None

        self.setStyleSheet(f"background:{BG};")
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 主展示区
        self._lbl_main = QLabel()
        self._lbl_main.setAlignment(Qt.AlignCenter)
        self._lbl_main.setWordWrap(True)
        self._lbl_main.setStyleSheet(
            f"background:{BG}; color:{WHITE}; font-size:40px;"
            "font-family:'Microsoft YaHei'; padding:40px;"
        )
        lay.addWidget(self._lbl_main, stretch=1)

        # 提示文字覆盖层（图片显示时用）
        self._lbl_overlay = QLabel()
        self._lbl_overlay.setAlignment(Qt.AlignCenter)
        self._lbl_overlay.setFixedHeight(44)
        self._lbl_overlay.setStyleSheet(
            f"background:rgba(0,0,0,180); color:{WHITE}; font-size:18px;"
            "font-family:'Microsoft YaHei';"
        )
        self._lbl_overlay.hide()
        lay.addWidget(self._lbl_overlay)

        # 进度条
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setStyleSheet(
            "QProgressBar{background:#111;border:none;}"
            "QProgressBar::chunk{background:#d4a94a;}"
        )
        lay.addWidget(self._bar)

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
        self._lbl_overlay.hide()
        self._lbl_main.setPixmap(QPixmap())
        self._lbl_main.setText(
            "【 图像描述任务 】\n\n"
            f"接下来将展示 {len(self._images)} 幅图片\n\n"
            "请用语言描述您看到的内容以及引发的感受\n\n"
            "整个过程无需任何按键操作"
        )
        self._bar.setValue(0)
        self._lbl_hint.setText(
            f"共 {len(self._images)} 幅图片，每幅 {self._per_secs}s   "
            ""
        )
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)

        self._speak_then(
            self._voice,
            f"接下来是图像描述任务，共有{len(self._images)}幅图片。"
            "每幅图片请用语言描述您看到的内容以及引发的感受。"
            "整个过程无需任何按键操作。",
            lambda: self._show_image(0),
        )

    def _show_image(self, idx: int):
        self._phase    = "showing"
        self._idx      = idx
        self._elapsed  = 0
        self._img_start = time.time()
        self._send_marker("STIM_IMAGE_ON", image=idx + 1)

        p = self._images[idx]
        self._load_image(p['path'])
        self._lbl_overlay.show()
        self._lbl_overlay.setText(
            f"图片 {idx + 1} / {len(self._images)}   请描述您看到的内容和感受"
        )
        self._bar.setStyleSheet(
            "QProgressBar{background:#111;border:none;}"
            "QProgressBar::chunk{background:#d4a94a;}"
        )
        self._bar.setValue(0)
        self._lbl_hint.setText(
            f"第 {idx + 1}/{len(self._images)} 幅   剩余 {self._per_secs}s"
        )
        self._tick.start()

    def _load_image(self, path: str):
        pix = QPixmap(path)
        if pix.isNull():
            frame = cv2.imread(path)
            if frame is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                pix = QPixmap.fromImage(
                    QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
                )
        if not pix.isNull():
            sw = self._lbl_main.width() or self.width()
            sh = max((self._lbl_main.height() or self.height()) - 80, 100)
            pix = pix.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._lbl_main.setPixmap(pix)
        else:
            self._lbl_main.setPixmap(QPixmap())
            self._lbl_main.setText(f"[图片加载失败]\n{path}")

    def _show_transit(self):
        self._phase   = "transit"
        self._elapsed = 0
        self._lbl_overlay.hide()
        self._lbl_main.setPixmap(QPixmap())
        self._lbl_main.setText("")
        self._bar.setStyleSheet(
            "QProgressBar{background:#111;border:none;}"
            "QProgressBar::chunk{background:#555;}"
        )
        self._lbl_hint.setText("切换中…")
        self._tick.start()

    def _show_end(self):
        self._phase = "end"
        self._tick.stop()
        self._lbl_overlay.hide()
        self._lbl_main.setPixmap(QPixmap())
        self._lbl_main.setText(
            "图像描述任务已完成\n\n感谢您的配合，请稍作休息"
        )
        self._bar.setValue(100)
        self._lbl_hint.setText("任务完成")
        self._speak_then(
            self._voice,
            "图像描述任务已完成，感谢您的配合，请稍作休息。",
            self._force_finish,
        )

    def _on_tick(self):
        self._elapsed += 1
        target = {
            "showing": self._per_secs,
            "transit": self._transit_secs,
        }.get(self._phase, 5)

        pct = int(self._elapsed / max(target, 1) * 100)
        self._bar.setValue(min(pct, 100))

        if self._phase == "showing":
            rm, rs = divmod(max(self._per_secs - self._elapsed, 0), 60)
            self._lbl_hint.setText(
                f"第 {self._idx + 1}/{len(self._images)} 幅   "
                f"剩余 {rm:02d}:{rs:02d}"
            )

        if self._elapsed >= target:
            self._tick.stop()
            if self._phase == "showing":
                self._send_marker("STIM_IMAGE_OFF",
                                  image=self._idx + 1)
                p = self._images[self._idx]
                self._results.append({
                    "order":      self._idx + 1,
                    "filename":   p.get('filename', os.path.basename(p['path'])),
                    "valence":    p.get('valence', ''),
                    "arousal":    p.get('arousal', ''),
                    "display_ms": round((time.time() - self._img_start) * 1000),
                    "timestamp":  time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                next_idx = self._idx + 1
                if next_idx >= len(self._images):
                    self._show_end()
                else:
                    self._show_transit()

            elif self._phase == "transit":
                self._show_image(self._idx + 1)

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
