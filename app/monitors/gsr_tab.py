"""
实时外周生理信号显示Tab - 完整版
显示Shimmer GSR+的实时数据（从device_controller获取）
包含心率和HRV实时计算
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFrame
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import numpy as np
from collections import deque
from scipy import signal

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False


class HeartRateAnalyzer:
    """心率和HRV分析器（从PPG信号）"""

    def __init__(self, sampling_rate=128):
        self.sampling_rate = sampling_rate
        self.ppg_buffer = deque(maxlen=sampling_rate * 30)  # 保存30秒数据
        self.rr_intervals = deque(maxlen=100)  # 保存最近100个R-R间期
        self.last_peak_time = None

    def add_sample(self, ppg_value):
        """添加PPG样本"""
        self.ppg_buffer.append(ppg_value)

    def detect_peaks(self, ppg_data, min_distance=60):
        """
        检测PPG波峰

        Args:
            ppg_data: PPG数据数组
            min_distance: 最小波峰间隔（样本数），默认60 = 0.47秒 @ 128Hz

        Returns:
            peaks: 波峰位置索引数组
        """
        if len(ppg_data) < 100:
            return np.array([])

        # 1. 去趋势（去除基线漂移）
        ppg_detrended = signal.detrend(ppg_data)

        # 2. 带通滤波（0.5-8Hz，保留心跳频率）
        sos = signal.butter(4, [0.5, 8], btype='band', fs=self.sampling_rate, output='sos')
        ppg_filtered = signal.sosfilt(sos, ppg_detrended)

        # 3. 找波峰
        # height: 波峰高度至少是信号标准差的0.5倍
        # distance: 相邻波峰至少间隔min_distance个样本
        threshold = np.std(ppg_filtered) * 0.5
        peaks, _ = signal.find_peaks(
            ppg_filtered,
            height=threshold,
            distance=min_distance
        )

        return peaks

    def calculate_hr_hrv(self):
        """
        计算心率和HRV指标

        Returns:
            dict: {
                'hr': 心率（BPM）,
                'sdnn': SDNN（ms）,
                'rmssd': RMSSD（ms）,
                'pnn50': pNN50（%）,
                'hr_valid': 是否有效
            }
        """
        result = {
            'hr': 0.0,
            'sdnn': 0.0,
            'rmssd': 0.0,
            'pnn50': 0.0,
            'hr_valid': False
        }

        # 需要至少10秒数据
        if len(self.ppg_buffer) < self.sampling_rate * 10:
            return result

        # 转换为numpy数组
        ppg_data = np.array(self.ppg_buffer)

        # 检测波峰
        peaks = self.detect_peaks(ppg_data)

        if len(peaks) < 5:  # 至少需要5个波峰
            return result

        # 计算R-R间期（以毫秒为单位）
        rr_intervals_samples = np.diff(peaks)  # 样本数
        rr_intervals_ms = (rr_intervals_samples / self.sampling_rate) * 1000  # 转换为毫秒

        # 过滤异常值（0.3秒 < RR间期 < 2秒，即30-200 BPM）
        valid_rr = rr_intervals_ms[(rr_intervals_ms > 300) & (rr_intervals_ms < 2000)]

        if len(valid_rr) < 3:
            return result

        # 更新R-R间期缓冲区
        for rr in valid_rr:
            self.rr_intervals.append(rr)

        # 计算心率（使用最近的平均R-R间期）
        mean_rr_ms = np.mean(valid_rr)
        hr = 60000 / mean_rr_ms  # BPM

        # 计算HRV指标
        if len(self.rr_intervals) >= 5:
            rr_array = np.array(self.rr_intervals)

            # SDNN: R-R间期的标准差
            sdnn = np.std(rr_array)

            # RMSSD: 相邻R-R间期差值的均方根
            rr_diff = np.diff(rr_array)
            rmssd = np.sqrt(np.mean(rr_diff ** 2))

            # pNN50: 相邻间期差>50ms的百分比
            nn50 = np.sum(np.abs(rr_diff) > 50)
            pnn50 = (nn50 / len(rr_diff)) * 100 if len(rr_diff) > 0 else 0

            result = {
                'hr': hr,
                'sdnn': sdnn,
                'rmssd': rmssd,
                'pnn50': pnn50,
                'hr_valid': True
            }
        else:
            result['hr'] = hr
            result['hr_valid'] = True

        return result


class RealtimeShimmerTab(QWidget):
    """实时外周生理信号显示Tab"""

    def __init__(self, collection_tab):
        """
        初始化

        Args:
            collection_tab: 数据采集Tab的引用
        """
        super().__init__()
        self.collection_tab = collection_tab

        # 数据缓冲区（保存最近5秒数据）
        self.buffer_size = 640  # 128Hz * 5秒
        self.gsr_buffer = deque(maxlen=self.buffer_size)
        self.ppg_buffer = deque(maxlen=self.buffer_size)
        self.accel_x_buffer = deque(maxlen=self.buffer_size)
        self.accel_y_buffer = deque(maxlen=self.buffer_size)
        self.accel_z_buffer = deque(maxlen=self.buffer_size)

        # 心率分析器
        self.hr_analyzer = HeartRateAnalyzer(sampling_rate=128)

        # 最新值
        self.latest_gsr = 0.0
        self.latest_ppg = 0.0
        self.latest_hr = 0.0
        self.latest_battery = 0.0

        # 计算的心率和HRV
        self.calculated_hr = 0.0
        self.sdnn = 0.0
        self.rmssd = 0.0
        self.pnn50 = 0.0
        # 更新计数器
        self.hr_update_counter = 0

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
        title_label = QLabel("📊 外周生理信号 - Shimmer GSR+ 实时监测")
        _tbg = tint('#4CAF50', 25) if _is_dark() else '#f0f8f0'
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: bold;
                color: #4CAF50;
                padding: 10px;
                background-color: {_tbg};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(title_label)

        if PYQTGRAPH_AVAILABLE:
            from app.monitors import theme_pg_layout
            self.plot_widget = pg.GraphicsLayoutWidget()
            theme_pg_layout(self.plot_widget)

            # GSR波形
            self.gsr_plot = self.plot_widget.addPlot(row=0, col=0, title="<b style='font-size:14pt'>GSR - 皮肤电导</b>")
            self.gsr_plot.setLabel('left', 'GSR', units='µS', **{'font-size': '12pt'})
            self.gsr_plot.setLabel('bottom', '时间', units='s', **{'font-size': '12pt'})
            self.gsr_plot.showGrid(x=True, y=True, alpha=0.3)
            self.gsr_curve = self.gsr_plot.plot(pen=pg.mkPen(color='g', width=3))

            # PPG波形
            self.ppg_plot = self.plot_widget.addPlot(row=1, col=0,
                                                     title="<b style='font-size:14pt'>PPG - 光电容积描记</b>")
            self.ppg_plot.setLabel('left', 'PPG', units='', **{'font-size': '12pt'})
            self.ppg_plot.setLabel('bottom', '时间', units='s', **{'font-size': '12pt'})
            self.ppg_plot.showGrid(x=True, y=True, alpha=0.3)
            self.ppg_curve = self.ppg_plot.plot(pen=pg.mkPen(color='r', width=3))

            # 加速度计波形
            self.accel_plot = self.plot_widget.addPlot(row=2, col=0,
                                                       title="<b style='font-size:14pt'>加速度计 - X/Y/Z轴</b>")
            self.accel_plot.setLabel('left', '加速度', units='g', **{'font-size': '12pt'})
            self.accel_plot.setLabel('bottom', '时间', units='s', **{'font-size': '12pt'})
            self.accel_plot.showGrid(x=True, y=True, alpha=0.3)
            self.accel_x_curve = self.accel_plot.plot(pen=pg.mkPen(color='b', width=2), name='X')
            self.accel_y_curve = self.accel_plot.plot(pen=pg.mkPen(color='g', width=2), name='Y')
            self.accel_z_curve = self.accel_plot.plot(pen=pg.mkPen(color='r', width=2), name='Z')
            self.accel_plot.addLegend()

            layout.addWidget(self.plot_widget, stretch=1)
        else:
            no_plot_label = QLabel("⚠️ 实时波形显示不可用\n\n请安装 pyqtgraph:\npip install pyqtgraph")
            no_plot_label.setAlignment(Qt.AlignCenter)
            no_plot_label.setStyleSheet("color: #999; font-size: 16px; padding: 50px;")
            layout.addWidget(no_plot_label, stretch=1)

        # 统计信息面板
        stats_group = self.create_stats_panel()
        layout.addWidget(stats_group)

        self.setLayout(layout)

    def create_stats_panel(self) -> QGroupBox:
        """创建统计信息面板"""
        group = QGroupBox("📈 实时统计数据")
        group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 14px; }")

        layout = QHBoxLayout()

        # GSR统计
        gsr_frame = self.create_stat_frame("GSR 皮肤电导", "#4CAF50")
        gsr_layout = QVBoxLayout()
        self.gsr_current_label = QLabel("当前值: -- µS")
        self.gsr_avg_label = QLabel("平均值: -- µS")
        self.gsr_range_label = QLabel("范围: --")
        gsr_layout.addWidget(self.gsr_current_label)
        gsr_layout.addWidget(self.gsr_avg_label)
        gsr_layout.addWidget(self.gsr_range_label)
        gsr_frame.setLayout(gsr_layout)
        layout.addWidget(gsr_frame)

        # 心率和HRV统计
        hr_frame = self.create_stat_frame("心率 & HRV", "#f44336")
        hr_layout = QVBoxLayout()
        self.hr_current_label = QLabel("心率: -- BPM")
        self.sdnn_label = QLabel("SDNN: -- ms")
        self.rmssd_label = QLabel("RMSSD: -- ms")
        hr_layout.addWidget(self.hr_current_label)
        hr_layout.addWidget(self.sdnn_label)
        hr_layout.addWidget(self.rmssd_label)
        hr_frame.setLayout(hr_layout)
        layout.addWidget(hr_frame)

        # PPG统计
        ppg_frame = self.create_stat_frame("PPG", "#2196F3")
        ppg_layout = QVBoxLayout()
        self.ppg_current_label = QLabel("当前: --")
        self.ppg_quality_label = QLabel("信号质量: --")
        self.ppg_samples_label = QLabel("已采样: 0")
        ppg_layout.addWidget(self.ppg_current_label)
        ppg_layout.addWidget(self.ppg_quality_label)
        ppg_layout.addWidget(self.ppg_samples_label)
        ppg_frame.setLayout(ppg_layout)
        layout.addWidget(ppg_frame)

        # 设备状态
        device_frame = self.create_stat_frame("设备状态", "#9C27B0")
        device_layout = QVBoxLayout()
        self.device_status_label = QLabel("状态: 未连接")
        self.device_battery_label = QLabel("电量: --")
        self.device_connection_label = QLabel("连接: --")
        device_layout.addWidget(self.device_status_label)
        device_layout.addWidget(self.device_battery_label)
        device_layout.addWidget(self.device_connection_label)
        device_frame.setLayout(device_layout)
        layout.addWidget(device_frame)

        group.setLayout(layout)
        return group

    def create_stat_frame(self, title: str, color: str) -> QFrame:
        """创建统计信息框架"""
        from app.monitors import _is_dark, tint
        text_color = '#d4d4d4' if _is_dark() else '#333'
        bg = tint(color, 30)
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{
                color: {text_color};
                font-size: 12px;
                padding: 3px;
            }}
        """)
        return frame

    def update_display(self):
        """更新显示 - 从device_controller的轮询线程获取数据"""
        if not PYQTGRAPH_AVAILABLE:
            return

        # 获取device_controller
        if not hasattr(self.collection_tab, 'device_controller'):
            return

        device_controller = self.collection_tab.device_controller

        # 检查device_controller是否为None
        if device_controller is None:
            return

        # 调试输出
      #  print(f"[Shimmer Tab] 连接状态: {device_controller.shimmer_connected}, 录制状态: {device_controller.is_recording}")

        # 检查Shimmer是否连接
        if not device_controller.shimmer_connected:
          #  self.device_status_label.setText("状态: 未连接")
            return

        # 检查是否正在录制
        if not device_controller.is_recording:
         #   self.device_status_label.setText("状态: 已连接（未录制）")
            return

        # 从shimmer_device获取最新数据
        try:
            if not hasattr(device_controller, 'shimmer_device') or device_controller.shimmer_device is None:
                return

            # 从data_buffer获取数据
            shimmer_device = device_controller.shimmer_device

            if hasattr(shimmer_device, 'data_buffer') and shimmer_device.data_buffer:
                # 处理缓冲区中的新数据
                while shimmer_device.data_buffer:
                    packet = shimmer_device.data_buffer.pop(0)

                    # 解析数据
                    try:
                        sample, timestamp = shimmer_device.extract_sample_from_packet(packet)
                        if sample is not None:
                            channel_names = shimmer_device.get_channel_names()

                            # 提取各通道数据
                            for i, channel_name in enumerate(channel_names):
                                if i < len(sample):
                                    value = sample[i]

                                    if 'GSR_Skin_Conductance' in channel_name:
                                        self.gsr_buffer.append(value)
                                        self.latest_gsr = value
                                    elif 'PPG' in channel_name and 'PPGtoHR' not in channel_name:
                                        self.ppg_buffer.append(value)
                                        self.latest_ppg = value
                                        # 添加到心率分析器
                                        self.hr_analyzer.add_sample(value)
                                    elif 'Accel_LN_X' in channel_name:
                                        self.accel_x_buffer.append(value)
                                    elif 'Accel_LN_Y' in channel_name:
                                        self.accel_y_buffer.append(value)
                                    elif 'Accel_LN_Z' in channel_name:
                                        self.accel_z_buffer.append(value)
                                    elif 'PPGtoHR' in channel_name:
                                        self.latest_hr = value
                                    elif 'VSenseBatt' in channel_name:
                                        self.latest_battery = value
                    except:
                        pass

            # 更新波形
            if len(self.gsr_buffer) > 0:
                gsr_array = np.array(self.gsr_buffer)
                time_array = np.arange(len(gsr_array)) / 128.0
                self.gsr_curve.setData(time_array, gsr_array)

                # 更新统计
                self.gsr_current_label.setText(f"当前值: {self.latest_gsr:.4f} µS")
                self.gsr_avg_label.setText(f"平均值: {np.mean(gsr_array):.4f} µS")
                self.gsr_range_label.setText(f"范围: {np.min(gsr_array):.4f} - {np.max(gsr_array):.4f} µS")

            if len(self.ppg_buffer) > 0:
                ppg_array = np.array(self.ppg_buffer)
                time_array = np.arange(len(ppg_array)) / 128.0
                self.ppg_curve.setData(time_array, ppg_array)

                self.ppg_current_label.setText(f"当前: {self.latest_ppg:.2f}")
                self.ppg_samples_label.setText(f"已采样: {len(self.ppg_buffer)}")

                # 信号质量
                if len(ppg_array) > 100:
                    std = np.std(ppg_array[-100:])
                    quality = "良好" if std > 50 else "中等" if std > 20 else "较差"
                    self.ppg_quality_label.setText(f"信号质量: {quality}")

            # 计算心率和HRV（每秒计算一次）
            self.hr_update_counter += 1

            if self.hr_update_counter % 20 == 0:  # 50ms * 20 = 1秒
                hr_hrv = self.hr_analyzer.calculate_hr_hrv()

                if hr_hrv['hr_valid']:
                    self.calculated_hr = hr_hrv['hr']
                    self.sdnn = hr_hrv['sdnn']
                    self.rmssd = hr_hrv['rmssd']
                    self.pnn50 = hr_hrv['pnn50']

                    # 更新心率显示
                    self.hr_current_label.setText(f"心率: {self.calculated_hr:.1f} BPM")
                    self.sdnn_label.setText(f"SDNN: {self.sdnn:.1f} ms")
                    self.rmssd_label.setText(f"RMSSD: {self.rmssd:.1f} ms")
                else:
                    # 没有有效数据时显示等待状态
                    self.hr_current_label.setText(f"心率: 等待信号...")
                    self.sdnn_label.setText(f"SDNN: --")
                    self.rmssd_label.setText(f"RMSSD: --")

            # 更新加速度计
            if len(self.accel_x_buffer) > 0:
                accel_x = np.array(self.accel_x_buffer)
                accel_y = np.array(self.accel_y_buffer)
                accel_z = np.array(self.accel_z_buffer)
                time_array = np.arange(len(accel_x)) / 128.0

                self.accel_x_curve.setData(time_array, accel_x)
                self.accel_y_curve.setData(time_array, accel_y)
                self.accel_z_curve.setData(time_array, accel_z)

            # 更新设备状态
            self.device_status_label.setText("状态: 采集中 ✓")
            self.device_connection_label.setText("连接: 正常")

            # 电池电压转换为百分比（粗略估计）
            if self.latest_battery > 0:
                battery_percent = min(100, max(0, (self.latest_battery - 3.0) / 1.2 * 100))
                self.device_battery_label.setText(f"电量: {battery_percent:.0f}% ({self.latest_battery:.2f}V)")

        except Exception as e:
            pass  # 静默处理错误