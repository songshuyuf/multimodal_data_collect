"""
实时视频显示Tab - 独立版本
只显示视频预览，画面更大
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFrame
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
import cv2


class RealtimeVideoTab(QWidget):
    """实时视频显示Tab"""

    def __init__(self, collection_tab):
        """
        初始化

        Args:
            collection_tab: 数据采集Tab的引用
        """
        super().__init__()
        self.collection_tab = collection_tab

        self.init_ui()

        # 定时更新
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(50)  # 50ms更新一次，20fps

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        from app.monitors import _is_dark, tint
        title_label = QLabel("🎥 视频实时监测")
        _tbg = tint('#2196F3', 25) if _is_dark() else '#e3f2fd'
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: bold;
                color: #2196F3;
                padding: 10px;
                background-color: {_tbg};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(title_label)

        # 视频预览区域
        video_group = QGroupBox("📹 视频预览")
        video_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        video_layout = QVBoxLayout()

        # 视频显示 - 更大的尺寸
        self.video_label = QLabel("📹 摄像头未连接\n\n请在\"设备监控\"Tab中连接视频设备并开始实验")
        self.video_label.setMinimumHeight(480)  # 增大最小高度
        self.video_label.setScaledContents(False)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                color: #666;
                border: 2px solid #333;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        video_layout.addWidget(self.video_label)

        video_group.setLayout(video_layout)
        layout.addWidget(video_group, stretch=3)  # 给视频更多空间

        # 视频信息面板
        info_group = QGroupBox("📊 视频信息")
        info_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        info_layout = QVBoxLayout()

        dark = _is_dark()
        _tc = '#d4d4d4' if dark else '#333'
        def _vs(bg_light):
            bg = tint(bg_light, 50) if dark else bg_light
            return f"QLabel{{font-size:13px;padding:8px 15px;background-color:{bg};border-radius:5px;color:{_tc};font-weight:bold;}}"

        row1_layout = QHBoxLayout()
        self.video_status_label = QLabel("状态: 未连接")
        self.video_fps_label = QLabel("FPS: --")
        self.video_resolution_label = QLabel("分辨率: --")
        for label in [self.video_status_label, self.video_fps_label, self.video_resolution_label]:
            label.setStyleSheet(_vs('#f0f4ff'))
            row1_layout.addWidget(label)
        info_layout.addLayout(row1_layout)

        row2_layout = QHBoxLayout()
        self.video_frames_label = QLabel("已录制: 0 帧")
        self.video_codec_label = QLabel("编码: MP4V")
        self.video_duration_label = QLabel("录制时长: 00:00")
        for label in [self.video_frames_label, self.video_codec_label, self.video_duration_label]:
            label.setStyleSheet(_vs('#fff4f0'))
            row2_layout.addWidget(label)
        info_layout.addLayout(row2_layout)

        row3_layout = QHBoxLayout()
        self.avg_fps_label = QLabel("平均FPS: --")
        self.frame_drop_label = QLabel("丢帧: 0")
        self.bitrate_label = QLabel("码率: -- Mbps")
        for label in [self.avg_fps_label, self.frame_drop_label, self.bitrate_label]:
            label.setStyleSheet(_vs('#f0fff4'))
            row3_layout.addWidget(label)

        info_layout.addLayout(row3_layout)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group, stretch=1)  # 信息区占较小空间

        self.setLayout(layout)

    def update_display(self):
        """更新显示"""
        if not hasattr(self.collection_tab, 'device_controller') or not self.collection_tab.device_controller:
            return

        device_controller = self.collection_tab.device_controller

        # 更新视频
        self.update_video(device_controller)

    @staticmethod
    def _status_style(bg_hex, fg_hex):
        from app.monitors import _is_dark, tint
        bg = tint(bg_hex, 50) if _is_dark() else bg_hex
        return f"QLabel{{font-size:13px;padding:8px 15px;background-color:{bg};border-radius:5px;color:{fg_hex};font-weight:bold;}}"

    def update_video(self, device_controller):
        """更新视频显示"""
        try:
            if not hasattr(device_controller, 'video_connected') or not device_controller.video_connected:
                self.video_status_label.setText("状态: 未连接")
                self.video_status_label.setStyleSheet(self._status_style('#ffcccc', '#cc0000'))
                return

            if hasattr(device_controller, 'is_recording') and device_controller.is_recording:
                self.video_status_label.setText("状态: 🔴 录制中")
                self.video_status_label.setStyleSheet(self._status_style('#ffcccc', '#cc0000'))
            else:
                self.video_status_label.setText("状态: ⚪ 已连接")
                self.video_status_label.setStyleSheet(self._status_style('#c8e6c9', '#2e7d32'))

            # 获取最新帧
            frame = device_controller.get_latest_video_frame()
            if frame is not None:
                # 转换为QImage
                height, width, channel = frame.shape
                bytes_per_line = 3 * width
                q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()

                # 缩放图片以适应标签（保持宽高比）
                pixmap = QPixmap.fromImage(q_img)
                scaled_pixmap = pixmap.scaled(
                    self.video_label.width(),
                    self.video_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.video_label.setPixmap(scaled_pixmap)

                # 更新统计信息
                fps = device_controller.get_video_fps()
                frame_count = device_controller.video_frame_count

                self.video_fps_label.setText(f"FPS: {fps:.1f}")
                self.video_resolution_label.setText(f"分辨率: {width}x{height}")
                self.video_frames_label.setText(f"已录制: {frame_count} 帧")

                # 计算时长
                if fps > 0 and frame_count > 0:
                    duration_sec = frame_count / fps
                    minutes = int(duration_sec // 60)
                    seconds = int(duration_sec % 60)
                    self.video_duration_label.setText(f"录制时长: {minutes:02d}:{seconds:02d}")

                # 计算平均FPS
                if hasattr(device_controller, 'start_time') and device_controller.start_time:
                    from datetime import datetime
                    elapsed = (datetime.now() - device_controller.start_time).total_seconds()
                    if elapsed > 0:
                        avg_fps = frame_count / elapsed
                        self.avg_fps_label.setText(f"平均FPS: {avg_fps:.1f}")

        except Exception as e:
            pass  # 静默处理错误