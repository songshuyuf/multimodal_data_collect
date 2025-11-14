"""
实时数据可视化
显示Shimmer GSR+的实时数据波形
"""

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore
from PyQt5 import QtWidgets
from collections import deque
import time


class RealtimeVisualizer:
    """实时数据可视化器"""

    def __init__(self, window_size=500):
        """
        初始化可视化器

        Args:
            window_size: 显示的数据点数量
        """
        self.window_size = window_size

        # 数据缓冲区
        self.gsr_buffer = deque(maxlen=window_size)
        self.ppg_buffer = deque(maxlen=window_size)
        self.hr_buffer = deque(maxlen=100)
        self.accel_x_buffer = deque(maxlen=window_size)
        self.accel_y_buffer = deque(maxlen=window_size)
        self.accel_z_buffer = deque(maxlen=window_size)

        # 时间轴
        self.time_buffer = deque(maxlen=window_size)
        self.start_time = time.time()

        # 当前值
        self.current_hr = 0.0
        self.current_gsr = 0.0

        # 创建GUI
        # 创建GUI
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication([])
        self.win = pg.GraphicsLayoutWidget(title="Shimmer GSR+ 实时监控")
        self.win.resize(1200, 800)
        self.win.setWindowTitle('多模态生理信号实时监控')

        self._setup_plots()

        # 更新定时器
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plots)
        self.timer.start(50)  # 20 Hz更新

    def _setup_plots(self):
        """设置绘图区域"""
        # 标题
        title = pg.LabelItem(text='<span style="font-size: 16pt; font-weight: bold;">实时生理信号监控</span>')
        self.win.addItem(title, row=0, col=0, colspan=2)

        # 第一行: GSR
        self.win.nextRow()
        self.plot_gsr = self.win.addPlot(title="GSR - 皮肤电导 (μS)")
        self.plot_gsr.setLabel('left', '电导', units='μS')
        self.plot_gsr.setLabel('bottom', '时间', units='s')
        self.plot_gsr.showGrid(x=True, y=True, alpha=0.3)
        self.curve_gsr = self.plot_gsr.plot(pen=pg.mkPen(color='g', width=2))

        # 心率显示
        self.hr_label = pg.LabelItem(text='<span style="font-size: 24pt; color: red;">心率: -- BPM</span>')
        self.win.addItem(self.hr_label, row=1, col=1)

        # 第二行: PPG
        self.win.nextRow()
        self.plot_ppg = self.win.addPlot(title="PPG - 光电脉搏")
        self.plot_ppg.setLabel('left', 'PPG信号', units='ADC')
        self.plot_ppg.setLabel('bottom', '时间', units='s')
        self.plot_ppg.showGrid(x=True, y=True, alpha=0.3)
        self.curve_ppg = self.plot_ppg.plot(pen=pg.mkPen(color='r', width=2))

        # 心率趋势图
        self.plot_hr = self.win.addPlot(title="心率趋势")
        self.plot_hr.setLabel('left', '心率', units='BPM')
        self.plot_hr.setLabel('bottom', '时间', units='s')
        self.plot_hr.showGrid(x=True, y=True, alpha=0.3)
        self.plot_hr.setYRange(40, 120)
        self.curve_hr = self.plot_hr.plot(pen=pg.mkPen(color='y', width=2))

        # 第三行: 加速度计
        self.win.nextRow()
        self.plot_accel = self.win.addPlot(title="加速度计 - 3轴", colspan=2)
        self.plot_accel.setLabel('left', '加速度', units='m/s²')
        self.plot_accel.setLabel('bottom', '时间', units='s')
        self.plot_accel.showGrid(x=True, y=True, alpha=0.3)
        self.plot_accel.addLegend()
        self.curve_accel_x = self.plot_accel.plot(pen=pg.mkPen(color='r', width=2), name='X轴')
        self.curve_accel_y = self.plot_accel.plot(pen=pg.mkPen(color='g', width=2), name='Y轴')
        self.curve_accel_z = self.plot_accel.plot(pen=pg.mkPen(color='b', width=2), name='Z轴')

        # 状态栏
        self.win.nextRow()
        self.status_label = pg.LabelItem(text='<span style="font-size: 12pt;">状态: 等待数据...</span>')
        self.win.addItem(self.status_label, row=4, col=0, colspan=2)

    def add_sample(self, sample, timestamp):
        """
        添加新样本

        Args:
            sample: 数据样本 [GSR_Cond, GSR_Res, PPG, Accel_X, Accel_Y, Accel_Z, ...]
            timestamp: 时间戳
        """
        try:
            # 相对时间
            rel_time = timestamp - self.start_time
            self.time_buffer.append(rel_time)

            # 提取数据 (根据你的通道顺序)
            if len(sample) >= 20:
                gsr_cond = sample[0]  # GSR_Skin_Conductance
                ppg = sample[2]  # PPG_A13
                accel_x = sample[3]  # Accel_LN_X
                accel_y = sample[4]  # Accel_LN_Y
                accel_z = sample[5]  # Accel_LN_Z
                hr = sample[19]  # PPGtoHR

                self.gsr_buffer.append(gsr_cond)
                self.ppg_buffer.append(ppg)
                self.accel_x_buffer.append(accel_x)
                self.accel_y_buffer.append(accel_y)
                self.accel_z_buffer.append(accel_z)

                # 心率
                if hr > 0:
                    self.current_hr = hr
                    self.hr_buffer.append(hr)

                self.current_gsr = gsr_cond

        except Exception as e:
            print(f"可视化添加数据错误: {e}")

    def update_plots(self):
        """更新图表"""
        if len(self.time_buffer) < 2:
            return

        try:
            # 转换为numpy数组
            time_array = np.array(self.time_buffer)

            # 更新GSR
            if len(self.gsr_buffer) > 0:
                gsr_array = np.array(self.gsr_buffer)
                self.curve_gsr.setData(time_array, gsr_array)

            # 更新PPG
            if len(self.ppg_buffer) > 0:
                ppg_array = np.array(self.ppg_buffer)
                self.curve_ppg.setData(time_array, ppg_array)

            # 更新加速度计
            if len(self.accel_x_buffer) > 0:
                accel_x_array = np.array(self.accel_x_buffer)
                accel_y_array = np.array(self.accel_y_buffer)
                accel_z_array = np.array(self.accel_z_buffer)
                self.curve_accel_x.setData(time_array, accel_x_array)
                self.curve_accel_y.setData(time_array, accel_y_array)
                self.curve_accel_z.setData(time_array, accel_z_array)

            # 更新心率
            if len(self.hr_buffer) > 0:
                hr_time = np.linspace(time_array[0], time_array[-1], len(self.hr_buffer))
                hr_array = np.array(self.hr_buffer)
                self.curve_hr.setData(hr_time, hr_array)

            # 更新心率标签
            if self.current_hr > 0:
                self.hr_label.setText(
                    f'<span style="font-size: 24pt; color: red; font-weight: bold;">心率: {self.current_hr:.0f} BPM</span>'
                )

            # 更新状态
            self.status_label.setText(
                f'<span style="font-size: 12pt;">样本数: {len(self.time_buffer)} | '
                f'GSR: {self.current_gsr:.3f} μS | '
                f'采集时间: {time_array[-1]:.1f}s</span>'
            )

        except Exception as e:
            print(f"更新图表错误: {e}")

    def show(self):
        """显示窗口"""
        self.win.show()

    def run(self):
        """运行GUI事件循环"""
        QtWidgets.QApplication.instance().exec_()


# 独立测试
if __name__ == "__main__":
    import random

    visualizer = RealtimeVisualizer()
    visualizer.show()


    # 模拟数据
    def simulate_data():
        t = time.time()
        sample = [
            random.uniform(0.5, 2.0),  # GSR
            random.uniform(500, 1500),  # GSR_Res
            random.uniform(2000, 3000),  # PPG
            random.uniform(-100, 100),  # Accel_X
            random.uniform(-100, 100),  # Accel_Y
            random.uniform(-100, 100),  # Accel_Z
            0, 0, 0,  # Accel_WR
            0, 0, 0,  # Gyro
            0, 0, 0,  # Mag
            0, 0,  # Temp, Pressure
            0, 0,  # External, Battery
            random.uniform(60, 80),  # HR
        ]
        visualizer.add_sample(sample, t)


    timer = QtCore.QTimer()
    timer.timeout.connect(simulate_data)
    timer.start(8)  # 模拟128Hz

    visualizer.run()