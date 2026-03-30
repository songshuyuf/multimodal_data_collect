"""
艺术范式基类 Widget
====================
所有范式 Widget 继承此类，统一实现：
  - 全屏锁定
  - Ctrl+C  → 强制结束当前范式（发 finished 信号）
  - Ctrl+D  → 切换窗口化 / 全屏（供操作员检查设备采集状态）
  - _speak_then(text, callback) → 配音同步：语音播完再执行 callback
  - 其余按键 → 一律忽略（Dot-probe 子类覆盖以接收方向键）
"""

import os
import csv
import time

from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore    import Qt, QTimer, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore    import QUrl


class BaseParadigmWidget(QWidget):
    """
    范式基类。

    子类必须实现：
        _do_start()  —— 启动内部计时器、加载资源等
        _do_stop()   —— 停止计时器、释放资源、保存结果

    finished(str) 信号携带结果 CSV 路径（可为空字符串）。
    """

    finished = pyqtSignal(str)   # 结果 CSV 路径

    def __init__(self, output_path: str = "", parent=None):
        super().__init__(parent)
        self._output_path = output_path
        self._aborted     = False

        self._base_voice_player = None
        self._voice_pending_cb  = None
        self._voice_connected   = False

        self._marker_mgr = None

    # ── Marker ────────────────────────────────────────────────

    def set_marker_manager(self, mgr):
        self._marker_mgr = mgr

    def _send_marker(self, name: str, **kwargs):
        if self._marker_mgr:
            self._marker_mgr.send_marker(name, **kwargs)

    # ── 生命周期 ─────────────────────────────────────────────────

    def start(self):
        """显示全屏并启动范式（确保置顶且获得焦点）"""
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self._do_start()

    def _do_start(self):
        """子类实现：启动内部逻辑"""

    def _do_stop(self):
        """子类实现：停止逻辑并保存"""

    def _force_finish(self):
        """强制结束（Ctrl+C 调用 或 正常结束后调用）"""
        if self._aborted:
            return
        self._aborted = True
        self._voice_pending_cb = None
        self._do_stop()
        self.finished.emit(self._output_path or "")
        self.hide()

    # ── 语音同步机制 ──────────────────────────────────────────────

    def _speak_then(self, voice, text: str, callback):
        """
        播放 AI 配音，语音播放完毕后调用 callback。
        如果 voice 不可用或 TTS 生成失败，8 秒后兜底调用 callback。
        """
        if voice is None or not text.strip():
            QTimer.singleShot(300, callback)
            return

        self._voice_pending_cb = callback

        if self._base_voice_player is None:
            self._base_voice_player = QMediaPlayer(self)
            self._base_voice_player.stateChanged.connect(
                self._on_base_voice_state
            )

        if not self._voice_connected and hasattr(voice, 'play_signal'):
            voice.play_signal.connect(self._on_base_voice_ready)
            self._voice_connected = True

        voice.speak(text)
        fallback_ms = max(len(text) * 400, 30000)
        self._voice_fallback_timer = QTimer(self)
        self._voice_fallback_timer.setSingleShot(True)
        self._voice_fallback_timer.timeout.connect(self._on_voice_fallback)
        self._voice_fallback_timer.start(fallback_ms)

    def _on_base_voice_ready(self, audio_path: str):
        """TTS 音频已生成，开始播放"""
        if self._base_voice_player is None:
            return
        self._base_voice_player.setMedia(
            QMediaContent(QUrl.fromLocalFile(audio_path))
        )
        self._base_voice_player.play()

    def _on_base_voice_state(self, state):
        """QMediaPlayer 状态变化：播放结束时触发 callback"""
        if state == QMediaPlayer.StoppedState and self._voice_pending_cb:
            cb = self._voice_pending_cb
            self._voice_pending_cb = None
            if hasattr(self, '_voice_fallback_timer'):
                self._voice_fallback_timer.stop()
            QTimer.singleShot(300, cb)

    def _on_voice_fallback(self):
        """兜底：TTS 生成超时或播放异常时强制推进"""
        if self._voice_pending_cb:
            cb = self._voice_pending_cb
            self._voice_pending_cb = None
            cb()

    def _speak_no_wait(self, voice, text: str):
        """播放语音但不等待完成（用于非关键过渡）"""
        if voice is None or not text.strip():
            return
        if self._base_voice_player is None:
            self._base_voice_player = QMediaPlayer(self)
            self._base_voice_player.stateChanged.connect(
                self._on_base_voice_state
            )
        if not self._voice_connected and hasattr(voice, 'play_signal'):
            voice.play_signal.connect(self._on_base_voice_ready)
            self._voice_connected = True
        voice.speak(text)

    # ── 按键处理 ─────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key  = event.key()
        mods = event.modifiers()

        if key == Qt.Key_C and (mods & Qt.ControlModifier):
            self._force_finish()
            return

        if key == Qt.Key_D and (mods & Qt.ControlModifier):
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            return
