"""
实时EEG信号显示Tab
支持Neuracle HEEG 64通道脑电信号实时显示
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QPushButton, QFrame
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

import matplotlib

matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np


class RealtimeEEGTab(QWidget):
    """实时EEG信号显示Tab"""

    def __init__(self, device_controller=None):
        """
        初始化EEG显示Tab

        Args:
            device_controller: 设备控制器实例（可选）
        """
        super().__init__()
        self.device_controller = device_controller

        # 显示参数
        self.display_channels = 8  # 显示的通道数
        self.buffer_size = 1000  # 显示的样本点数

        # 初始化UI
        self.init_ui()

        # 启动更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(100)  # 100ms更新一次

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 标题和状态栏
        header_layout = self.create_header()
        layout.addLayout(header_layout)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # EEG波形图
        self.canvas = self.create_plot()
        layout.addWidget(self.canvas)

        self.setLayout(layout)

    def create_header(self) -> QHBoxLayout:
        """创建顶部标题和状态栏"""
        layout = QHBoxLayout()

        # 标题
        from app.monitors import _is_dark, tint
        title_label = QLabel("🧠 HEEG 脑电信号")
        _tbg = tint('#9C27B0', 25) if _is_dark() else 'transparent'
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: bold;
                color: #9C27B0;
                padding: 10px;
                background-color: {_tbg};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(title_label)

        layout.addStretch()

        # 设备状态
        status_group = QGroupBox("设备状态")
        status_layout = QHBoxLayout()

        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(QLabel("HEEG:"))
        status_layout.addWidget(self.status_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 统计信息
        stats_group = QGroupBox("统计信息")
        stats_layout = QHBoxLayout()

        stats_layout.addWidget(QLabel("数据包:"))
        self.packet_label = QLabel("0")
        stats_layout.addWidget(self.packet_label)

        stats_layout.addWidget(QLabel("样本:"))
        self.sample_label = QLabel("0")
        stats_layout.addWidget(self.sample_label)

        stats_layout.addWidget(QLabel("Trigger:"))
        self.trigger_label = QLabel("-")
        stats_layout.addWidget(self.trigger_label)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        return layout

    def create_plot(self) -> FigureCanvas:
        """创建EEG波形图"""
        from app.monitors import theme_mpl_figure
        self.figure = Figure(figsize=(10, 6), dpi=100)

        # 创建子图（每个通道一个子图）
        self.axes = []
        for i in range(self.display_channels):
            ax = self.figure.add_subplot(self.display_channels, 1, i + 1)
            ax.set_ylabel(f'Ch{i + 1}\n(μV)', fontsize=8, rotation=0,
                          ha='right', va='center')
            ax.set_ylim(-200, 200)  # 默认范围
            ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
            ax.set_xlim(0, self.buffer_size)

            # 只在最后一个子图显示x轴标签
            if i == self.display_channels - 1:
                ax.set_xlabel('样本点')
            else:
                ax.set_xticklabels([])

            # 设置刻度字体大小
            ax.tick_params(labelsize=8)

            self.axes.append(ax)

        self.figure.tight_layout()

        self.lines = []
        from app.monitors import _is_dark
        line_color = '#00ff88' if _is_dark() else 'g'
        for ax in self.axes:
            line, = ax.plot([], [], color=line_color, linewidth=0.8)
            self.lines.append(line)

        theme_mpl_figure(self.figure)

        canvas = FigureCanvas(self.figure)
        return canvas

    def update_display(self):
        """更新显示（定时器调用）"""
        try:
            # 检查是否有device_controller
            if not self.device_controller:
                return

            # 检查HEEG设备是否就绪
            if not hasattr(self.device_controller, 'heeg_ready'):
                return

            # 更新状态标签
            if self.device_controller.heeg_ready:
                self.status_label.setText("已连接")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.status_label.setText("未连接")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
                return

            # 获取HEEG统计信息
            if hasattr(self.device_controller, 'heeg_packet_count'):
                self.packet_label.setText(str(self.device_controller.heeg_packet_count))

            if hasattr(self.device_controller, 'heeg_sample_count'):
                self.sample_label.setText(str(self.device_controller.heeg_sample_count))

            # 获取实时数据
            if not hasattr(self.device_controller, 'get_realtime_heeg_data'):
                return

            data = self.device_controller.get_realtime_heeg_data()

            if not data:
                return

            # 更新trigger显示
            trigger = data.get('trigger', None)
            if trigger:
                self.trigger_label.setText(str(trigger))
                self.trigger_label.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.trigger_label.setText("-")
                self.trigger_label.setStyleSheet("color: black;")

            # 更新波形图
            for i in range(self.display_channels):
                channel_key = f'channel_{i + 1}'
                if channel_key in data and len(data[channel_key]) > 0:
                    channel_data = list(data[channel_key])
                    x_data = list(range(len(channel_data)))

                    # 更新线条数据
                    self.lines[i].set_data(x_data, channel_data)

                    # 自动调整x轴范围
                    self.axes[i].set_xlim(0, max(len(channel_data), 100))

                    # 动态调整y轴范围
                    if len(channel_data) > 0:
                        data_min = min(channel_data)
                        data_max = max(channel_data)
                        margin = (data_max - data_min) * 0.1 if data_max != data_min else 10
                        self.axes[i].set_ylim(
                            data_min - margin,
                            data_max + margin
                        )

            # 刷新画布
            self.canvas.draw_idle()

        except Exception as e:
            # 静默失败，避免影响GUI主线程
            pass

    def clear_display(self):
        """清空显示"""
        for line in self.lines:
            line.set_data([], [])
        self.canvas.draw()

    def set_device_controller(self, controller):
        """设置设备控制器"""
        self.device_controller = controller


# ==================== 测试代码 ====================
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    from collections import deque
    import time


    # 模拟设备控制器
    class MockDeviceController:
        def __init__(self):
            self.heeg_ready = True
            self.heeg_packet_count = 0
            self.heeg_sample_count = 0

            self.realtime_heeg_data = {
                f'channel_{i + 1}': deque(maxlen=1000)
                for i in range(8)
            }
            self.realtime_heeg_data['trigger'] = None

        def get_realtime_heeg_data(self):
            # 模拟数据更新
            self.heeg_packet_count += 1
            self.heeg_sample_count += 10

            # 模拟EEG波形（不同频率的正弦波）
            t = time.time()
            for i in range(8):
                freq = 1 + i * 0.5
                for j in range(10):
                    value = 100 * np.sin(2 * np.pi * freq * (t + j * 0.001))
                    self.realtime_heeg_data[f'channel_{i + 1}'].append(value)

            return {k: list(v) if hasattr(v, '__iter__') else v
                    for k, v in self.realtime_heeg_data.items()}


    # 创建应用
    app = QApplication(sys.argv)

    # 创建模拟控制器
    mock_controller = MockDeviceController()

    # 创建Tab
    tab = RealtimeEEGTab(device_controller=mock_controller)
    tab.setWindowTitle("HEEG实时显示测试")
    tab.resize(900, 700)
    tab.show()

    sys.exit(app.exec_())