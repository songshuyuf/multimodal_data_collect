"""
实时音频显示Tab - 独立版本
显示音频波形、频谱和详细信息
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFrame, QGridLayout
from PyQt5.QtCore import Qt, QTimer
import numpy as np

try:
    import pyqtgraph as pg

    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False


class RealtimeAudioTab(QWidget):
    """实时音频显示Tab"""

    def __init__(self, collection_tab):
        """
        初始化

        Args:
            collection_tab: 数据采集Tab的引用
        """
        super().__init__()
        self.collection_tab = collection_tab
        self.audio_buffer_size = 4000

        self.init_ui()

        # 定时更新
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(50)  # 50ms更新一次

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 标题
        from app.monitors import _is_dark, tint
        title_label = QLabel("🎤 音频实时监测")
        _tbg = tint('#FF9800', 25) if _is_dark() else '#fff4e6'
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: bold;
                color: #FF9800;
                padding: 10px;
                background-color: {_tbg};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(title_label)

        if PYQTGRAPH_AVAILABLE:
            from app.monitors import theme_pg_plot

            waveform_group = QGroupBox("🌊 时域波形")
            waveform_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
            waveform_layout = QVBoxLayout()

            self.audio_plot = pg.PlotWidget()
            theme_pg_plot(self.audio_plot)
            self.audio_plot.setLabel('left', '振幅', **{'font-size': '14pt'})
            self.audio_plot.setLabel('bottom', '时间', units='s', **{'font-size': '14pt'})
            self.audio_plot.showGrid(x=True, y=True, alpha=0.3)
            self.audio_plot.setMinimumHeight(280)
            self.audio_curve = self.audio_plot.plot(pen=pg.mkPen(color='#2196F3', width=2))

            waveform_layout.addWidget(self.audio_plot)
            waveform_group.setLayout(waveform_layout)
            layout.addWidget(waveform_group, stretch=2)

            spectrum_group = QGroupBox("📊 频域频谱")
            spectrum_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
            spectrum_layout = QVBoxLayout()

            self.spectrum_plot = pg.PlotWidget()
            theme_pg_plot(self.spectrum_plot)
            self.spectrum_plot.setLabel('left', '幅度 (dB)', **{'font-size': '14pt'})
            self.spectrum_plot.setLabel('bottom', '频率', units='Hz', **{'font-size': '14pt'})
            self.spectrum_plot.showGrid(x=True, y=True, alpha=0.3)
            self.spectrum_plot.setMinimumHeight(280)
            self.spectrum_curve = self.spectrum_plot.plot(
                pen=pg.mkPen(color='#FF9800', width=2),
                fillLevel=0,
                brush=pg.mkBrush(255, 152, 0, 100)
            )

            spectrum_layout.addWidget(self.spectrum_plot)
            spectrum_group.setLayout(spectrum_layout)
            layout.addWidget(spectrum_group, stretch=2)

        else:
            no_plot_label = QLabel("⚠️ 音频波形显示不可用\n\n请安装: pip install pyqtgraph")
            no_plot_label.setAlignment(Qt.AlignCenter)
            no_plot_label.setStyleSheet("""
                QLabel {
                    color: #999;
                    font-size: 16px;
                    padding: 50px;
                    background-color: #f5f5f5;
                    border-radius: 10px;
                }
            """)
            layout.addWidget(no_plot_label)

        dark = _is_dark()
        _tc = '#d4d4d4' if dark else '#333'

        def _info_style(bg_light, fg=_tc):
            if dark:
                r, g, b = int(bg_light[1:3],16), int(bg_light[3:5],16), int(bg_light[5:7],16)
                bg = f'rgba({r},{g},{b},50)'
            else:
                bg = bg_light
            return f"QLabel{{font-size:14px;padding:10px 15px;background-color:{bg};border-radius:5px;color:{fg};font-weight:bold;}}"

        _hdr_bg = tint('#888888', 35) if dark else '#f5f5f5'
        _hdr_style = f"QLabel{{font-size:13px;padding:10px 12px;background-color:{_hdr_bg};border-radius:5px;color:{_tc};font-weight:bold;}}"

        def _hdr(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(_hdr_style)
            return lbl

        info_group = QGroupBox("📊 音频信息")
        info_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")
        info_layout = QGridLayout()

        self.audio_status_label = QLabel("状态: 未连接")
        self.audio_status_label.setStyleSheet(_info_style('#ffcccc', '#cc0000'))
        info_layout.addWidget(_hdr("连接状态:"), 0, 0)
        info_layout.addWidget(self.audio_status_label, 0, 1)

        self.audio_level_label = QLabel("-- dB")
        self.audio_level_label.setStyleSheet(_info_style('#e3f2fd', '#1976d2') + "QLabel{font-size:16px;font-family:monospace;}")
        info_layout.addWidget(_hdr("实时音量:"), 0, 2)
        info_layout.addWidget(self.audio_level_label, 0, 3)

        self.audio_rms_label = QLabel("--")
        self.audio_rms_label.setStyleSheet(_info_style('#f0f4ff'))
        info_layout.addWidget(_hdr("RMS:"), 1, 0)
        info_layout.addWidget(self.audio_rms_label, 1, 1)

        self.audio_peak_label = QLabel("--")
        self.audio_peak_label.setStyleSheet(_info_style('#f0f4ff'))
        info_layout.addWidget(_hdr("峰值:"), 1, 2)
        info_layout.addWidget(self.audio_peak_label, 1, 3)

        self.audio_samples_label = QLabel("0 样本")
        self.audio_samples_label.setStyleSheet(_info_style('#fff4f0'))
        info_layout.addWidget(_hdr("已采样:"), 2, 0)
        info_layout.addWidget(self.audio_samples_label, 2, 1)

        self.audio_rate_label = QLabel("44100 Hz")
        self.audio_rate_label.setStyleSheet(_info_style('#fff4f0'))
        info_layout.addWidget(_hdr("采样率:"), 2, 2)
        info_layout.addWidget(self.audio_rate_label, 2, 3)

        self.audio_channels_label = QLabel("单声道")
        self.audio_channels_label.setStyleSheet(_info_style('#f0fff4'))
        info_layout.addWidget(_hdr("声道:"), 3, 0)
        info_layout.addWidget(self.audio_channels_label, 3, 1)

        self.audio_duration_label = QLabel("00:00")
        self.audio_duration_label.setStyleSheet(_info_style('#f0fff4') + "QLabel{font-family:monospace;}")
        info_layout.addWidget(_hdr("录制时长:"), 3, 2)
        info_layout.addWidget(self.audio_duration_label, 3, 3)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group, stretch=1)

        self.setLayout(layout)

    def update_display(self):
        """更新显示"""
        if not hasattr(self.collection_tab, 'device_controller') or not self.collection_tab.device_controller:
            return

        device_controller = self.collection_tab.device_controller

        # 更新音频
        if PYQTGRAPH_AVAILABLE:
            self.update_audio(device_controller)

    @staticmethod
    def _status_style(bg_hex, fg_hex):
        from app.monitors import _is_dark, tint
        bg = tint(bg_hex, 50) if _is_dark() else bg_hex
        return f"QLabel{{font-size:14px;padding:10px 15px;background-color:{bg};border-radius:5px;color:{fg_hex};font-weight:bold;}}"

    def update_audio(self, device_controller):
        """更新音频显示"""
        try:
            if not hasattr(device_controller, 'audio_connected') or not device_controller.audio_connected:
                self.audio_status_label.setText("状态: 未连接")
                self.audio_status_label.setStyleSheet(self._status_style('#ffcccc', '#cc0000'))
                return

            if hasattr(device_controller, 'is_recording') and device_controller.is_recording:
                self.audio_status_label.setText("状态: 🔴 录制中")
                self.audio_status_label.setStyleSheet(self._status_style('#ffcccc', '#cc0000'))
            else:
                self.audio_status_label.setText("状态: ⚪ 已连接")
                self.audio_status_label.setStyleSheet(self._status_style('#c8e6c9', '#2e7d32'))

            # 获取音频数据
            audio_data = device_controller.get_latest_audio_data(self.audio_buffer_size)
            if audio_data is not None and len(audio_data) > 0:
                # 时间轴
                sample_rate = 44100
                time_axis = np.arange(len(audio_data)) / sample_rate

                # 更新波形
                self.audio_curve.setData(time_axis, audio_data)

                # 计算并更新频谱
                if len(audio_data) >= 512:
                    # FFT
                    fft_data = np.fft.rfft(audio_data)
                    fft_freq = np.fft.rfftfreq(len(audio_data), 1.0 / sample_rate)
                    fft_magnitude = np.abs(fft_data) / len(audio_data)

                    # 转换为dB
                    fft_magnitude_db = 20 * np.log10(fft_magnitude + 1e-10)

                    # 只显示到2kHz
                    max_freq_idx = np.searchsorted(fft_freq, 2000)
                    self.spectrum_curve.setData(fft_freq[:max_freq_idx], fft_magnitude_db[:max_freq_idx])

                # 更新音频统计信息
                rms = np.sqrt(np.mean(audio_data ** 2))
                peak = np.max(np.abs(audio_data))
                db = 20 * np.log10(rms + 1e-10)

                self.audio_level_label.setText(f"{db:.1f} dB")
                self.audio_rms_label.setText(f"{rms:.4f}")
                self.audio_peak_label.setText(f"{peak:.4f}")
                self.audio_samples_label.setText(f"{device_controller.audio_sample_count} 样本")

                # 更新时长
                if hasattr(device_controller, 'start_time') and device_controller.start_time:
                    from datetime import datetime
                    elapsed = (datetime.now() - device_controller.start_time).total_seconds()
                    minutes = int(elapsed // 60)
                    seconds = int(elapsed % 60)
                    self.audio_duration_label.setText(f"{minutes:02d}:{seconds:02d}")

        except Exception as e:
            pass  # 静默处理错误