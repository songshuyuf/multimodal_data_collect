"""
主控台页面 — Fluent Design 卡片式滚动布局
业务逻辑完整保留：设备管理、患者选择、实验启停、Runner 信号、语音、日志
"""

import os
import logging
from datetime import datetime
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from qfluentwidgets import (
    SmoothScrollArea, HeaderCardWidget,
    PrimaryPushButton, PushButton,
    TitleLabel, StrongBodyLabel, CaptionLabel,
    FluentIcon as FIF, setFont,
)

from data.database import DatabaseManager
from data.session import SessionManager

from .widgets.device_panel import DevicePanel
from .widgets.patient_panel import PatientPanel
from .widgets.progress_panel import ExperimentOverviewCard, ExperimentProgressPanel


class ConsolePage(SmoothScrollArea):
    """
    主控台 — 单列卡片滚动布局

    对外接口（与旧 ExperimentTab 兼容）：
        device_controller  — DeviceController 实例（可能为 None）
        is_collecting      — bool
        device_controller_ready — pyqtSignal(object)
    """

    device_controller_ready = pyqtSignal(object)
    experiment_session_done = pyqtSignal(str)   # session_dir path

    def __init__(self, db: DatabaseManager, sm: SessionManager, parent=None):
        super().__init__(parent)
        self.setObjectName("consolePage")
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea{background:transparent; border:none;}")

        self.db = db
        self.sm = sm
        self.logger = logging.getLogger(__name__)

        self.is_collecting: bool = False
        self._experiment_running: bool = False
        self._record_start: Optional[datetime] = None
        self._task_start: Optional[datetime] = None
        self._current_task_duration: int = 0
        self._current_session_dir: str = ""

        self._runner = None
        self._voice = None

        self._build_ui()
        self._init_voice()

        self._tick_timer = QTimer()
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000)

    @property
    def device_controller(self):
        return self._device_panel.device_controller

    # ═══════════════════════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════════════════════

    def _build_ui(self):
        container = QWidget()
        container.setStyleSheet("QWidget{background:transparent;}")
        self.setWidget(container)

        self._lay = QVBoxLayout(container)
        self._lay.setContentsMargins(36, 28, 36, 28)
        self._lay.setSpacing(20)
        self._lay.setAlignment(Qt.AlignTop)

        self._build_patient_card()
        self._build_experiment_card()
        self._build_device_card()
        self._build_overview_progress()
        self._build_log_card()

    # ── 患者选择 ──

    def _build_patient_card(self):
        self._patient_panel = PatientPanel(self.db)
        self._patient_panel.log_message.connect(self._log)
        self._lay.addWidget(self._patient_panel)

    # ── 实验控制 ──

    def _build_experiment_card(self):
        card = HeaderCardWidget(self)
        card.setTitle("Step 2 · 实验控制")

        btn_row = QHBoxLayout()
        btn_row.setSpacing(14)

        self._btn_start = PrimaryPushButton(FIF.PLAY, "开始采集实验")
        self._btn_start.setFixedHeight(52)
        self._btn_start.setMinimumWidth(260)
        setFont(self._btn_start, 16, QFont.Bold)
        self._btn_start.clicked.connect(self._on_start)
        btn_row.addWidget(self._btn_start, stretch=3)

        self._btn_stop = PushButton(FIF.CLOSE, "停止")
        self._btn_stop.setFixedHeight(52)
        self._btn_stop.setEnabled(False)
        setFont(self._btn_stop, 16, QFont.Bold)
        self._btn_stop.clicked.connect(self._on_stop)
        btn_row.addWidget(self._btn_stop, stretch=1)

        card.viewLayout.addLayout(btn_row)

        self._timer_lbl = TitleLabel("00:00:00")
        self._timer_lbl.setAlignment(Qt.AlignCenter)
        card.viewLayout.addWidget(self._timer_lbl)

        self._stats_lbl = CaptionLabel(
            "EEG: —  |  GSR: —  |  EMG: —  |  视频: —  |  音频: —"
        )
        self._stats_lbl.setAlignment(Qt.AlignCenter)
        card.viewLayout.addWidget(self._stats_lbl)

        self._lay.addWidget(card)

    # ── 设备检测 ──

    def _build_device_card(self):
        self._device_panel = DevicePanel()
        self._device_panel.device_controller_ready.connect(self._on_device_ready)
        self._device_panel.log_message.connect(self._log)
        self._lay.addWidget(self._device_panel)

    # ── 概览 + 进度 ──

    def _build_overview_progress(self):
        self._overview_card = ExperimentOverviewCard()
        self._lay.addWidget(self._overview_card)

        self._progress_panel = ExperimentProgressPanel()
        self._progress_panel.setVisible(False)
        self._lay.addWidget(self._progress_panel)

    # ── 日志 ──

    def _build_log_card(self):
        card = HeaderCardWidget(self)
        card.setTitle("操作日志")

        self._log_box = QTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setFixedHeight(180)
        self._log_box.setStyleSheet(
            "QTextEdit { background: transparent; border: none; font-size: 13px; }"
        )
        card.viewLayout.addWidget(self._log_box)

        btn_clear = PushButton("清空")
        btn_clear.setFixedHeight(30)
        btn_clear.clicked.connect(self._log_box.clear)
        card.viewLayout.addWidget(btn_clear)

        self._lay.addWidget(card)

    # ═══════════════════════════════════════════════════════════
    #  业务逻辑（完整保留自旧版 ExperimentTab）
    # ═══════════════════════════════════════════════════════════

    def _init_voice(self):
        try:
            from engine.voice import VoiceGuidance
            self._voice = VoiceGuidance()
            self._voice.play_signal.connect(self._play_voice_slot)
            self._log("\u2713 AI 语音引导已就绪")
        except Exception:
            self._voice = None

    def _on_device_ready(self, dc):
        self.device_controller_ready.emit(dc)

    # ── 实验控制 ──

    def _on_start(self):
        if self._patient_panel.current_patient is None:
            QMessageBox.warning(self, "提示", "请先选择患者")
            return

        self._device_panel._ensure_device_controller()

        session_dir = "./data/sessions/default"
        try:
            patient = self._patient_panel.current_patient
            existing = self.sm.get_patient_sessions(str(patient.patient_id))
            session_no = len(existing) + 1
            session = self.sm.create_session(str(patient.patient_id), session_no)
            if session and session.data_path:
                base = getattr(self.sm.fm, 'base_path', './data/sessions')
                session_dir = os.path.join(base, session.data_path)
                self._log(f"会话目录：{session_dir}")
        except Exception as e:
            self._log(f"\u26a0 会话目录创建失败，使用默认路径：{e}")

        dc = self._device_panel.device_controller
        if dc:
            ok = dc.start_recording()
            if not ok:
                self._log("\u26a0 设备未连接，以模拟模式运行")

        self.is_collecting = True
        self._experiment_running = True
        self._record_start = datetime.now()
        self._current_session_dir = session_dir

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._overview_card.setVisible(False)
        self._progress_panel.setVisible(True)

        self._start_runner(session_dir)
        self._log("\u25b6 实验已开始")

    def _start_runner(self, session_dir: str):
        try:
            from engine.runner import ExperimentRunner

            self._runner = ExperimentRunner(
                config_path="./experiment_config.json",
                dataset_root="./dataset",
                session_dir=session_dir,
                voice=self._voice,
            )

            total = len(self._runner._config.get('tasks', []))
            self._progress_panel._total = total

            self._runner.task_started.connect(self._on_task_started)
            self._runner.task_progress.connect(
                self._progress_panel.update_task_progress
            )
            self._runner.experiment_finished.connect(self._on_experiment_finished)
            self._runner.status_message.connect(self._log)

            self._runner.start()

        except Exception as e:
            self._log(f"\u2717 启动实验范式失败：{e}")
            import traceback
            traceback.print_exc()

    def _on_task_started(self, name: str, task_id: int):
        self._task_start = datetime.now()
        try:
            tasks = self._runner._config.get('tasks', [])
            for t in tasks:
                if t['id'] == task_id:
                    self._current_task_duration = t.get('duration', 0)
                    break
        except Exception:
            self._current_task_duration = 0

        total = len(self._runner._config.get('tasks', []))
        self._progress_panel.update_task(name, task_id, total)
        self._log(f"\u25ba 任务 {task_id}/{total}：{name}")

    def _on_experiment_finished(self):
        total = len(self._runner._config.get('tasks', [])) if self._runner else 8
        self._progress_panel.mark_finished(total)
        self._on_stop(auto=True)
        self._log("\u2713 实验已全部完成")

        if self._current_session_dir:
            self.experiment_session_done.emit(self._current_session_dir)

    def _on_stop(self, auto: bool = False):
        if not self._experiment_running:
            return

        if not auto and self._runner:
            self._runner.stop()

        dc = self._device_panel.device_controller
        if dc and self.is_collecting:
            stats = dc.stop_recording()
            dur = stats.get('duration', 0)
            self._log(
                f"\u25a0 采集停止  时长 {dur:.1f}s  "
                f"EEG {stats.get('heeg_packets', 0)} 包  "
                f"视频 {stats.get('video_frames', 0)} 帧"
            )

        self.is_collecting = False
        self._experiment_running = False
        self._record_start = None
        self._task_start = None

        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._timer_lbl.setText("00:00:00")
        self._stats_lbl.setText(
            "EEG: —  |  GSR: —  |  EMG: —  |  视频: —  |  音频: —"
        )

        if not auto:
            self._overview_card.setVisible(True)
            self._progress_panel.setVisible(False)

    # ── 定时刷新 ──

    def _tick(self):
        if not self.is_collecting or self._record_start is None:
            return

        elapsed = int((datetime.now() - self._record_start).total_seconds())
        task_remain = None
        if self._task_start and self._current_task_duration > 0:
            used = int((datetime.now() - self._task_start).total_seconds())
            task_remain = max(0, self._current_task_duration - used)

        self._progress_panel.update_elapsed(elapsed, task_remain)

        h, r = divmod(elapsed, 3600)
        m, s = divmod(r, 60)
        self._timer_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")

        dc = self._device_panel.device_controller
        if dc:
            self._stats_lbl.setText(
                f"EEG: {dc.heeg_packet_count} 包  |  "
                f"GSR: {dc.shimmer_packet_count} 包  |  "
                f"EMG: {dc.shimmer_emg_packet_count} 包  |  "
                f"视频: {dc.video_frame_count} 帧  |  "
                f"音频: {dc.audio_sample_count} 样本"
            )

    # ── 语音播放 ──

    def _play_voice_slot(self, file_path: str):
        if not os.path.exists(file_path):
            return
        try:
            from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
            from PyQt5.QtCore import QUrl

            if not hasattr(self, '_voice_player'):
                self._voice_player = QMediaPlayer()
                self._voice_player.setVolume(100)

            abs_path = os.path.abspath(file_path)
            self._voice_player.setMedia(QMediaContent(QUrl.fromLocalFile(abs_path)))
            self._voice_player.play()
            return
        except ImportError:
            pass
        except Exception:
            pass

        try:
            import subprocess, sys
            abs_path = os.path.abspath(file_path)
            if sys.platform == "win32":
                subprocess.Popen(
                    ["cmd", "/c", "start", "/min", "", abs_path],
                    shell=False, creationflags=0x08000000,
                )
            elif sys.platform == "darwin":
                subprocess.Popen(["open", abs_path])
            else:
                subprocess.Popen(["xdg-open", abs_path])
        except Exception:
            pass

    # ── 日志 ──

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_box.append(
            f"<span style='color:#9CA3AF'>{ts}</span>  {msg}"
        )
        self.logger.info(msg)
