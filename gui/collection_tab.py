"""
数据采集Tab
提供数据采集的界面和控制
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QGroupBox, QTextEdit, QLineEdit, QMessageBox,
    QFormLayout, QFrame, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from datetime import datetime

from database.database_manager import DatabaseManager
from managers.session_manager import SessionManager
from database.models import Patient
from .device_controller import DeviceController


class CollectionTab(QWidget):
    """数据采集Tab"""

    def __init__(self, db_manager: DatabaseManager, session_manager: SessionManager):
        """
        初始化数据采集Tab

        Args:
            db_manager: 数据库管理器实例
            session_manager: 会话管理器实例
        """
        super().__init__()
        self.db = db_manager
        self.sm = session_manager

        # 当前状态
        self.current_patient = None
        self.current_session = None
        self.is_collecting = False

        # 设备控制器
        self.device_controller = None

        # 设备状态
        self.device_status = {
            'shimmer': False,
            'video': False,
            'audio': False
        }

        self.init_ui()
        self.load_patients()

        # 状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_collection_status)
        self.status_timer.start(1000)  # 每秒更新一次

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 患者选择区域
        patient_group = self.create_patient_selection()
        layout.addWidget(patient_group)

        # 会话信息区域
        session_group = self.create_session_info()
        layout.addWidget(session_group)

        # 设备状态区域
        device_group = self.create_device_status()
        layout.addWidget(device_group)

        # 采集控制区域
        control_group = self.create_control_panel()
        layout.addWidget(control_group)

        # 采集进度区域
        progress_group = self.create_progress_panel()
        layout.addWidget(progress_group)

        # 日志区域
        log_group = self.create_log_panel()
        layout.addWidget(log_group)

        layout.addStretch()
        self.setLayout(layout)

    def create_patient_selection(self) -> QGroupBox:
        """创建患者选择区域"""
        group = QGroupBox("1. 选择患者")
        group.setStyleSheet("QGroupBox { font-weight: bold; }")

        layout = QHBoxLayout()

        # 患者下拉框
        self.patient_combo = QComboBox()
        self.patient_combo.setMinimumWidth(300)
        self.patient_combo.currentIndexChanged.connect(self.on_patient_selected)
        layout.addWidget(QLabel("患者:"))
        layout.addWidget(self.patient_combo)

        # 刷新按钮
        btn_refresh = QPushButton("🔄 刷新")
        btn_refresh.clicked.connect(self.load_patients)
        layout.addWidget(btn_refresh)

        layout.addStretch()

        # 患者信息显示
        self.patient_info_label = QLabel("未选择患者")
        self.patient_info_label.setStyleSheet("color: gray;")
        layout.addWidget(self.patient_info_label)

        group.setLayout(layout)
        return group

    def create_session_info(self) -> QGroupBox:
        """创建会话信息区域"""
        group = QGroupBox("2. 会话信息")
        group.setStyleSheet("QGroupBox { font-weight: bold; }")

        layout = QFormLayout()

        # 会话名称
        self.session_name_input = QLineEdit()
        self.session_name_input.setPlaceholderText("例如: 基线测试")
        layout.addRow("会话名称:", self.session_name_input)

        # 备注
        self.session_notes_input = QLineEdit()
        self.session_notes_input.setPlaceholderText("备注信息（可选）")
        layout.addRow("备注:", self.session_notes_input)

        # 创建会话按钮
        self.btn_create_session = QPushButton("📝 创建会话")
        self.btn_create_session.clicked.connect(self.create_session)
        self.btn_create_session.setEnabled(False)
        layout.addRow("", self.btn_create_session)

        # 当前会话状态
        self.session_status_label = QLabel("未创建会话")
        self.session_status_label.setStyleSheet("color: gray;")
        layout.addRow("状态:", self.session_status_label)

        group.setLayout(layout)
        return group

    def create_device_status(self) -> QGroupBox:
        """创建设备状态区域"""
        group = QGroupBox("3. 设备状态")
        group.setStyleSheet("QGroupBox { font-weight: bold; }")

        layout = QVBoxLayout()

        # Shimmer设备
        shimmer_layout = QHBoxLayout()
        shimmer_layout.addWidget(QLabel("Shimmer GSR+:"))
        self.shimmer_status_label = self.create_status_label("未连接")
        shimmer_layout.addWidget(self.shimmer_status_label)
        self.btn_connect_shimmer = QPushButton("连接")
        self.btn_connect_shimmer.clicked.connect(lambda: self.toggle_device('shimmer'))
        shimmer_layout.addWidget(self.btn_connect_shimmer)
        shimmer_layout.addStretch()
        layout.addLayout(shimmer_layout)

        # 视频设备
        video_layout = QHBoxLayout()
        video_layout.addWidget(QLabel("视频摄像头:"))
        self.video_status_label = self.create_status_label("未连接")
        video_layout.addWidget(self.video_status_label)
        self.btn_connect_video = QPushButton("连接")
        self.btn_connect_video.clicked.connect(lambda: self.toggle_device('video'))
        video_layout.addWidget(self.btn_connect_video)
        video_layout.addStretch()
        layout.addLayout(video_layout)

        # 音频设备
        audio_layout = QHBoxLayout()
        audio_layout.addWidget(QLabel("音频麦克风:"))
        self.audio_status_label = self.create_status_label("未连接")
        audio_layout.addWidget(self.audio_status_label)
        self.btn_connect_audio = QPushButton("连接")
        self.btn_connect_audio.clicked.connect(lambda: self.toggle_device('audio'))
        audio_layout.addWidget(self.btn_connect_audio)
        audio_layout.addStretch()
        layout.addLayout(audio_layout)

        group.setLayout(layout)
        return group

    def create_control_panel(self) -> QGroupBox:
        """创建采集控制区域"""
        group = QGroupBox("4. 采集控制")
        group.setStyleSheet("QGroupBox { font-weight: bold; }")

        layout = QHBoxLayout()

        # 开始采集按钮
        self.btn_start = QPushButton("▶️ 开始采集 (空格)")
        self.btn_start.setMinimumHeight(50)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.btn_start.clicked.connect(self.start_collection)
        self.btn_start.setEnabled(False)
        layout.addWidget(self.btn_start)

        # 停止采集按钮
        self.btn_stop = QPushButton("⏹️ 停止采集 (空格)")
        self.btn_stop.setMinimumHeight(50)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.btn_stop.clicked.connect(self.stop_collection)
        self.btn_stop.setEnabled(False)
        layout.addWidget(self.btn_stop)

        group.setLayout(layout)
        return group

    def create_progress_panel(self) -> QGroupBox:
        """创建采集进度面板"""
        group = QGroupBox("📊 采集进度")
        group.setStyleSheet("QGroupBox { font-weight: bold; }")

        layout = QVBoxLayout()

        # 时长显示
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("采集时长:"))
        self.time_label = QLabel("00:00:00")
        self.time_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2196F3;")
        time_layout.addWidget(self.time_label)
        time_layout.addStretch()
        layout.addLayout(time_layout)

        # 数据量显示
        stats_layout = QHBoxLayout()
        self.shimmer_samples_label = QLabel("Shimmer: 0 samples")
        self.video_frames_label = QLabel("Video: 0 frames")
        self.audio_samples_label = QLabel("Audio: 0 samples")
        stats_layout.addWidget(self.shimmer_samples_label)
        stats_layout.addWidget(self.video_frames_label)
        stats_layout.addWidget(self.audio_samples_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        group.setLayout(layout)
        return group

    def create_log_panel(self) -> QGroupBox:
        """创建日志面板"""
        group = QGroupBox("📋 操作日志")
        group.setStyleSheet("QGroupBox { font-weight: bold; }")

        layout = QVBoxLayout()

        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                font-family: Consolas, monospace;
                font-size: 10px;
            }
        """)
        layout.addWidget(self.log_text)

        # 清除日志按钮
        btn_clear_log = QPushButton("清除日志")
        btn_clear_log.clicked.connect(self.log_text.clear)
        layout.addWidget(btn_clear_log)

        group.setLayout(layout)
        return group

    def create_status_label(self, text: str) -> QLabel:
        """创建状态标签"""
        label = QLabel(text)
        label.setMinimumWidth(80)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                padding: 5px;
                border-radius: 3px;
                background-color: #ffcccc;
                color: #cc0000;
                font-weight: bold;
            }
        """)
        return label

    def load_patients(self):
        """加载患者列表"""
        self.patient_combo.clear()
        self.patient_combo.addItem("-- 请选择患者 --", None)

        patients = self.db.get_all_patients()
        for patient in patients:
            display_text = f"{patient.name} (ID: {patient.patient_id})"
            if patient.age:
                display_text += f" - {patient.age}岁"
            if patient.diagnosis:
                display_text += f" - {patient.diagnosis}"

            self.patient_combo.addItem(display_text, patient)

        self.log_message(f"加载了 {len(patients)} 位患者")

    def on_patient_selected(self, index):
        """患者选择改变"""
        if index <= 0:
            self.current_patient = None
            self.patient_info_label.setText("未选择患者")
            self.patient_info_label.setStyleSheet("color: gray;")
            self.btn_create_session.setEnabled(False)
            return

        self.current_patient = self.patient_combo.itemData(index)

        # 显示患者信息
        info = f"✓ {self.current_patient.name}"
        if self.current_patient.age:
            info += f", {self.current_patient.age}岁"
        if self.current_patient.gender:
            gender_map = {'M': '男', 'F': '女', 'Other': '其他'}
            info += f", {gender_map.get(self.current_patient.gender, '')}"

        self.patient_info_label.setText(info)
        self.patient_info_label.setStyleSheet("color: green; font-weight: bold;")
        self.btn_create_session.setEnabled(True)

        self.log_message(f"选择患者: {self.current_patient.name} (ID: {self.current_patient.patient_id})")

    def create_session(self):
        """创建会话"""
        if not self.current_patient:
            QMessageBox.warning(self, "警告", "请先选择患者")
            return

        session_name = self.session_name_input.text().strip()
        if not session_name:
            QMessageBox.warning(self, "警告", "请输入会话名称")
            self.session_name_input.setFocus()
            return

        notes = self.session_notes_input.text().strip()

        # 创建会话
        try:
            self.current_session = self.sm.create_session(
                self.current_patient.patient_id,
                session_name,
                notes
            )

            if self.current_session:
                self.session_status_label.setText(f"✓ 会话已创建: {session_name}")
                self.session_status_label.setStyleSheet("color: green; font-weight: bold;")

                # 启动会话
                self.sm.start_session(self.current_session.session_id)

                # 创建设备控制器
                session_paths = self.sm.get_current_session_paths()
                self.device_controller = DeviceController(session_paths)
                self.device_controller.set_status_callback(self.log_message)

                self.log_message(f"会话创建成功: {session_name} (ID: {self.current_session.session_id})")
                self.log_message(f"数据保存路径: {self.current_session.data_path}")

                # 禁用会话创建，启用设备控制
                self.btn_create_session.setEnabled(False)
                self.session_name_input.setEnabled(False)
                self.session_notes_input.setEnabled(False)

                QMessageBox.information(self, "成功", f"会话 '{session_name}' 创建成功！\n\n现在可以连接设备了")
            else:
                QMessageBox.critical(self, "错误", "创建会话失败")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建会话失败: {str(e)}")
            self.log_message(f"错误: {str(e)}")

    def toggle_device(self, device: str):
        """切换设备连接状态"""
        if not self.device_controller:
            QMessageBox.warning(self, "警告", "请先创建会话")
            return

        current_status = self.device_status[device]

        # 禁用按钮，防止重复点击
        if device == 'shimmer':
            self.btn_connect_shimmer.setEnabled(False)
        elif device == 'video':
            self.btn_connect_video.setEnabled(False)
        else:
            self.btn_connect_audio.setEnabled(False)

        if not current_status:
            # 连接设备
            success = False
            if device == 'shimmer':
                success = self.device_controller.initialize_shimmer()
            elif device == 'video':
                success = self.device_controller.initialize_video()
            else:
                success = self.device_controller.initialize_audio()

            if success:
                self.device_status[device] = True
                self.update_device_ui(device, True)
            else:
                QMessageBox.warning(self, "连接失败", f"{device.upper()} 设备连接失败")
        else:
            # 断开设备
            if device == 'shimmer':
                self.device_controller.disconnect_shimmer()
            elif device == 'video':
                self.device_controller.disconnect_video()
            else:
                self.device_controller.disconnect_audio()

            self.device_status[device] = False
            self.update_device_ui(device, False)

        # 重新启用按钮
        if device == 'shimmer':
            self.btn_connect_shimmer.setEnabled(True)
        elif device == 'video':
            self.btn_connect_video.setEnabled(True)
        else:
            self.btn_connect_audio.setEnabled(True)

        self.check_ready_to_collect()

    def update_device_ui(self, device: str, connected: bool):
        """更新设备UI状态"""
        if device == 'shimmer':
            label = self.shimmer_status_label
            button = self.btn_connect_shimmer
        elif device == 'video':
            label = self.video_status_label
            button = self.btn_connect_video
        else:
            label = self.audio_status_label
            button = self.btn_connect_audio

        if connected:
            label.setText("✓ 已连接")
            label.setStyleSheet("""
                QLabel {
                    padding: 5px;
                    border-radius: 3px;
                    background-color: #ccffcc;
                    color: #008000;
                    font-weight: bold;
                }
            """)
            button.setText("断开")
        else:
            label.setText("未连接")
            label.setStyleSheet("""
                QLabel {
                    padding: 5px;
                    border-radius: 3px;
                    background-color: #ffcccc;
                    color: #cc0000;
                    font-weight: bold;
                }
            """)
            button.setText("连接")

    def check_ready_to_collect(self):
        """检查是否准备好开始采集"""
        ready = (
            self.current_session is not None and
            self.device_controller is not None and
            any(self.device_status.values())  # 至少有一个设备连接
        )

        self.btn_start.setEnabled(ready and not self.is_collecting)

    def start_collection(self):
        """开始采集"""
        if not self.current_session:
            QMessageBox.warning(self, "警告", "请先创建会话")
            return

        if not self.device_controller:
            QMessageBox.warning(self, "警告", "设备控制器未初始化")
            return

        # 检查设备状态
        connected_devices = [d for d, status in self.device_status.items() if status]
        if not connected_devices:
            QMessageBox.warning(self, "警告", "请至少连接一个设备")
            return

        # 开始录制
        success = self.device_controller.start_recording()

        if success:
            self.is_collecting = True
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)

            # 禁用设备连接按钮
            self.btn_connect_shimmer.setEnabled(False)
            self.btn_connect_video.setEnabled(False)
            self.btn_connect_audio.setEnabled(False)

            # 记录开始时间
            self.collection_start_time = datetime.now()
        else:
            QMessageBox.critical(self, "错误", "启动采集失败")

    def stop_collection(self):
        """停止采集"""
        if not self.is_collecting or not self.device_controller:
            return

        # 停止录制
        stats = self.device_controller.stop_recording()

        self.is_collecting = False
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)

        # 启用设备连接按钮
        self.btn_connect_shimmer.setEnabled(True)
        self.btn_connect_video.setEnabled(True)
        self.btn_connect_audio.setEnabled(True)

        # 结束会话
        if self.current_session:
            duration = stats.get('duration', 0)
            self.sm.end_session(duration=duration, quality_score=0.95)
            self.log_message(f"会话已结束，时长: {duration}秒")

        # 显示统计信息
        stats_msg = f"采集完成！\n\n时长: {stats.get('duration', 0)}秒\n"
        stats_msg += f"设备: {', '.join([d.upper() for d in stats.get('devices', [])])}"

        QMessageBox.information(self, "采集完成", stats_msg)

        # 重置状态
        self.reset_session()

    def update_collection_status(self):
        """更新采集状态（定时器调用）"""
        if self.is_collecting and hasattr(self, 'collection_start_time'):
            # 更新时长显示
            elapsed = (datetime.now() - self.collection_start_time).total_seconds()
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            self.time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

            # 更新数据量显示（从设备控制器获取）
            if self.device_controller and hasattr(self.device_controller, 'recorder') and self.device_controller.recorder:
                try:
                    recorder = self.device_controller.recorder

                    # Shimmer样本数
                    if hasattr(recorder, 'shimmer_saver') and recorder.shimmer_saver and hasattr(recorder.shimmer_saver, 'buffer'):
                        shimmer_count = len(recorder.shimmer_saver.buffer)
                        self.shimmer_samples_label.setText(f"Shimmer: {shimmer_count} samples")

                    # 视频帧数
                    if hasattr(recorder, 'video_frame_count'):
                        self.video_frames_label.setText(f"Video: {recorder.video_frame_count} frames")

                    # 音频样本数
                    if hasattr(recorder, 'audio_buffer'):
                        audio_count = len(recorder.audio_buffer)
                        self.audio_samples_label.setText(f"Audio: {audio_count} samples")

                except Exception as e:
                    pass  # 静默失败

    def reset_session(self):
        """重置会话状态"""
        # 清理设备控制器
        if self.device_controller:
            self.device_controller.cleanup()
            self.device_controller = None

        # 重置设备状态
        for device in self.device_status:
            self.device_status[device] = False
            self.update_device_ui(device, False)

        # 重置UI
        self.current_session = None
        self.session_name_input.clear()
        self.session_notes_input.clear()
        self.session_name_input.setEnabled(True)
        self.session_notes_input.setEnabled(True)
        self.session_status_label.setText("未创建会话")
        self.session_status_label.setStyleSheet("color: gray;")
        self.btn_create_session.setEnabled(self.current_patient is not None)
        self.btn_start.setEnabled(False)

        # 重置进度显示
        self.time_label.setText("00:00:00")
        self.shimmer_samples_label.setText("Shimmer: 0 samples")
        self.video_frames_label.setText("Video: 0 frames")
        self.audio_samples_label.setText("Audio: 0 samples")

    def log_message(self, message: str):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def keyPressEvent(self, event):
        """键盘事件 - 空格键控制"""
        if event.key() == Qt.Key_Space:
            if self.btn_start.isEnabled():
                self.start_collection()
            elif self.btn_stop.isEnabled():
                self.stop_collection()
        else:
            super().keyPressEvent(event)