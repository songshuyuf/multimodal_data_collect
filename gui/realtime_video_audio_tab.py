"""
实时视音频显示Tab
显示视频预览和音频波形
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFrame, QSplitter
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
import numpy as np
import cv2

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False


class RealtimeVideoAudioTab(QWidget):
    """实时视音频显示Tab"""

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

        # 标题
        title_label = QLabel("🎥 视频 + 🎤 音频 实时监测")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2196F3;
                padding: 10px;
                background-color: #e3f2fd;
                border-radius: 5px;
            }
        """)
        layout.addWidget(title_label)

        # 使用分割器分为上下两部分
        splitter = QSplitter(Qt.Vertical)

        # === 上部：视频预览 ===
        video_group = QGroupBox("📹 视频预览")
        video_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        video_layout = QVBoxLayout()

        # 视频显示
        self.video_label = QLabel("📹 摄像头未连接\n\n请在"'数据采集'"Tab中连接视频设备并开始采集")
        self.video_label.setMinimumSize(640, 480)
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

        # 视频信息面板
        video_info_frame = QFrame()
        video_info_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f4ff;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        video_info_layout = QHBoxLayout()
        video_info_layout.setContentsMargins(10, 5, 10, 5)

        self.video_fps_label = QLabel("FPS: --")
        self.video_resolution_label = QLabel("分辨率: --")
        self.video_frames_label = QLabel("已录制: 0 帧")
        self.video_codec_label = QLabel("编码: MP4V")
        self.video_duration_label = QLabel("时长: 00:00")

        for label in [self.video_fps_label, self.video_resolution_label,
                     self.video_frames_label, self.video_codec_label, self.video_duration_label]:
            label.setStyleSheet("font-size: 11px; padding: 3px; color: #333;")
            video_info_layout.addWidget(label)

        video_info_layout.addStretch()
        video_info_frame.setLayout(video_info_layout)
        video_layout.addWidget(video_info_frame)

        video_group.setLayout(video_layout)
        splitter.addWidget(video_group)

        # === 下部：音频波形 ===
        audio_group = QGroupBox("🎤 音频波形")
        audio_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        audio_layout = QVBoxLayout()

        if PYQTGRAPH_AVAILABLE:
            # 音频波形显示
            self.audio_plot = pg.PlotWidget()
            self.audio_plot.setBackground('w')
            self.audio_plot.setLabel('left', '振幅', **{'font-size': '12pt'})
            self.audio_plot.setLabel('bottom', '时间', units='s', **{'font-size': '12pt'})
            self.audio_plot.showGrid(x=True, y=True, alpha=0.3)
            self.audio_curve = self.audio_plot.plot(pen=pg.mkPen(color='c', width=2))

            # 音频频谱显示
            self.spectrum_plot = pg.PlotWidget()
            self.spectrum_plot.setBackground('w')
            self.spectrum_plot.setLabel('left', '幅度', **{'font-size': '12pt'})
            self.spectrum_plot.setLabel('bottom', '频率', units='Hz', **{'font-size': '12pt'})
            self.spectrum_plot.showGrid(x=True, y=True, alpha=0.3)
            self.spectrum_curve = self.spectrum_plot.plot(pen=pg.mkPen(color='m', width=2), fillLevel=0, brush='m')

            self.audio_buffer_size = 4000

            # 创建分割器显示波形和频谱
            audio_splitter = QSplitter(Qt.Horizontal)
            audio_splitter.addWidget(self.audio_plot)
            audio_splitter.addWidget(self.spectrum_plot)
            audio_splitter.setStretchFactor(0, 1)
            audio_splitter.setStretchFactor(1, 1)

            audio_layout.addWidget(audio_splitter)
        else:
            no_plot_label = QLabel("⚠️ 音频波形显示不可用\n\n请安装: pip install pyqtgraph")
            no_plot_label.setAlignment(Qt.AlignCenter)
            no_plot_label.setStyleSheet("color: #999; font-size: 14px; padding: 30px;")
            audio_layout.addWidget(no_plot_label)

        # 音频信息面板
        audio_info_frame = QFrame()
        audio_info_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f4ff;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        audio_info_layout = QHBoxLayout()
        audio_info_layout.setContentsMargins(10, 5, 10, 5)

        self.audio_level_label = QLabel("🔊 音量: -- dB")
        self.audio_peak_label = QLabel("峰值: --")
        self.audio_rms_label = QLabel("RMS: --")
        self.audio_samples_label = QLabel("已采样: 0")
        self.audio_rate_label = QLabel("采样率: 44100 Hz")
        self.audio_channels_label = QLabel("声道: 单声道")

        for label in [self.audio_level_label, self.audio_peak_label,
                     self.audio_rms_label, self.audio_samples_label,
                     self.audio_rate_label, self.audio_channels_label]:
            label.setStyleSheet("font-size: 11px; padding: 3px; color: #333;")
            audio_info_layout.addWidget(label)

        audio_info_layout.addStretch()
        audio_info_frame.setLayout(audio_info_layout)
        audio_layout.addWidget(audio_info_frame)

        audio_group.setLayout(audio_layout)
        splitter.addWidget(audio_group)

        # 设置分割比例
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)

        layout.addWidget(splitter)
        self.setLayout(layout)

    def update_display(self):
        """更新显示"""
        # 检查采集状态
        if not hasattr(self.collection_tab, 'is_collecting') or not self.collection_tab.is_collecting:
            print("DEBUG Video: 未在采集")
            return

        try:
            print("DEBUG Video: 开始获取 recorder")
            recorder = self.collection_tab.device_controller.recorder

            if not recorder:
                print("DEBUG Video: recorder 为 None")
                return

            # 更新视频（从共享帧）
            if hasattr(recorder, 'current_video_frame'):
                if recorder.current_video_frame is not None:
                    print(f"DEBUG Video: 有视频帧，大小: {recorder.current_video_frame.shape}")

                    frame = recorder.current_video_frame

                    # 转换为Qt格式
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = frame_rgb.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

                    # 显示
                    pixmap = QPixmap.fromImage(qt_image)
                    scaled = pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.video_label.setPixmap(scaled)

                    # 更新信息
                    if hasattr(recorder, 'video_cap') and recorder.video_cap:
                        fps = recorder.video_cap.get(cv2.CAP_PROP_FPS)
                        self.video_fps_label.setText(f"FPS: {fps:.1f}")
                        self.video_resolution_label.setText(f"分辨率: {w}x{h}")

                    if hasattr(recorder, 'video_frame_count'):
                        count = recorder.video_frame_count
                        self.video_frames_label.setText(f"已录制: {count} 帧")

                        # 时长
                        if hasattr(recorder, 'video_cap') and recorder.video_cap:
                            fps = recorder.video_cap.get(cv2.CAP_PROP_FPS)
                            if fps > 0:
                                sec = count / fps
                                m, s = int(sec // 60), int(sec % 60)
                                self.video_duration_label.setText(f"时长: {m:02d}:{s:02d}")
                else:
                    print("DEBUG Video: current_video_frame 为 None")
            else:
                print("DEBUG Video: recorder 没有 current_video_frame 属性")

            # 更新音频
            if PYQTGRAPH_AVAILABLE and hasattr(recorder, 'audio_buffer') and len(recorder.audio_buffer) > 0:
                audio = np.array(recorder.audio_buffer[-self.audio_buffer_size:], dtype=np.float32)
                print(f"DEBUG Audio: 音频样本数: {len(audio)}")

                if len(audio) > 0:
                    rms = np.sqrt(np.mean(audio ** 2))
                    peak = np.max(np.abs(audio))
                    db = 20 * np.log10(rms) if rms > 0 else -100

                    self.audio_level_label.setText(f"🔊 音量: {db:.1f} dB")
                    self.audio_peak_label.setText(f"峰值: {peak:.3f}")
                    self.audio_rms_label.setText(f"RMS: {rms:.3f}")
                    self.audio_samples_label.setText(f"已采样: {len(recorder.audio_buffer)}")

                    # 波形
                    if len(audio) >= self.audio_buffer_size:
                        time_array = np.arange(self.audio_buffer_size) / 44100.0
                        self.audio_curve.setData(time_array, audio)

                        # 频谱
                        try:
                            fft = np.fft.fft(audio)
                            freq = np.fft.fftfreq(len(audio), 1 / 44100.0)
                            pos_idx = freq > 0
                            freq = freq[pos_idx]
                            mag = np.abs(fft[pos_idx])

                            mask = freq < 5000
                            freq = freq[mask]
                            mag = mag[mask]
                            mag_db = 20 * np.log10(mag + 1e-10)

                            self.spectrum_curve.setData(freq, mag_db)
                        except:
                            pass

        except Exception as e:
            print(f"DEBUG Video: 发生异常: {e}")
            import traceback
            traceback.print_exc()