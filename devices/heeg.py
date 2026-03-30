#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neuracle HEEG设备驱动
适配多模态采集系统框架
"""

import time
import socket
import numpy as np
from enum import Enum
from struct import unpack
from threading import Lock, Thread
from typing import Optional, Callable, Dict
import logging


class HEEGState(Enum):
    """HEEG设备状态"""
    NOT_CONNECTED = 0
    CONNECTED = 1
    READY = 2
    RUNNING = 3
    STOPPED = 4


def resolve_heeg_packet(raw: bytes) -> dict:
    """
    解析HEEG数据包（基于官方代码）

    Args:
        raw: 完整的HEEG数据包

    Returns:
        解析后的数据字典
    """
    try:
        # 获取头部长度
        header_length = int.from_bytes(raw[2:6], byteorder="little", signed=False)
        head = raw[:header_length]

        # 解包头部
        (_, header_length, total_length, time_stamp, channel_count,
         sample_rate, data_count_per_channel) = unpack("<H6I", head)

        # 解析数据
        data_size = data_count_per_channel * channel_count * 4
        b_datas = raw[header_length:header_length + data_size]
        datas = np.array(
            unpack(f"<{data_count_per_channel * channel_count}f", b_datas)
        ).reshape(channel_count, data_count_per_channel)

        # 解析trigger
        trigger_start = header_length + data_size
        b_trigger = raw[trigger_start:trigger_start + 30]
        trigger_str = unpack("<30s", b_trigger)[0].decode("utf8").strip("\x00")

        trigger = None
        if trigger_str != "":
            try:
                trigger = int(trigger_str.split(":")[1])
            except:
                pass

        return {
            "timeStamp": time_stamp,
            "channelCount": channel_count,
            "sampleRate": sample_rate,
            "dataCountPerChannel": data_count_per_channel,
            "datas": datas,
            "trigger": trigger
        }
    except Exception as e:
        raise ValueError(f"解析HEEG数据包失败: {e}")


class NeuracleHEEGDevice:
    """
    Neuracle HEEG设备驱动
    连接NSH-R软件的TCP转发服务，接收64通道EEG数据
    """

    def __init__(self, hostname='127.0.0.1', port=8172):
        """
        初始化HEEG设备

        Args:
            hostname: NSH-R软件的TCP服务地址（通常是127.0.0.1）
            port: TCP端口（默认8172）
        """
        self.hostname = hostname
        self.port = port
        self.logger = logging.getLogger(__name__)

        # 连接状态
        self.state = HEEGState.NOT_CONNECTED
        self.sock: Optional[socket.socket] = None

        # 数据缓冲
        self.socket_buffer = bytes()
        self.buffer_lock = Lock()

        # 接收线程
        self.recv_thread: Optional[Thread] = None
        self.running = False

        # 数据回调
        self.data_callback: Optional[Callable] = None

        # 设备信息
        self.channel_count = 0
        self.sample_rate = 0
        self.channel_names = []  # 通道名称列表

        # 统计信息
        self.packet_count = 0
        self.total_samples = 0
        self.last_timestamp = 0

        self.data_buffer = None
        self.buffer_max_samples = 4000  # 缓存2秒数据
        self.buffer_lock = Lock()

    def connect(self, max_retries=3) -> bool:
        """
        连接HEEG设备

        Args:
            max_retries: 最大重试次数

        Returns:
            是否连接成功
        """
        self.logger.info(f"连接HEEG设备: {self.hostname}:{self.port}")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)

        retry_count = 0
        while self.state == HEEGState.NOT_CONNECTED and retry_count < max_retries:
            try:
                self.sock.connect((self.hostname, self.port))
                self.sock.setblocking(False)
                self.state = HEEGState.CONNECTED

                # 启动接收线程
                self.running = True
                self.recv_thread = Thread(target=self._recv_loop, daemon=True)
                self.recv_thread.start()

                self.logger.info("✅ HEEG设备连接成功")
                return True

            except Exception as e:
                retry_count += 1
                self.logger.warning(
                    f"连接失败 (尝试 {retry_count}/{max_retries}): {e}"
                )
                if retry_count < max_retries:
                    time.sleep(1)

        self.logger.error("❌ 无法连接到HEEG设备")
        self.logger.error("请检查:")
        self.logger.error("  1. NSH-R软件是否正在运行")
        self.logger.error("  2. 是否已开始采集数据")
        self.logger.error("  3. config.ini中 [DataSend] Value=1")
        return False

    def disconnect(self):
        """断开连接"""
        self.logger.info("断开HEEG设备...")

        self.running = False
        self.state = HEEGState.STOPPED

        if self.recv_thread and self.recv_thread.is_alive():
            self.recv_thread.join(timeout=2)

        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

        self.state = HEEGState.NOT_CONNECTED
        self.logger.info("已断开连接")

    def set_data_callback(self, callback: Callable):
        """
        设置数据回调函数

        Args:
            callback: 回调函数，接收data_struct字典参数
        """
        self.data_callback = callback

    def start_streaming(self) -> bool:
        """开始数据流"""
        if self.state == HEEGState.NOT_CONNECTED:
            self.logger.error("设备未连接")
            return False

        if self.state == HEEGState.READY:
            self.state = HEEGState.RUNNING
            self.logger.info("开始数据流")
            return True

        return False

    def stop_streaming(self):
        """停止数据流"""
        if self.state == HEEGState.RUNNING:
            self.state = HEEGState.READY
            self.logger.info("停止数据流")

    def _recv_loop(self):
        """接收数据循环（运行在独立线程）"""
        self.logger.info("HEEG接收线程已启动")

        while self.running and self.state != HEEGState.STOPPED:
            try:
                self._recv_and_parse()
                time.sleep(1e-6)  # 短暂休眠，避免CPU占用过高
            except Exception as e:
                self.logger.error(f"接收循环错误: {e}", exc_info=True)
                time.sleep(0.1)

        self.logger.info("HEEG接收线程已停止")

    def _recv_and_parse(self):
        """接收并解析数据"""
        buf = bytes()
        retry = True

        # 接收数据
        while retry:
            try:
                for _ in range(10):
                    chunk = self.sock.recv(4096)
                    buf += chunk
                    if len(self.socket_buffer) > 0:
                        self._resolve_buffer()
            except BlockingIOError:
                if len(buf) > 0:
                    retry = False
                else:
                    retry = True
                    break
            except Exception as e:
                self.logger.error(f"Socket接收错误: {e}")
                retry = False

        # 添加到缓冲区
        if len(buf) > 0:
            with self.buffer_lock:
                self.socket_buffer += buf
            self._resolve_buffer()

    def _resolve_buffer(self):
        """解析缓冲区中的数据包"""
        while True:
            with self.buffer_lock:
                if len(self.socket_buffer) < 2:
                    return

                # 检查包头
                head_token = bytes.fromhex('5AA5')
                if self.socket_buffer[0:2] != head_token:
                    # 尝试找到下一个有效包头
                    self.socket_buffer = self.socket_buffer[1:]
                    continue

                # 获取包长度
                if len(self.socket_buffer) < 10:
                    return

                total_length = int.from_bytes(
                    self.socket_buffer[6:10], byteorder='little', signed=False
                )

                # 检查是否有完整包
                if len(self.socket_buffer) < total_length:
                    return

                # 提取完整包
                msg = self.socket_buffer[:total_length]

                # 检查包尾
                tail_token = bytes.fromhex('A55A')
                if msg[-2:] != tail_token:
                    self.socket_buffer = self.socket_buffer[total_length:]
                    continue

                # 从缓冲区移除已处理的包
                self.socket_buffer = self.socket_buffer[total_length:]

            # 解析数据包
            try:
                # 解析成功
                data_struct = resolve_heeg_packet(msg)

                # 更新实时数据缓存
                with self.buffer_lock:
                    if self.data_buffer is None:
                        self.data_buffer = data_struct['datas']
                    else:
                        # 拼接新数据
                        self.data_buffer = np.concatenate(
                            [self.data_buffer, data_struct['datas']],
                            axis=1
                        )

                        # 保留最后buffer_max_samples个样本
                        if self.data_buffer.shape[1] > self.buffer_max_samples:
                            self.data_buffer = self.data_buffer[:, -self.buffer_max_samples:]


                # 更新设备信息...

                # 更新设备信息（首次接收时）
                if self.state == HEEGState.CONNECTED:
                    self.channel_count = data_struct["channelCount"]
                    self.sample_rate = data_struct["sampleRate"]

                    # 生成通道名称
                    self.channel_names = [
                        f"EEG_{i + 1}" for i in range(self.channel_count)
                    ]

                    self.state = HEEGState.READY
                    self.logger.info(
                        f"设备就绪: {self.channel_count}通道, "
                        f"{self.sample_rate}Hz"
                    )

                # 更新统计信息
                self.packet_count += 1
                self.total_samples += data_struct["dataCountPerChannel"]
                self.last_timestamp = data_struct["timeStamp"]

                # 调用回调
                if self.state == HEEGState.RUNNING and self.data_callback:
                    self.data_callback(data_struct)

            except Exception as e:
                self.logger.error(f"解析数据包失败: {e}")

    def get_device_info(self) -> Dict:
        """
        获取设备信息

        Returns:
            设备信息字典
        """
        return {
            'device_type': 'Neuracle HEEG',
            'device_id': f'{self.hostname}:{self.port}',
            'channel_count': self.channel_count,
            'sample_rate': self.sample_rate,
            'channel_names': self.channel_names,
            'state': self.state.name,
            'hostname': self.hostname,
            'port': self.port,
            'packet_count': self.packet_count,
            'total_samples': self.total_samples,
            'last_timestamp': self.last_timestamp
        }

    def is_connected(self) -> bool:
        """是否已连接"""
        return self.state != HEEGState.NOT_CONNECTED

    def is_streaming(self) -> bool:
        """是否正在流式传输"""
        return self.state == HEEGState.RUNNING

    def get_channel_count(self) -> int:
        """获取通道数"""
        return self.channel_count

    def get_sample_rate(self) -> int:
        """获取采样率"""
        return self.sample_rate

    def get_channel_names(self) -> list:
        """获取通道名称列表"""
        return self.channel_names

    def get_latest_data(self, num_samples: int = 1000):
        """
        获取最新的EEG数据（用于GUI实时显示）

        Args:
            num_samples: 返回的样本数

        Returns:
            numpy数组 (channels, samples) 或 None
        """
        with self.buffer_lock:
            if self.data_buffer is None:
                return None

            # 返回最后num_samples个样本
            if self.data_buffer.shape[1] >= num_samples:
                return self.data_buffer[:, -num_samples:].copy()
            else:
                return self.data_buffer.copy()

# ==================== 测试代码 ====================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Neuracle HEEG 设备测试")
    print("=" * 60)
    print("\n⚠️  请确保:")
    print("  1. NSH-R软件正在运行")
    print("  2. 设备状态显示'在线'")
    print("  3. 正在采集数据")
    print("  4. config.ini中 [DataSend] Value=1")
    print("\n按 Enter 继续...")
    input()

    # 数据统计
    sample_count = 0
    packet_count = 0
    start_time = time.time()


    def data_callback(data_struct):
        global sample_count, packet_count

        packet_count += 1
        sample_count += data_struct['dataCountPerChannel']

        if packet_count % 100 == 0:
            elapsed = time.time() - start_time
            rate = sample_count / elapsed if elapsed > 0 else 0

            print(f"\r📊 数据包: {packet_count}, "
                  f"样本: {sample_count}, "
                  f"速率: {rate:.1f} samples/s, "
                  f"Trigger: {data_struct.get('trigger', 'None')}", end='')


    # 创建设备
    device = NeuracleHEEGDevice(hostname='127.0.0.1', port=8172)

    # 连接
    if device.connect():
        print("\n✅ 设备连接成功！")

        # 等待设备就绪
        time.sleep(0.5)

        info = device.get_device_info()
        print(f"\n📋 设备信息:")
        print(f"  类型: {info['device_type']}")
        print(f"  通道数: {info['channel_count']}")
        print(f"  采样率: {info['sample_rate']} Hz")
        print(f"  状态: {info['state']}")

        # 设置回调
        device.set_data_callback(data_callback)

        # 开始流式传输
        device.start_streaming()

        print("\n开始接收数据...")
        print("运行30秒后自动停止（按Ctrl+C提前停止）\n")

        try:
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n\n用户中断...")

        # 停止
        device.stop_streaming()
        device.disconnect()

        print(f"\n\n" + "=" * 60)
        print(f"测试完成!")
        print(f"  总数据包: {packet_count}")
        print(f"  总样本数: {sample_count}")
        print(f"  运行时间: {time.time() - start_time:.1f}秒")
        print("=" * 60)

    else:
        print("\n❌ 无法连接到设备")