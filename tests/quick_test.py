"""
快速测试脚本 - 模拟设备模式
直接运行测试整个系统（基于新架构 ExperimentRunner）
"""

import sys
import time
from PyQt5.QtWidgets import QApplication

from devices.mock import MockHEEGDevice, MockShimmerDevice
from engine.runner import ExperimentRunner


class MockDeviceController:

    def __init__(self):
        self.heeg_device = MockHEEGDevice()
        self.shimmer_device = MockShimmerDevice()
        self.heeg_connected = False
        self.shimmer_connected = False
        self.is_recording = False
        print("✓ 模拟设备控制器已创建")

    def initialize_all_devices(self):
        self.heeg_connected = self.heeg_device.connect()
        self.shimmer_connected = self.shimmer_device.connect()
        print(f"HEEG: {'✓' if self.heeg_connected else '✗'}")
        print(f"Shimmer: {'✓' if self.shimmer_connected else '✗'}")

    def start_recording(self):
        if self.heeg_connected:
            self.heeg_device.start_streaming()
        if self.shimmer_connected:
            self.shimmer_device.start_streaming()
        self.is_recording = True
        print("✓ 录制已开始（模拟模式）")

    def stop_recording(self):
        if self.heeg_connected:
            self.heeg_device.stop_streaming()
        if self.shimmer_connected:
            self.shimmer_device.stop_streaming()
        self.is_recording = False
        print("✓ 录制已停止")


def quick_test():
    print("\n" + "=" * 60)
    print("快速测试 - 模拟设备 + ExperimentRunner")
    print("=" * 60 + "\n")

    app = QApplication(sys.argv)

    print("[1/3] 创建模拟设备...")
    device_controller = MockDeviceController()
    device_controller.initialize_all_devices()

    print("\n[2/3] 创建 ExperimentRunner...")
    runner = ExperimentRunner(
        config_path='experiment_config.json',
        dataset_root='./dataset',
        session_dir='./data/sessions/quick_test',
    )

    runner.task_started.connect(
        lambda name, tid: print(f"\n>>> 任务开始: {name} (ID: {tid})")
    )
    runner.experiment_finished.connect(
        lambda: print("\n实验完成！")
    )
    runner.status_message.connect(
        lambda msg: print(f"  [status] {msg}")
    )

    print("\n[3/3] 开始实验...")
    print("=" * 60 + "\n")
    device_controller.start_recording()
    runner.start()
    sys.exit(app.exec_())


def minimal_test():
    print("\n" + "=" * 60)
    print("最小测试 - 仅测试模拟数据生成")
    print("=" * 60 + "\n")

    print("[测试1] HEEG设备")
    heeg = MockHEEGDevice()
    heeg.connect()
    heeg.start_streaming()
    time.sleep(3)
    print(f"✓ 生成了 {len(heeg.data_buffer)} 个HEEG数据包")
    heeg.stop_streaming()

    print("\n[测试2] Shimmer设备")
    shimmer = MockShimmerDevice()
    shimmer.connect()
    shimmer.start_streaming()
    time.sleep(3)
    print(f"✓ 生成了 {len(shimmer.data_buffer)} 个Shimmer数据包")

    if shimmer.data_buffer:
        last_packet = shimmer.data_buffer[-1]
        sample, timestamp = shimmer.extract_sample_from_packet(last_packet)
        print(f"\n最后一个样本:")
        print(f"  GSR电导: {sample[0]:.6f} µS")
        print(f"  PPG: {sample[2]:.2f}")
        print(f"  心率: {sample[16]:.1f} BPM")

    shimmer.stop_streaming()
    print("\n✓ 测试完成")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='快速测试脚本')
    parser.add_argument('--mode', choices=['full', 'minimal'], default='full',
                        help='测试模式: full=完整测试, minimal=最小测试')
    args = parser.parse_args()

    if args.mode == 'minimal':
        minimal_test()
    else:
        quick_test()
