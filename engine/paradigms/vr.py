"""
VR 沉浸任务 Widget（集成版）
PC 端用 OpenCV 播放本地视频，同步触发 PICO VR 播放。
"""

import os, csv, time, threading

import cv2

from PyQt5.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QProgressBar
from PyQt5.QtCore    import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui     import QImage, QPixmap

from engine.paradigms.base import BaseParadigmWidget

BG    = "#000000"
WHITE = "#f0f0f0"
GRAY  = "#222222"
LGRAY = "#555555"
GREEN = "#66bb6a"
ORANGE = "#ffa726"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DEFAULT_PC_VIDEO  = os.path.join(_PROJECT_ROOT, "vr", "video", "fengjing.mp4")
DEFAULT_PLAY_SECS = 180
INTRO_SECS        = 10
MAX_CONNECT_SECS  = 120


class _PicoConnectWorker(QObject):
    """后台线程：持续尝试连接 PICO 直到成功或被 abort"""
    status   = pyqtSignal(str)
    connected = pyqtSignal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._ctrl     = controller
        self._stop_evt = threading.Event()

    def abort(self):
        self._stop_evt.set()

    def run(self):
        attempt = 0
        while not self._stop_evt.is_set():
            attempt += 1
            self.status.emit(f"PICO 连接中… (第 {attempt} 次)")
            try:
                ok = self._ctrl.connect()
            except Exception:
                ok = False
            if ok:
                self.status.emit("PICO 已连接 ✓")
                self.connected.emit()
                return
            self._stop_evt.wait(4)
        self.status.emit("PICO 连接已取消")


class VRTask(BaseParadigmWidget):
    """
    params keys (all optional with defaults):
        pc_video_path, play_duration, pico_serial, pico_ip,
        pico_vr_file
    """

    def __init__(self, params: dict, output_path: str, voice=None, parent=None):
        super().__init__(output_path, parent)
        self._params  = params
        self._voice   = voice

        self._pc_video     = params.get('pc_video_path', DEFAULT_PC_VIDEO)
        self._play_secs    = int(params.get('play_duration', DEFAULT_PLAY_SECS))
        self._pico_serial  = params.get('pico_serial', '')
        self._pico_ip      = params.get('pico_ip', '')
        self._pico_vr_file = params.get('pico_vr_file',
                                        '/sdcard/Movies/ScreenRecording/fengjing.mp4')

        self._phase             = "intro"
        self._pico_ok           = False
        self._pico_play_sent    = False
        self._pico_ctrl         = None
        self._pico_worker       = None
        self._pico_thread       = None
        self._voice_player      = None
        self._results           = []

        self._cap        = None
        self._frame_idx  = 0
        self._fps        = 30.0
        self._elapsed    = 0

        self.setStyleSheet(f"background:{BG};")
        self._build_ui()
        self._init_pico_ctrl()

    def _init_pico_ctrl(self):
        try:
            from devices.vr_sync import VRADBController
            kw = {}
            if self._pico_serial:
                kw['pico_serial'] = self._pico_serial
            if self._pico_ip:
                kw['pico_ip'] = self._pico_ip
            self._pico_ctrl = VRADBController(**kw)
        except Exception:
            self._pico_ctrl = None

    # ── UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._lbl_video = QLabel()
        self._lbl_video.setAlignment(Qt.AlignCenter)
        self._lbl_video.setStyleSheet(f"background:{BG};")
        lay.addWidget(self._lbl_video, stretch=1)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(8, 0, 8, 0)

        self._lbl_pico = QLabel("PICO: 未连接")
        self._lbl_pico.setStyleSheet(
            f"color:{ORANGE}; font-size:13px; font-family:'Microsoft YaHei';"
        )
        status_row.addWidget(self._lbl_pico)
        status_row.addStretch()
        self._lbl_timer = QLabel()
        self._lbl_timer.setStyleSheet(
            f"color:{LGRAY}; font-size:13px; font-family:monospace;"
        )
        status_row.addWidget(self._lbl_timer)
        status_row.addStretch()
        self._lbl_hint = QLabel("")
        self._lbl_hint.setStyleSheet(
            f"color:{LGRAY}; font-size:12px; font-family:'Microsoft YaHei';"
        )
        status_row.addWidget(self._lbl_hint)

        bar_widget_h = QLabel()
        bar_widget_h.setFixedHeight(28)
        bar_widget_h.setStyleSheet(f"background:{GRAY};")
        lay.addWidget(bar_widget_h)
        bar_inner = QHBoxLayout(bar_widget_h)
        bar_inner.setContentsMargins(8, 0, 8, 0)
        bar_inner.addLayout(status_row)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)
        self._bar.setStyleSheet(
            "QProgressBar{background:#111;border:none;}"
            "QProgressBar::chunk{background:#4488cc;}"
        )
        lay.addWidget(self._bar)

    # ── 启动/停止 ────────────────────────────────────────────────

    def _do_start(self):
        self._show_intro()

    def _do_stop(self):
        if hasattr(self, '_pico_wait_timer'):
            self._pico_wait_timer.stop()
        if hasattr(self, '_frame_timer'):
            self._frame_timer.stop()
        if hasattr(self, '_count_timer'):
            self._count_timer.stop()
        if self._cap:
            self._cap.release()
            self._cap = None
        if self._pico_worker:
            self._pico_worker.abort()
        self._save_results()

    # ── 引导页 → 配音 → 等 PICO → PC 播放 ──────────────────────

    def _show_intro(self):
        self._phase = "intro"
        self._lbl_video.setText(
            f"<span style='font-size:32px; color:{WHITE};'>"
            "【 VR 沉浸体验 】</span>"
            "<br><br>"
            f"<span style='font-size:20px; color:{LGRAY};'>"
            "请戴上 VR 头显，保持放松</span>"
            "<br>"
            f"<span style='font-size:20px; color:{LGRAY};'>"
            "即将开始播放风景视频，整个过程无需任何按键操作</span>"
        )
        self._lbl_pico.setText("PICO: 连接中…")
        self._lbl_timer.setText("准备中…")

        self._start_pico_connect()

        self._speak_then(
            self._voice,
            "即将开始VR沉浸体验，请戴好VR头显，"
            "保持放松，感受自然风景的美好。"
            "整个过程无需任何按键操作。",
            self._after_voice,
        )

    def _start_pico_connect(self):
        """启动后台 PICO 连接循环"""
        if not self._pico_ctrl:
            self._lbl_pico.setStyleSheet(f"color:{LGRAY}; font-size:13px;")
            self._lbl_pico.setText("PICO: 未配置")
            return

        self._pico_worker = _PicoConnectWorker(self._pico_ctrl)
        self._pico_worker.status.connect(self._on_pico_status)
        self._pico_worker.connected.connect(self._on_pico_connected)
        self._pico_thread = threading.Thread(
            target=self._pico_worker.run, daemon=True
        )
        self._pico_thread.start()

    def _after_voice(self):
        """配音结束后：如果 PICO 已连接直接开始，否则等待"""
        if self._aborted:
            return
        self._phase = "wait_pico"
        if self._pico_ok:
            self._begin_playback()
        elif self._pico_ctrl is None:
            self._begin_playback()
        else:
            self._lbl_timer.setText("等待 VR 连接…")
            self._lbl_video.setText(
                f"<span style='font-size:28px; color:{WHITE};'>"
                "等待 PICO VR 连接</span><br><br>"
                f"<span style='font-size:18px; color:{LGRAY};'>"
                "请确认 PICO 已开机并通过 USB 或 WiFi 连接到电脑</span>"
            )
            self._pico_wait_timer = QTimer(self)
            self._pico_wait_timer.setSingleShot(True)
            self._pico_wait_timer.timeout.connect(self._pico_wait_timeout)
            self._pico_wait_timer.start(MAX_CONNECT_SECS * 1000)

    def _pico_wait_timeout(self):
        """等待 PICO 超时 → 直接用 PC 端播放"""
        if self._phase == "wait_pico" and not self._pico_ok:
            self._lbl_pico.setStyleSheet(f"color:{ORANGE}; font-size:13px;")
            self._lbl_pico.setText("PICO: 超时未连接（仅 PC 播放）")
            self._begin_playback()

    # ── 播放 ─────────────────────────────────────────────────────

    def _begin_playback(self):
        """PICO 就绪（或超时/无 PICO）后，启动播放"""
        if self._aborted or self._phase == "playing":
            return
        self._phase = "playing"
        if hasattr(self, '_pico_wait_timer'):
            self._pico_wait_timer.stop()

        self._send_marker("STIM_VIDEO_ON")

        if self._pico_ok and self._pico_ctrl:
            self._trigger_pico_play()

        self._video_open_retries = 0
        self._video_reopening   = False
        self._try_open_video()

        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(int(1000 / max(self._fps, 1)))
        self._frame_timer.timeout.connect(self._render_frame)
        self._frame_timer.start()

        self._elapsed = 0
        self._count_timer = QTimer(self)
        self._count_timer.setInterval(1000)
        self._count_timer.timeout.connect(self._on_count_tick)
        self._count_timer.start()

        self._play_start = time.time()

    def _try_open_video(self) -> bool:
        """尝试打开视频（多后端），成功返回 True"""
        if not os.path.exists(self._pc_video):
            print(f"  [VR] PC 视频不存在：{self._pc_video}")
            return False
        import sys as _sys
        backends = [cv2.CAP_ANY]
        if _sys.platform == "win32":
            backends.append(cv2.CAP_DSHOW)
        for backend in backends:
            cap = cv2.VideoCapture(self._pc_video, backend)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    if self._cap:
                        self._cap.release()
                    self._cap = cap
                    self._fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    if hasattr(self, '_frame_timer'):
                        self._frame_timer.setInterval(int(1000 / max(self._fps, 1)))
                    print(f"  [VR] 视频已打开 (backend={backend})")
                    return True
            cap.release()
        print(f"  [VR] 视频打开失败，稍后重试...")
        return False

    def _schedule_video_retry(self):
        """非阻塞式重试打开视频"""
        self._video_open_retries += 1
        if self._video_open_retries > 10:
            self._lbl_timer.setText("视频加载失败")
            return
        self._video_reopening = True
        QTimer.singleShot(500, self._do_video_retry)

    def _do_video_retry(self):
        self._video_reopening = False
        if self._try_open_video():
            self._video_open_retries = 0

    def _trigger_pico_play(self):
        """在后台触发 PICO 播放（仅一次）"""
        if self._pico_play_sent:
            return
        self._pico_play_sent = True
        if self._pico_worker:
            self._pico_worker.abort()

        def _play():
            try:
                self._pico_ctrl.ensure_connected()
                self._pico_ctrl._play_file(self._pico_vr_file)
            except Exception as e:
                print(f"  [VR] PICO 播放出错: {e}")
        threading.Thread(target=_play, daemon=True).start()

    def _render_frame(self):
        if not self._cap or not self._cap.isOpened():
            if not self._video_reopening:
                self._schedule_video_retry()
            return
        ret, frame = self._cap.read()
        if not ret:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()
        if not ret:
            self._cap.release()
            self._cap = None
            if not self._video_reopening:
                self._schedule_video_retry()
            return
        self._video_open_retries = 0
        h, w, ch = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        sw = self._lbl_video.width()
        sh = self._lbl_video.height()
        pix = QPixmap.fromImage(qimg).scaled(
            sw, sh, Qt.KeepAspectRatio, Qt.FastTransformation
        )
        self._lbl_video.setPixmap(pix)

    def _on_count_tick(self):
        self._elapsed += 1
        rm, rs = divmod(max(self._play_secs - self._elapsed, 0), 60)
        self._lbl_timer.setText(f"{rm:02d}:{rs:02d}")
        pct = int(self._elapsed / self._play_secs * 100)
        self._bar.setValue(min(pct, 100))

        if self._elapsed >= self._play_secs:
            self._count_timer.stop()
            self._show_end()

    # ── 结束 ─────────────────────────────────────────────────────

    def _show_end(self):
        self._send_marker("STIM_VIDEO_OFF")
        if self._pico_worker:
            self._pico_worker.abort()
        if hasattr(self, '_frame_timer'):
            self._frame_timer.stop()
        if self._cap:
            self._cap.release()
            self._cap = None

        self._lbl_video.setPixmap(QPixmap())
        self._lbl_video.setText(
            f"<span style='font-size:28px; color:{WHITE};'>"
            "VR 沉浸体验已完成</span><br>"
            f"<span style='font-size:18px; color:{LGRAY};'>"
            "感谢您的配合，请摘下头显</span>"
        )
        self._lbl_timer.setText("")
        self._bar.setValue(100)
        self._results.append({
            "pico_connected": str(self._pico_ok),
            "video":          os.path.basename(self._pc_video),
            "play_ms":        round((time.time() - getattr(self, '_play_start', time.time())) * 1000),
            "timestamp":      time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self._speak_then(
            self._voice,
            "VR沉浸体验已完成，感谢您的配合，请摘下头显。",
            self._force_finish,
        )

    # ── PICO 回调（连接成功即触发播放）──────────────────────────

    def _on_pico_status(self, msg: str):
        self._lbl_pico.setText(f"PICO: {msg}")

    def _on_pico_connected(self):
        self._pico_ok = True
        self._lbl_pico.setStyleSheet(f"color:{GREEN}; font-size:13px;")
        self._lbl_pico.setText("PICO: 已连接 ✓")
        if self._phase == "wait_pico":
            self._begin_playback()
        elif self._phase == "playing":
            self._trigger_pico_play()

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
