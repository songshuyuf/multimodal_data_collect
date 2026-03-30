"""
VR 范式单元测试（图形化版）
============================
PC 端播放本地视频（OpenCV 解码）+ 同步通过 ADB 控制 PICO 播放同一视频。

实验流程
--------
  [指导语屏 + AI 配音，10s 自动进入]
  → [PC 播放 fengjing.mp4  +  PICO 同步播放，3 分钟倒计时]
  → [结束屏 + AI 配音，自动停止 PICO]

视频路径
--------
  PC   : vr/video/fengjing.mp4
  PICO : /sdcard/Movies/ScreenRecording/fengjing.mp4

运行
----
  python -X utf8 tests/test_vr_paradigm_unit.py --serial PA8210MGH3300381G
  python -X utf8 tests/test_vr_paradigm_unit.py --pico-ip 192.168.x.x
  python -X utf8 tests/test_vr_paradigm_unit.py --pc-only
"""

import argparse
import os
import sys
import csv
import time
import threading

import cv2
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel,
                             QVBoxLayout, QHBoxLayout, QProgressBar)
from PyQt5.QtCore    import Qt, QTimer, QUrl, pyqtSignal, QObject
from PyQt5.QtGui     import QImage, QPixmap
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── 路径配置 ─────────────────────────────────────────────────────
PC_VIDEO_PATH  = os.path.join(ROOT, "vr", "video", "fengjing.mp4")
PICO_VIDEO_DIR = "/sdcard/Movies/ScreenRecording"
PICO_FILENAME  = "fengjing.mp4"
OUTPUT_DIR     = os.path.join(ROOT, "dataset", "results")

# ── 时序（秒） ────────────────────────────────────────────────────
INTRO_SECS = 10
PLAY_SECS  = 180   # 3 分钟

# ── 配色 ─────────────────────────────────────────────────────────
BG    = "#0a0a0a"
WHITE = "#f0f0f0"
GRAY  = "#444444"
LGRAY = "#888888"
GREEN = "#5fba7d"
RED   = "#e05c5c"


# ── OpenCV 视频播放器（逐帧渲染到 QLabel） ───────────────────────
class CVVideoPlayer:
    """用 OpenCV 解码视频，通过 QTimer 将帧渲染到 QLabel，完全绕开 DirectShow。"""

    def __init__(self, label: QLabel):
        self._label  = label
        self._cap    = None
        self._timer  = QTimer()
        self._timer.timeout.connect(self._next_frame)
        self._fps    = 30.0
        self._w = self._h = 0

    def load(self, path: str) -> bool:
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            return False
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._w   = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._h   = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return True

    def play(self):
        if self._cap and self._cap.isOpened():
            interval = max(1, int(1000 / self._fps))
            self._timer.start(interval)

    def stop(self):
        self._timer.stop()
        if self._cap:
            self._cap.release()
            self._cap = None
        self._label.clear()

    def _next_frame(self):
        if not self._cap or not self._cap.isOpened():
            return
        ok, frame = self._cap.read()
        if not ok:
            # 视频结束：循环播放
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
            if not ok:
                return

        # BGR → RGB → QImage → QPixmap
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg  = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix   = QPixmap.fromImage(qimg)

        # 等比缩放适应 label
        lw = self._label.width()
        lh = self._label.height()
        if lw > 0 and lh > 0:
            pix = pix.scaled(lw, lh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._label.setPixmap(pix)


# ── ADB 后台工作线程 ──────────────────────────────────────────────
class VRConnectWorker(QObject):
    connected    = pyqtSignal(bool, str)   # (成功?, 消息)
    play_started = pyqtSignal(bool, str)
    retry_status = pyqtSignal(int, int)    # (当前次, 最大次) 用于更新 UI

    # 连接参数
    MAX_RETRIES    = 5     # 最多尝试 5 次
    RETRY_INTERVAL = 4     # 每次间隔 4 秒

    def __init__(self, pico_ip="", pico_serial="", pc_only=False):
        super().__init__()
        self.pico_ip     = pico_ip
        self.pico_serial = pico_serial
        self.pc_only     = pc_only
        self._vr         = None
        self._stop_retry = False   # 外部可设 True 中断重试

    def do_connect(self):
        """带循环重试的连接，最多 MAX_RETRIES 次，每次失败等待 RETRY_INTERVAL 秒"""
        if self.pc_only:
            self.connected.emit(True, "PC-only 模式（不连 PICO）")
            return
        try:
            from devices.vr_sync import VRADBController
            self._vr = VRADBController(
                pico_ip=self.pico_ip,
                pico_serial=self.pico_serial,
                pico_video_dir=PICO_VIDEO_DIR,
            )
        except Exception as e:
            self.connected.emit(False, f"初始化异常：{e}")
            return

        self._stop_retry = False
        for attempt in range(1, self.MAX_RETRIES + 1):
            if self._stop_retry:
                break
            self.retry_status.emit(attempt, self.MAX_RETRIES)
            try:
                ok = self._vr.connect(retries=1)   # 每轮只尝试 1 次，外层循环控制间隔
                if ok:
                    self.connected.emit(True, f"PICO 连接成功（第 {attempt} 次）")
                    return
            except Exception as e:
                print(f"  [VR] 第 {attempt} 次连接异常：{e}")

            if attempt < self.MAX_RETRIES and not self._stop_retry:
                time.sleep(self.RETRY_INTERVAL)

        self.connected.emit(False, f"PICO 连接失败（已重试 {self.MAX_RETRIES} 次），仅 PC 端播放")

    def abort_retry(self):
        """中断重试循环（实验开始时调用）"""
        self._stop_retry = True

    def do_play(self):
        if self.pc_only or self._vr is None:
            self.play_started.emit(True, "PC-only 模式")
            return
        try:
            # 播放前再确认一次连接
            if not self._vr.ensure_connected():
                # 尝试重连一次
                ok_conn = self._vr.connect(retries=2)
                if not ok_conn:
                    self.play_started.emit(False, "PICO 重连失败，跳过 PICO 播放")
                    return
            ok = self._vr.play(PICO_FILENAME)
            self.play_started.emit(ok, "PICO 视频已启动" if ok else "PICO 视频启动失败")
        except Exception as e:
            self.play_started.emit(False, f"播放异常：{e}")

    def do_stop(self):
        self._stop_retry = True
        if self._vr:
            try:
                self._vr.stop()
            except Exception:
                pass


# ── 主窗口 ────────────────────────────────────────────────────────
class VRWindow(QWidget):
    def __init__(self, pico_ip="", pico_serial="", pc_only=False):
        super().__init__()
        self.pico_ip     = pico_ip
        self.pico_serial = pico_serial
        self.pc_only     = pc_only

        self.phase    = "intro"
        self._elapsed = 0
        self._target  = 0
        self._start_ts = 0.0
        self._pico_ok  = False
        self.result: dict = {}

        self.setWindowTitle("VR 沉浸体验任务")
        self.setStyleSheet(f"background:{BG};")
        self.showFullScreen()

        # 倒计时定时器
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)

        # 语音
        self._voice        = None
        self._voice_player = None
        self._init_voice()

        # ADB 工作线程
        self._worker = VRConnectWorker(pico_ip, pico_serial, pc_only)
        self._worker.connected.connect(self._on_pico_connected)
        self._worker.play_started.connect(self._on_pico_play_started)
        self._worker.retry_status.connect(self._on_retry_status)

        self._build_ui()

        # OpenCV 播放器
        self._cv_player = CVVideoPlayer(self._video_label)

        QTimer.singleShot(200, self._show_intro)

    # ─────────────────────────────────── UI ────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 顶部状态条
        top = QHBoxLayout()
        top.setContentsMargins(20, 8, 20, 8)
        self._lbl_title = QLabel("VR 沉浸体验任务")
        self._lbl_title.setStyleSheet(
            f"color:{WHITE}; font-size:16px; font-family:'Microsoft YaHei';"
        )
        top.addWidget(self._lbl_title)
        top.addStretch()
        self._lbl_pico = QLabel("PICO: 连接中…")
        self._lbl_pico.setStyleSheet(
            f"color:{LGRAY}; font-size:14px; font-family:'Microsoft YaHei';"
        )
        top.addWidget(self._lbl_pico)
        outer.addLayout(top)

        # 中间：说明文字（intro/end 时显示）
        self._lbl_overlay = QLabel()
        self._lbl_overlay.setAlignment(Qt.AlignCenter)
        self._lbl_overlay.setWordWrap(True)
        self._lbl_overlay.setStyleSheet(
            f"background:{BG}; color:{WHITE}; font-size:24px;"
            "line-height:200%; font-family:'Microsoft YaHei';"
        )
        outer.addWidget(self._lbl_overlay, stretch=1)

        # 中间：视频帧（playing 时显示）
        self._video_label = QLabel()
        self._video_label.setAlignment(Qt.AlignCenter)
        self._video_label.setStyleSheet(f"background:{BG};")
        self._video_label.hide()
        outer.addWidget(self._video_label, stretch=1)

        # 进度条
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)
        self._bar.setStyleSheet("""
            QProgressBar { background:#1a1a1a; border:none; }
            QProgressBar::chunk { background:#7ec8e3; }
        """)
        outer.addWidget(self._bar)

        # 底部信息条
        bot = QHBoxLayout()
        bot.setContentsMargins(20, 6, 20, 6)
        self._lbl_timer = QLabel()
        self._lbl_timer.setStyleSheet(
            f"color:{LGRAY}; font-size:14px; font-family:monospace;"
        )
        bot.addWidget(self._lbl_timer)
        bot.addStretch()
        self._lbl_hint = QLabel("按 Esc 退出")
        self._lbl_hint.setStyleSheet(
            f"color:{GRAY}; font-size:13px; font-family:'Microsoft YaHei';"
        )
        bot.addWidget(self._lbl_hint)
        outer.addLayout(bot)

    # ─────────────────────────────────── 指导语 ─────────────────────

    def _show_intro(self):
        self.phase    = "intro"
        self._elapsed = 0
        self._target  = INTRO_SECS

        self._video_label.hide()
        self._lbl_overlay.show()
        self._lbl_overlay.setText(
            "<b style='color:#f5c842; font-size:32px;'>VR 沉浸体验任务</b><br><br>"
            "接下来请您戴上 VR 头显<br><br>"
            "您将沉浸在一段约 3 分钟的自然风景中<br><br>"
            "请保持放松，自由感受画面带来的体验<br><br>"
            "如有任何不适请立即告知工作人员"
        )
        self._lbl_hint.setText("正在准备…   |   按 Esc 退出")
        self._update_bottom()
        self._tick.start()

        self._speak(
            "接下来请戴上VR头显。"
            "您将沉浸在一段约三分钟的自然风景中，请保持放松，"
            "自由感受画面带来的体验。如有任何不适请立即告知工作人员。"
        )
        threading.Thread(target=self._worker.do_connect, daemon=True).start()

    # ─────────────────────────────────── 播放阶段 ───────────────────

    def _start_playing(self):
        self.phase     = "playing"
        self._elapsed  = 0
        self._target   = PLAY_SECS
        self._start_ts = time.time()

        self._lbl_overlay.hide()
        self._video_label.show()

        # 加载并播放视频（OpenCV）
        if self._cv_player.load(PC_VIDEO_PATH):
            self._cv_player.play()
        else:
            self._video_label.setText(
                f"<span style='color:{RED};'>视频加载失败：</span><br>{PC_VIDEO_PATH}"
            )

        # 中止还在进行的重试，然后启动 PICO 播放
        self._worker.abort_retry()
        threading.Thread(target=self._worker.do_play, daemon=True).start()

        self._lbl_hint.setText("VR 播放中   ·   按 Esc 退出")
        self._update_bottom()
        self._tick.start()

    # ─────────────────────────────────── 结束 ───────────────────────

    def _show_end(self):
        self.phase = "end"
        self._tick.stop()
        self._cv_player.stop()
        self._video_label.hide()
        self._lbl_overlay.show()
        threading.Thread(target=self._worker.do_stop, daemon=True).start()

        actual_ms = round((time.time() - self._start_ts) * 1000)
        self.result = {
            "pico_connected": self._pico_ok,
            "video":          PICO_FILENAME,
            "play_ms":        actual_ms,
            "timestamp":      time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save_result()

        self._lbl_overlay.setText(
            "<b style='color:#f5c842; font-size:32px;'>任务完成</b><br><br>"
            "VR 沉浸体验任务已完成<br><br>"
            "请缓慢摘下 VR 头显<br><br>"
            "感谢您的配合，请稍作休息<br><br>"
            "按  Esc  退出"
        )
        self._bar.setValue(100)
        self._lbl_timer.setText("")
        self._lbl_hint.setText("结果已保存   |   按 Esc 退出")
        self._speak("VR沉浸体验任务已完成。请缓慢摘下VR头显，感谢您的配合，请稍作休息。")

    # ─────────────────────────────────── PICO 回调 ──────────────────

    def _on_retry_status(self, attempt: int, total: int):
        """实时显示连接重试进度"""
        self._lbl_pico.setStyleSheet(
            f"color:#f5c842; font-size:14px; font-family:'Microsoft YaHei';"
        )
        self._lbl_pico.setText(f"PICO: 连接中… ({attempt}/{total})")
        print(f"  [VR] 连接尝试 {attempt}/{total}…")

    def _on_pico_connected(self, ok: bool, msg: str):
        self._pico_ok = ok
        color = GREEN if ok else (LGRAY if self.pc_only else RED)
        if self.pc_only:
            label = "PICO: PC-only"
        elif ok:
            label = "PICO: 已连接 ✓"
        else:
            label = "PICO: 连接失败，仅 PC 端"
        self._lbl_pico.setStyleSheet(
            f"color:{color}; font-size:14px; font-family:'Microsoft YaHei';"
        )
        self._lbl_pico.setText(label)
        print(f"  [VR] {msg}")

    def _on_pico_play_started(self, ok: bool, msg: str):
        if ok:
            self._lbl_pico.setText("PICO: 播放中 ▶")
        print(f"  [VR] {msg}")

    # ─────────────────────────────────── 计时 ───────────────────────

    def _on_tick(self):
        self._elapsed += 1
        self._update_bottom()
        if self._elapsed >= self._target:
            self._tick.stop()
            if self.phase == "intro":
                self._start_playing()
            elif self.phase == "playing":
                self._show_end()

    def _update_bottom(self):
        remaining = max(self._target - self._elapsed, 0)
        pct       = int(self._elapsed / max(self._target, 1) * 100)
        self._bar.setValue(pct)
        rm, rs = divmod(remaining, 60)
        label  = f"剩余  {rm:02d}:{rs:02d}  /  {self._target // 60}:{self._target % 60:02d}"
        self._lbl_timer.setText(label)

    # ─────────────────────────────────── 保存 ───────────────────────

    def _save_result(self):
        if not self.result:
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ts   = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(OUTPUT_DIR, f"vr_{ts}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(self.result.keys()))
            w.writeheader()
            w.writerow(self.result)
        print(f"[VR] 结果已保存：{path}")

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
            self._cv_player.stop()
            threading.Thread(target=self._worker.do_stop, daemon=True).start()
            self._save_result()
            QApplication.quit()


# ── 入口 ─────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="VR 范式单元测试")
    ap.add_argument("--pico-ip",  default="",                   help="PICO 局域网 IP（WiFi 模式）")
    ap.add_argument("--serial",   default="PA8210MGH3300381G",  help="PICO USB 序列号（USB 模式）")
    ap.add_argument("--pc-only",  action="store_true",          help="仅测试 PC 端，不连 PICO")
    args = ap.parse_args()

    print("=" * 55)
    print("  VR 范式单元测试")
    print("=" * 55)
    mode = "PC-only" if args.pc_only else (f"WiFi ({args.pico_ip})" if args.pico_ip else f"USB ({args.serial})")
    print(f"  模式  : {mode}")

    ok = os.path.exists(PC_VIDEO_PATH)
    print(f"  视频  : {'[OK]' if ok else '[缺失]'}  {PC_VIDEO_PATH}")
    print(f"  时长  : {PLAY_SECS // 60} 分 {PLAY_SECS % 60} 秒")
    print()
    if not ok:
        print("  [错误] 视频文件不存在，请检查路径")
        return

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = VRWindow(pico_ip=args.pico_ip, pico_serial=args.serial, pc_only=args.pc_only)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
