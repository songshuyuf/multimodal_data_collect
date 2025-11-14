"""
实时外周生理信号显示Tab
显示Shimmer GSR+的实时数据
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFrame
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import numpy as np

try:
    import pyqtgraph as pg

    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False


class RealtimeShimmerTab(QWidget):
    """实时外周生理信号显示Tab"""

    def __init__(self, collection_tab):
        """
        初始化

        Args:
            collection_tab: 数据采集Tab的引用，用于获取实时数据
        """
        super().__init__()
        self.collection_tab = collection_tab

        self.init_ui()

        # 定时更新
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(100)  # 100ms更新一次

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 标题
        title_label = QLabel("📊 外周生理信号 - Shimmer GSR+ 实时监测")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #4CAF50;
                padding: 10px;
                background-color: #f0f8f0;
                border-radius: 5px;
            }
        """)
        layout.addWidget(title_label)

        if PYQTGRAPH_AVAILABLE:
            # 创建波形显示区域
            self.plot_widget = pg.GraphicsLayoutWidget()
            self.plot_widget.setBackground('w')

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

        # 心率统计
        hr_frame = self.create_stat_frame("心率", "#f44336")
        hr_layout = QVBoxLayout()
        self.hr_current_label = QLabel("当前: -- BPM")
        self.hr_avg_label = QLabel("平均: -- BPM")
        self.hr_range_label = QLabel("范围: --")
        hr_layout.addWidget(self.hr_current_label)
        hr_layout.addWidget(self.hr_avg_label)
        hr_layout.addWidget(self.hr_range_label)
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
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {color}22;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
            QLabel {{
                color: #333;
                font-size: 12px;
                padding: 3px;
            }}
        """)
        return frame

    def update_display(self):
        """更新显示"""
        if not PYQTGRAPH_AVAILABLE:
            print("DEBUG: pyqtgraph 不可用")
            return

        # 检查是否正在采集
        if not hasattr(self.collection_tab, 'is_collecting') or not self.collection_tab.is_collecting:
            print("DEBUG: 未在采集")
            self.device_status_label.setText("状态: 未采集")
            return

        # 获取recorder
        try:
            print("DEBUG: 开始获取 recorder")
            recorder = self.collection_tab.device_controller.recorder

            if not recorder:
                print("DEBUG: recorder 为 None")
                self.device_status_label.setText("状态: 录制器未启动")
                return

            # 使用共享数据
            data = recorder.realtime_data
            print(f"DEBUG: GSR数据点数: {len(data['gsr'])}")
            print(f"DEBUG: PPG数据点数: {len(data['ppg'])}")
            print(f"DEBUG: 心率: {data['hr']}")

            # 更新GSR波形
            if len(data['gsr']) > 0:
                gsr_array = np.array(data['gsr'])
                time_array = np.arange(len(gsr_array)) / 128.0
                self.gsr_curve.setData(time_array, gsr_array)

                # 统计
                self.gsr_current_label.setText(f"当前值: {gsr_array[-1]:.2f} µS")
                self.gsr_avg_label.setText(f"平均值: {np.mean(gsr_array):.2f} µS")
                self.gsr_range_label.setText(f"范围: {np.min(gsr_array):.2f} - {np.max(gsr_array):.2f} µS")

            # 更新PPG波形
            if len(data['ppg']) > 0:
                ppg_array = np.array(data['ppg'])
                time_array = np.arange(len(ppg_array)) / 128.0
                self.ppg_curve.setData(time_array, ppg_array)

                self.ppg_current_label.setText(f"当前: {ppg_array[-1]:.0f}")
                self.ppg_samples_label.setText(f"已采样: {len(ppg_array)}")

                # 信号质量
                if len(ppg_array) > 100:
                    std = np.std(ppg_array[-100:])
                    quality = "良好" if std > 50 else "中等" if std > 20 else "较差"
                    self.ppg_quality_label.setText(f"信号质量: {quality}")

            # 更新心率
            if data['hr'] > 0:
                self.hr_current_label.setText(f"当前: {data['hr']:.0f} BPM")

            # 更新加速度计
            if len(data['accel_x']) > 0:
                accel_x = np.array(data['accel_x'])
                accel_y = np.array(data['accel_y'])
                accel_z = np.array(data['accel_z'])
                time_array = np.arange(len(accel_x)) / 128.0

                self.accel_x_curve.setData(time_array, accel_x)
                self.accel_y_curve.setData(time_array, accel_y)
                self.accel_z_curve.setData(time_array, accel_z)

            # 更新状态
            self.device_status_label.setText("状态: 采集中 ✓")
            self.device_connection_label.setText("连接: 正常")
            self.device_battery_label.setText("电量: 充足")

        except Exception as e:
            print(f"DEBUG: 发生异常: {e}")
            import traceback
            traceback.print_exc()
            self.device_status_label.setText(f"状态: 错误")