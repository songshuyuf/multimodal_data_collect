"""
模拟数据生成器
用于在没有真实设备时测试系统
"""

import numpy as np
import time
import threading
from collections import deque


class MockHEEGDevice:
    """模拟HEEG设备"""

    def __init__(self, sampling_rate=2000, n_channels=64):
        """
        初始化模拟HEEG设备

        Args:
            sampling_rate: 采样率 (Hz)
            n_channels: 通道数
        """
        self.sampling_rate = sampling_rate
        self.n_channels = n_channels

        # 数据生成参数
        self.amplitude = 50.0  # 微伏
        self.base_freq = 10.0  # Alpha波频率

        # 运行状态
        self.is_streaming = False
        self.data_thread = None

        # 数据缓冲区
        self.data_buffer = deque(maxlen=10000)

        print(f"✓ 模拟HEEG设备已创建 ({n_channels}通道 @ {sampling_rate}Hz)")

    def connect(self):
        """连接设备"""
        time.sleep(0.5)
        print("✓ 模拟HEEG设备已连接")
        return True

    def start_streaming(self):
        """开始数据流"""
        if self.is_streaming:
            return False

        self.is_streaming = True
        self.data_thread = threading.Thread(target=self._generate_data_loop, daemon=True)
        self.data_thread.start()

        print("✓ 模拟HEEG数据流已启动")
        return True

    def stop_streaming(self):
        """停止数据流"""
        self.is_streaming = False
        if self.data_thread:
            self.data_thread.join(timeout=1)
        print("✓ 模拟HEEG数据流已停止")

    def _generate_data_loop(self):
        """数据生成循环"""
        sample_interval = 1.0 / self.sampling_rate  # 秒
        t = 0

        while self.is_streaming:
            start_time = time.time()

            # 生成一包数据（32个样本）
            samples_per_packet = 32

            for _ in range(samples_per_packet):
                # 生成64通道的模拟EEG数据
                sample = []
                for ch in range(self.n_channels):
                    # 基础Alpha波 + 少量噪声
                    freq = self.base_freq + np.random.randn() * 2  # 8-12 Hz
                    phase = np.random.rand() * 2 * np.pi

                    value = self.amplitude * np.sin(2 * np.pi * freq * t + phase)
                    value += np.random.randn() * 5  # 噪声

                    sample.append(value)

                # 模拟数据包格式
                data_packet = {
                    'timestamp': time.time(),
                    'datas': np.array(sample).reshape(self.n_channels, 1),
                    'count': samples_per_packet
                }

                self.data_buffer.append(data_packet)

                t += sample_interval

            # 控制生成速率
            elapsed = time.time() - start_time
            sleep_time = (samples_per_packet * sample_interval) - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def get_device_info(self):
        """获取设备信息"""
        return {
            'sampling_rate': self.sampling_rate,
            'n_channels': self.n_channels,
            'device_type': 'Mock HEEG'
        }

    def disconnect(self):
        """断开连接"""
        self.stop_streaming()
        print("✓ 模拟HEEG设备已断开")


class MockShimmerDevice:
    """模拟Shimmer GSR+设备"""

    def __init__(self, sampling_rate=128):
        """
        初始化模拟Shimmer设备

        Args:
            sampling_rate: 采样率 (Hz)
        """
        self.sampling_rate = sampling_rate

        # 通道名称
        self.channel_names = [
            'GSR_Skin_Conductance',
            'GSR_Skin_Resistance',
            'PPG_A13',
            'Accel_LN_X', 'Accel_LN_Y', 'Accel_LN_Z',
            'Gyro_X', 'Gyro_Y', 'Gyro_Z',
            'Mag_X', 'Mag_Y', 'Mag_Z',
            'Temperature_BMP280', 'Pressure_BMP280',
            'Ext_Exp_A7', 'VSenseBatt', 'PPGtoHR'
        ]

        # 运行状态
        self.is_streaming = False
        self.data_thread = None

        # 数据缓冲区
        self.data_buffer = deque(maxlen=1000)

        # 心率相关
        self.current_hr = 72.0
        self.hr_variation = 5.0

        print(f"✓ 模拟Shimmer设备已创建 (17通道 @ {sampling_rate}Hz)")

    def connect(self, com_port=None):
        """连接设备"""
        time.sleep(0.5)
        print("✓ 模拟Shimmer设备已连接")
        return True

    def start_streaming(self):
        """开始数据流"""
        if self.is_streaming:
            return False

        self.is_streaming = True
        self.data_thread = threading.Thread(target=self._generate_data_loop, daemon=True)
        self.data_thread.start()

        print("✓ 模拟Shimmer数据流已启动")
        return True

    def stop_streaming(self):
        """停止数据流"""
        self.is_streaming = False
        if self.data_thread:
            self.data_thread.join(timeout=1)
        print("✓ 模拟Shimmer数据流已停止")

    def _generate_data_loop(self):
        """数据生成循环"""
        sample_interval = 1.0 / self.sampling_rate
        t = 0

        while self.is_streaming:
            start_time = time.time()

            # 生成一个样本
            sample = self._generate_sample(t)

            # 创建数据包（模拟pyshimmer的格式）
            data_packet = MockDataPacket(sample)
            self.data_buffer.append(data_packet)

            t += sample_interval

            # 控制生成速率
            elapsed = time.time() - start_time
            sleep_time = sample_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _generate_sample(self, t):
        """生成一个样本的17通道数据"""
        # GSR（皮肤电导和电阻）
        gsr_conductance = 0.005 + np.random.randn() * 0.001  # µS
        gsr_resistance = 1.0 / gsr_conductance if gsr_conductance > 0 else 100000

        # PPG（光电容积描记 - 模拟心跳）
        hr_freq = self.current_hr / 60.0  # Hz
        ppg = 2250 + 50 * np.sin(2 * np.pi * hr_freq * t) + np.random.randn() * 10

        # 加速度计（模拟静止状态，有少量抖动）
        accel_x = 0.0 + np.random.randn() * 0.02
        accel_y = 0.0 + np.random.randn() * 0.02
        accel_z = 1.0 + np.random.randn() * 0.02  # 重力

        # 陀螺仪（模拟静止）
        gyro_x = np.random.randn() * 0.5
        gyro_y = np.random.randn() * 0.5
        gyro_z = np.random.randn() * 0.5

        # 磁力计
        mag_x = 25.0 + np.random.randn() * 1.0
        mag_y = 10.0 + np.random.randn() * 1.0
        mag_z = -15.0 + np.random.randn() * 1.0

        # 温度和压力
        temperature = 23.5 + np.random.randn() * 0.2
        pressure = 1013.2 + np.random.randn() * 0.5

        # 其他
        ext_exp = 0.0
        battery = 3.8 + np.random.randn() * 0.01

        # 心率（从PPG计算得出）
        self.current_hr += np.random.randn() * 0.5
        self.current_hr = np.clip(self.current_hr, 60, 85)

        return [
            gsr_conductance,
            gsr_resistance,
            ppg,
            accel_x, accel_y, accel_z,
            gyro_x, gyro_y, gyro_z,
            mag_x, mag_y, mag_z,
            temperature, pressure,
            ext_exp, battery,
            self.current_hr
        ]

    def extract_sample_from_packet(self, packet):
        """从数据包提取样本"""
        return packet.data, packet.timestamp

    def get_channel_names(self):
        """获取通道名称"""
        return self.channel_names

    def get_device_info(self):
        """获取设备信息"""
        return {
            'sampling_rate': self.sampling_rate,
            'n_channels': len(self.channel_names),
            'device_type': 'Mock Shimmer GSR+'
        }

    def disconnect(self):
        """断开连接"""
        self.stop_streaming()
        print("✓ 模拟Shimmer设备已断开")


class MockDataPacket:
    """模拟pyshimmer的DataPacket"""

    def __init__(self, data):
        self.data = data
        self.timestamp = time.time()


# ==================== 修改device_controller.py的方案 ====================

"""
在 device_controller.py 中添加模拟模式开关：

class DeviceController:
    def __init__(self, use_mock_devices=False):
        self.use_mock_devices = use_mock_devices

        if use_mock_devices:
            print("\n" + "="*60)
            print("⚠️  使用模拟设备模式")
            print("="*60 + "\n")

    def initialize_heeg(self):
        if self.use_mock_devices:
            from mock_devices import MockHEEGDevice
            self.heeg_device = MockHEEGDevice()
            self.heeg_connected = self.heeg_device.connect()
        else:
            # 原有的真实设备代码
            from neuracle_heeg_device import NeuracleTCPDevice
            ...

    def initialize_shimmer(self):
        if self.use_mock_devices:
            from mock_devices import MockShimmerDevice
            self.shimmer_device = MockShimmerDevice()
            self.shimmer_connected = self.shimmer_device.connect()
        else:
            # 原有的真实设备代码
            from shimmer_device import ShimmerGSRDevice
            ...
"""

# ==================== 测试代码 ====================
if __name__ == '__main__':
    import csv

    print("=" * 60)
    print("测试模拟设备")
    print("=" * 60)

    # 1. 测试HEEG
    print("\n[测试1] 模拟HEEG设备")
    heeg = MockHEEGDevice(sampling_rate=2000, n_channels=64)
    heeg.connect()
    heeg.start_streaming()

    time.sleep(2)
    print(f"  生成了 {len(heeg.data_buffer)} 个数据包")

    # 保存一些样本
    with open('mock_heeg_test.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp'] + [f'Ch{i + 1}' for i in range(64)])

        for i in range(min(100, len(heeg.data_buffer))):
            packet = heeg.data_buffer[i]
            row = [packet['timestamp']] + packet['datas'].flatten().tolist()
            writer.writerow(row)

    print("  ✓ 已保存测试数据: mock_heeg_test.csv")
    heeg.stop_streaming()

    # 2. 测试Shimmer
    print("\n[测试2] 模拟Shimmer设备")
    shimmer = MockShimmerDevice(sampling_rate=128)
    shimmer.connect()
    shimmer.start_streaming()

    time.sleep(2)
    print(f"  生成了 {len(shimmer.data_buffer)} 个数据包")

    # 保存一些样本
    with open('mock_shimmer_test.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp'] + shimmer.channel_names)

        for i in range(min(100, len(shimmer.data_buffer))):
            packet = shimmer.data_buffer[i]
            sample, timestamp = shimmer.extract_sample_from_packet(packet)
            row = [timestamp] + sample
            writer.writerow(row)

    print("  ✓ 已保存测试数据: mock_shimmer_test.csv")
    shimmer.stop_streaming()

    print("\n✓ 测试完成")