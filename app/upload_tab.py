"""
数据上传页面 — Fluent Design 卡片布局
=======================================
服务器配置 + 上传队列 + 进度追踪 + 历史记录
"""

import os
import logging
from functools import partial
from typing import Dict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from qfluentwidgets import (
    SmoothScrollArea, HeaderCardWidget, SimpleCardWidget,
    PrimaryPushButton, PushButton, ToolButton,
    LineEdit, PasswordLineEdit, SwitchButton,
    ProgressBar, InfoBadge, InfoLevel,
    TitleLabel, SubtitleLabel, StrongBodyLabel,
    BodyLabel, CaptionLabel, FluentIcon as FIF, setFont,
)

from .upload_manager import UploadManager, UploadStatus

logger = logging.getLogger(__name__)

_STATUS_TEXT = {
    UploadStatus.PENDING:     "等待中",
    UploadStatus.COMPRESSING: "压缩中",
    UploadStatus.UPLOADING:   "上传中",
    UploadStatus.COMPLETED:   "已完成",
    UploadStatus.FAILED:      "失败",
    UploadStatus.PAUSED:      "已暂停",
}
_STATUS_LEVEL = {
    UploadStatus.PENDING:     InfoLevel.INFOAMTION,
    UploadStatus.COMPRESSING: InfoLevel.INFOAMTION,
    UploadStatus.UPLOADING:   InfoLevel.INFOAMTION,
    UploadStatus.COMPLETED:   InfoLevel.SUCCESS,
    UploadStatus.FAILED:      InfoLevel.ERROR,
    UploadStatus.PAUSED:      InfoLevel.WARNING,
}

_MODALITY_ICONS = {
    "heeg": FIF.CALORIES,
    "shimmer": FIF.HEART,
    "shimmer_emg": FIF.PEOPLE,
    "video": FIF.VIDEO,
    "audio": FIF.MICROPHONE,
    "markers": FIF.FLAG,
    "other": FIF.DOCUMENT,
}


class _TaskRow(SimpleCardWidget):
    """单个上传任务的行控件"""

    retry_clicked = pyqtSignal(str)
    remove_clicked = pyqtSignal(str)

    def __init__(self, task_id: str, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.setFixedHeight(68)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(12)

        self._icon = QLabel()
        self._icon.setFixedSize(28, 28)
        lay.addWidget(self._icon)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self._name_lbl = StrongBodyLabel("")
        self._detail_lbl = CaptionLabel("")
        info_col.addWidget(self._name_lbl)
        info_col.addWidget(self._detail_lbl)
        lay.addLayout(info_col, stretch=3)

        self._bar = ProgressBar()
        self._bar.setFixedWidth(180)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        lay.addWidget(self._bar, stretch=2)

        self._size_lbl = CaptionLabel("")
        self._size_lbl.setFixedWidth(70)
        self._size_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self._size_lbl)

        self._badge = InfoBadge("等待中")
        self._badge.setFixedHeight(22)
        self._badge.setFixedWidth(56)
        lay.addWidget(self._badge)

        self._retry_btn = ToolButton(FIF.SYNC)
        self._retry_btn.setFixedSize(30, 30)
        self._retry_btn.setToolTip("重试")
        self._retry_btn.setVisible(False)
        self._retry_btn.clicked.connect(lambda: self.retry_clicked.emit(self.task_id))
        lay.addWidget(self._retry_btn)

        self._rm_btn = ToolButton(FIF.DELETE)
        self._rm_btn.setFixedSize(30, 30)
        self._rm_btn.setToolTip("移除")
        self._rm_btn.clicked.connect(lambda: self.remove_clicked.emit(self.task_id))
        lay.addWidget(self._rm_btn)

    def update_from_task(self, task):
        fname = os.path.basename(task.file_path)
        self._name_lbl.setText(fname)
        self._detail_lbl.setText(f"{task.session_name} / {task.modality}")
        self._size_lbl.setText(UploadManager.format_size(task.file_size))

        icon_key = task.modality if task.modality in _MODALITY_ICONS else "other"
        icon = _MODALITY_ICONS[icon_key]
        self._icon.setPixmap(icon.icon().pixmap(24, 24))

        pct = 0
        if task.total_chunks > 0:
            pct = int(100 * task.uploaded_chunks / task.total_chunks)
        if task.status == UploadStatus.COMPLETED:
            pct = 100
        self._bar.setValue(pct)

        status_text = _STATUS_TEXT.get(task.status, task.status)
        if task.status == UploadStatus.FAILED and task.error:
            status_text = task.error[:20]
        self._badge.setText(status_text)
        self._badge.setLevel(_STATUS_LEVEL.get(task.status, InfoLevel.INFOAMTION))

        self._retry_btn.setVisible(task.status == UploadStatus.FAILED)
        can_remove = task.status in (
            UploadStatus.COMPLETED, UploadStatus.FAILED, UploadStatus.PENDING
        )
        self._rm_btn.setVisible(can_remove)


class UploadPage(SmoothScrollArea):
    """数据上传页面"""

    def __init__(self, upload_manager: UploadManager, parent=None):
        super().__init__(parent)
        self.setObjectName("uploadPage")
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea{background:transparent; border:none;}")

        self._mgr = upload_manager
        self._rows: Dict[str, _TaskRow] = {}

        self._build_ui()
        self._connect_signals()
        self._refresh_queue()

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._periodic_refresh)
        self._tick.start(2000)

    # ═══════════════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════════════

    def _build_ui(self):
        container = QWidget()
        container.setStyleSheet("QWidget{background:transparent;}")
        self.setWidget(container)

        self._lay = QVBoxLayout(container)
        self._lay.setContentsMargins(36, 28, 36, 28)
        self._lay.setSpacing(20)
        self._lay.setAlignment(Qt.AlignTop)

        self._build_server_card()
        self._build_summary_card()
        self._build_queue_card()

    # ── 服务器配置卡片 ──

    def _build_server_card(self):
        card = HeaderCardWidget(self)
        card.setTitle("服务器配置")

        row1 = QHBoxLayout()
        row1.setSpacing(12)
        lbl_url = StrongBodyLabel("地址")
        lbl_url.setFixedWidth(50)
        row1.addWidget(lbl_url)
        self._url_edit = LineEdit()
        self._url_edit.setPlaceholderText("https://your-server.com")
        self._url_edit.setText(self._mgr.server_url)
        self._url_edit.setClearButtonEnabled(True)
        row1.addWidget(self._url_edit, stretch=1)
        card.viewLayout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(12)
        lbl_key = StrongBodyLabel("密钥")
        lbl_key.setFixedWidth(50)
        row2.addWidget(lbl_key)
        self._key_edit = PasswordLineEdit()
        self._key_edit.setPlaceholderText("API Key")
        self._key_edit.setText(self._mgr.api_key)
        self._key_edit.setClearButtonEnabled(True)
        row2.addWidget(self._key_edit, stretch=1)
        card.viewLayout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(16)

        self._btn_save = PrimaryPushButton(FIF.SAVE, "保存配置")
        self._btn_save.setFixedHeight(36)
        self._btn_save.clicked.connect(self._on_save_config)
        row3.addWidget(self._btn_save)

        self._btn_test = PushButton(FIF.WIFI, "测试连接")
        self._btn_test.setFixedHeight(36)
        self._btn_test.clicked.connect(self._on_test_connection)
        row3.addWidget(self._btn_test)

        self._conn_lbl = CaptionLabel("未测试")
        self._conn_lbl.setAlignment(Qt.AlignVCenter)
        row3.addWidget(self._conn_lbl, stretch=1)

        row3.addStretch()

        auto_lbl = StrongBodyLabel("实验结束自动上传")
        row3.addWidget(auto_lbl)
        self._auto_sw = SwitchButton()
        self._auto_sw.setChecked(self._mgr.auto_upload)
        self._auto_sw.checkedChanged.connect(self._on_auto_changed)
        row3.addWidget(self._auto_sw)

        card.viewLayout.addLayout(row3)
        self._lay.addWidget(card)

    # ── 总览卡片 ──

    def _build_summary_card(self):
        card = SimpleCardWidget(self)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(24)

        self._total_lbl = SubtitleLabel("0 个文件")
        lay.addWidget(self._total_lbl)

        self._size_lbl = BodyLabel("总计 0 B")
        lay.addWidget(self._size_lbl)

        self._overall_bar = ProgressBar()
        self._overall_bar.setRange(0, 100)
        self._overall_bar.setValue(0)
        self._overall_bar.setFixedWidth(200)
        lay.addWidget(self._overall_bar)

        self._progress_lbl = CaptionLabel("0%")
        lay.addWidget(self._progress_lbl)

        lay.addStretch()

        self._btn_add = PushButton(FIF.FOLDER_ADD, "添加会话")
        self._btn_add.setFixedHeight(34)
        self._btn_add.clicked.connect(self._on_add_session)
        lay.addWidget(self._btn_add)

        self._btn_start = PrimaryPushButton(FIF.SEND, "开始上传")
        self._btn_start.setFixedHeight(34)
        self._btn_start.clicked.connect(self._on_start)
        lay.addWidget(self._btn_start)

        self._btn_pause = PushButton(FIF.PAUSE, "暂停")
        self._btn_pause.setFixedHeight(34)
        self._btn_pause.clicked.connect(self._on_pause)
        lay.addWidget(self._btn_pause)

        self._btn_clear = ToolButton(FIF.DELETE)
        self._btn_clear.setFixedSize(34, 34)
        self._btn_clear.setToolTip("清除已完成")
        self._btn_clear.clicked.connect(self._on_clear)
        lay.addWidget(self._btn_clear)

        self._lay.addWidget(card)

    # ── 队列列表 ──

    def _build_queue_card(self):
        self._queue_card = HeaderCardWidget(self)
        self._queue_card.setTitle("上传队列")

        self._empty_lbl = BodyLabel("暂无上传任务")
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._queue_card.viewLayout.addWidget(self._empty_lbl)

        self._lay.addWidget(self._queue_card)
        self._lay.addStretch()

    # ═══════════════════════════════════════════════════
    #  信号连接
    # ═══════════════════════════════════════════════════

    def _connect_signals(self):
        self._mgr.task_added.connect(self._on_task_added)
        self._mgr.task_progress.connect(self._on_task_progress)
        self._mgr.task_status_changed.connect(self._on_task_status_changed)
        self._mgr.task_completed.connect(self._on_task_completed)
        self._mgr.task_failed.connect(self._on_task_failed)
        self._mgr.queue_changed.connect(self._refresh_queue)
        self._mgr.all_completed.connect(self._on_all_completed)

    # ═══════════════════════════════════════════════════
    #  事件处理
    # ═══════════════════════════════════════════════════

    def _on_save_config(self):
        self._mgr.server_url = self._url_edit.text().strip()
        self._mgr.api_key = self._key_edit.text().strip()
        self._mgr.save_config()
        self._conn_lbl.setText("配置已保存")

    def _on_test_connection(self):
        self._conn_lbl.setText("测试中...")
        self._btn_test.setEnabled(False)

        self._mgr.server_url = self._url_edit.text().strip()
        self._mgr.api_key = self._key_edit.text().strip()

        import threading
        def _test():
            ok, msg = self._mgr.test_connection()
            self._pending_conn_result = (ok, msg)
        self._pending_conn_result = None
        threading.Thread(target=_test, daemon=True).start()
        self._conn_poll = QTimer(self)
        self._conn_poll.timeout.connect(self._check_conn_result)
        self._conn_poll.start(200)

    def _check_conn_result(self):
        if self._pending_conn_result is not None:
            self._conn_poll.stop()
            ok, msg = self._pending_conn_result
            self._pending_conn_result = None
            self._show_conn_result(ok, msg)

    def _show_conn_result(self, ok: bool, msg: str):
        self._btn_test.setEnabled(True)
        prefix = "OK" if ok else "FAIL"
        self._conn_lbl.setText(f"[{prefix}] {msg}")

    def _on_auto_changed(self, checked: bool):
        self._mgr.auto_upload = checked
        self._mgr.save_config()

    def _on_add_session(self):
        folder = QFileDialog.getExistingDirectory(
            self, "选择会话目录", "./data/sessions"
        )
        if folder:
            count = self._mgr.add_session(folder)
            logger.info("手动添加 %d 个文件", count)

    def _on_start(self):
        self._mgr.start()

    def _on_pause(self):
        self._mgr.pause()

    def _on_clear(self):
        self._mgr.clear_completed()

    # ── 管理器信号回调 ──

    def _on_task_added(self, task_id: str):
        self._ensure_row(task_id)
        self._update_summary()

    def _on_task_progress(self, task_id: str, uploaded: int, total: int):
        row = self._rows.get(task_id)
        if row:
            task = self._mgr.get_task(task_id)
            if task:
                row.update_from_task(task)
        self._update_summary()

    def _on_task_status_changed(self, task_id: str, status: str):
        row = self._rows.get(task_id)
        if row:
            task = self._mgr.get_task(task_id)
            if task:
                row.update_from_task(task)
        self._update_summary()

    def _on_task_completed(self, task_id: str):
        self._on_task_status_changed(task_id, UploadStatus.COMPLETED)

    def _on_task_failed(self, task_id: str, error: str):
        self._on_task_status_changed(task_id, UploadStatus.FAILED)

    def _on_all_completed(self):
        self._update_summary()

    # ═══════════════════════════════════════════════════
    #  队列渲染
    # ═══════════════════════════════════════════════════

    def _ensure_row(self, task_id: str):
        if task_id in self._rows:
            return
        task = self._mgr.get_task(task_id)
        if not task:
            return

        row = _TaskRow(task_id, self._queue_card)
        row.update_from_task(task)
        row.retry_clicked.connect(self._mgr.retry_task)
        row.remove_clicked.connect(self._on_remove_task)
        self._rows[task_id] = row
        self._queue_card.viewLayout.addWidget(row)
        self._empty_lbl.setVisible(False)

    def _on_remove_task(self, task_id: str):
        row = self._rows.pop(task_id, None)
        if row:
            self._queue_card.viewLayout.removeWidget(row)
            row.deleteLater()
        self._mgr.remove_task(task_id)
        self._update_summary()
        if not self._rows:
            self._empty_lbl.setVisible(True)

    def _refresh_queue(self):
        stale = set(self._rows.keys())
        for task in self._mgr.get_all_tasks():
            stale.discard(task.task_id)
            self._ensure_row(task.task_id)
            row = self._rows.get(task.task_id)
            if row:
                row.update_from_task(task)

        for tid in stale:
            row = self._rows.pop(tid, None)
            if row:
                self._queue_card.viewLayout.removeWidget(row)
                row.deleteLater()

        self._empty_lbl.setVisible(len(self._rows) == 0)
        self._update_summary()

    def _update_summary(self):
        tasks = self._mgr.get_all_tasks()
        total_files = len(tasks)
        total_size = sum(t.file_size for t in tasks)
        done, full = self._mgr.get_total_progress()
        pct = int(100 * done / full) if full > 0 else 0

        self._total_lbl.setText(f"{total_files} 个文件")
        self._size_lbl.setText(f"总计 {UploadManager.format_size(total_size)}")
        self._overall_bar.setValue(pct)
        self._progress_lbl.setText(f"{pct}%")

    def _periodic_refresh(self):
        for task in self._mgr.get_all_tasks():
            row = self._rows.get(task.task_id)
            if row and task.status in (UploadStatus.UPLOADING, UploadStatus.COMPRESSING):
                row.update_from_task(task)
        self._update_summary()

    # ═══════════════════════════════════════════════════
    #  外部接口：实验结束后触发上传
    # ═══════════════════════════════════════════════════

    def enqueue_session(self, session_dir: str):
        """由实验完成信号调用，将会话数据加入上传队列。"""
        count = self._mgr.add_session(session_dir)
        if count > 0 and self._mgr.auto_upload:
            self._mgr.start()
        logger.info("实验结束，%d 个文件加入上传队列", count)
