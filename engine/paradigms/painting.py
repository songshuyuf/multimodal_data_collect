"""
绘画欣赏任务 Widget（集成版）
接受 task_executor 传入的绘画列表，全屏被动欣赏，自动推进。
"""

import os, csv, time
import cv2

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QProgressBar
from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtGui     import QImage, QPixmap

from engine.paradigms.base import BaseParadigmWidget

BG    = "#0a0a0a"
WHITE = "#f0f0f0"
GRAY  = "#333333"
LGRAY = "#666666"

# 默认时序（ms）
DEFAULT_DISPLAY_MS = 8000
DEFAULT_FIXATION_MS = 500
DEFAULT_ISI_MS = 500


class PaintingTask(BaseParadigmWidget):
    """
    绘画欣赏任务。

    paintings: list of dict，每项至少含 {path, style}
               可选含 {emotion, valence, arousal, artist}
    params:    来自 experiment_config 的 task params
    output_path: 结果 CSV 保存路径
    voice:     VoiceGuidance 实例（可为 None）
    """

    def __init__(self, paintings: list, params: dict,
                 output_path: str, voice=None, parent=None):
        super().__init__(output_path, parent)
        self._paintings   = paintings
        self._params      = params
        self._voice       = voice
        self._voice_player = None

        self._display_ms  = params.get('display_duration', DEFAULT_DISPLAY_MS)
        self._fixation_ms = params.get('fixation_duration', DEFAULT_FIXATION_MS)
        self._isi_ms      = params.get('isi', DEFAULT_ISI_MS)

        self._idx     = 0
        self._phase   = "intro"   # intro / fixation / display / isi / end
        self._results : list[dict] = []
        self._img_start = 0.0

        self.setStyleSheet(f"background:{BG};")
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 主展示区（文字 or 图片）
        self._lbl_main = QLabel()
        self._lbl_main.setAlignment(Qt.AlignCenter)
        self._lbl_main.setWordWrap(True)
        self._lbl_main.setStyleSheet(
            f"background:{BG}; color:{WHITE}; font-size:28px;"
            "font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_main, stretch=1)

        # 进度条
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)
        self._bar.setStyleSheet(
            "QProgressBar{background:#111;border:none;}"
            "QProgressBar::chunk{background:#8899aa;}"
        )
        lay.addWidget(self._bar)

        # 底部提示
        self._lbl_hint = QLabel()
        self._lbl_hint.setAlignment(Qt.AlignCenter)
        self._lbl_hint.setFixedHeight(30)
        self._lbl_hint.setStyleSheet(
            f"background:{GRAY}; color:{LGRAY}; font-size:12px;"
            "font-family:'Microsoft YaHei';"
        )
        lay.addWidget(self._lbl_hint)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._next_phase)

    # ── 启动/停止 ────────────────────────────────────────────────

    def _do_start(self):
        self._show_intro()

    def _do_stop(self):
        self._timer.stop()
        self._save_results()

    # ── 流程 ────────────────────────────────────────────────────

    def _show_intro(self):
        self._phase = "intro"
        self._lbl_main.setPixmap(QPixmap())
        self._lbl_main.setText(
            "【 绘画欣赏 】\n\n"
            f"接下来将展示 {len(self._paintings)} 幅绘画作品\n\n"
            "请放松心情，自然感受每一幅画带给您的感觉\n\n"
            "整个过程无需任何按键操作"
        )
        self._bar.setValue(0)
        self._lbl_hint.setText(f"共 {len(self._paintings)} 幅")
        self._speak_then(
            self._voice,
            "接下来您将欣赏一系列绘画作品。"
            "请放松心情，自然感受每一幅画带给您的感觉。"
            "整个过程无需任何按键操作，只需专注欣赏即可。",
            self._next_phase,
        )

    def _next_phase(self):
        if self._phase == "intro":
            self._idx = 0
            self._show_fixation()

        elif self._phase == "fixation":
            self._show_image()

        elif self._phase == "display":
            self._record_result()
            self._idx += 1
            if self._idx >= len(self._paintings):
                self._show_end()
            else:
                self._show_isi()

        elif self._phase == "isi":
            self._show_fixation()

        elif self._phase == "end":
            self._force_finish()

    def _show_fixation(self):
        self._phase = "fixation"
        self._lbl_main.setPixmap(QPixmap())
        self._lbl_main.setText("<span style='font-size:60px; color:#ffffff;'>+</span>")
        pct = int(self._idx / max(len(self._paintings), 1) * 100)
        self._bar.setValue(pct)
        self._lbl_hint.setText(
            f"{self._idx + 1} / {len(self._paintings)}"
        )
        self._timer.start(self._fixation_ms)

    def _show_image(self):
        self._phase = "display"
        p = self._paintings[self._idx]
        self._img_start = time.time()
        self._send_marker("STIM_PAINT_ON", trial=self._idx + 1,
                          style=p.get('style', ''))

        pix = QPixmap(p['path'])
        if pix.isNull():
            # 用 OpenCV 兜底
            frame = cv2.imread(p['path'])
            if frame is not None:
                rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                pix = QPixmap.fromImage(
                    QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
                )

        if not pix.isNull():
            sw = self._lbl_main.width()  or self.width()
            sh = (self._lbl_main.height() or self.height()) - 34
            pix = pix.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._lbl_main.setPixmap(pix)
        else:
            self._lbl_main.setText(f"[图片加载失败]\n{p['path']}")

        style = p.get('style', '?')
        emotion = p.get('emotion', '')
        hint = f"{self._idx + 1}/{len(self._paintings)}  {style}"
        if emotion:
            hint += f"  ·  {emotion}"
        self._lbl_hint.setText(hint)
        self._timer.start(self._display_ms)

    def _show_isi(self):
        self._phase = "isi"
        self._lbl_main.setPixmap(QPixmap())
        self._lbl_main.setText("")
        self._timer.start(self._isi_ms)

    def _show_end(self):
        self._phase = "end"
        self._lbl_main.setPixmap(QPixmap())
        self._lbl_main.setText(
            "绘画欣赏任务已完成\n\n感谢您的配合"
        )
        self._bar.setValue(100)
        self._lbl_hint.setText("任务完成")
        self._speak_then(
            self._voice,
            "绘画欣赏任务已完成，感谢您的配合，请稍作休息。",
            self._force_finish,
        )

    # ── 结果 ────────────────────────────────────────────────────

    def _record_result(self):
        self._send_marker("STIM_PAINT_OFF", trial=self._idx + 1)
        p = self._paintings[self._idx]
        self._results.append({
            "trial":     self._idx + 1,
            "filename":  os.path.basename(p['path']),
            "style":     p.get('style', ''),
            "emotion":   p.get('emotion', ''),
            "valence":   p.get('valence', ''),
            "arousal":   p.get('arousal', ''),
            "display_ms": round((time.time() - self._img_start) * 1000),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

    def _save_results(self):
        if not self._results or not self._output_path:
            return
        os.makedirs(os.path.dirname(self._output_path) or ".", exist_ok=True)
        with open(self._output_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(self._results[0].keys()))
            w.writeheader()
            w.writerows(self._results)

    # ── 语音 ────────────────────────────────────────────────────

    def _speak(self, text: str):
        self._speak_no_wait(self._voice, text)
