#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连接本地HEEG服务测试
TCP服务器在 127.0.0.1:8172
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入我们之前写的驱动
import time
import socket
import numpy as np
from struct import unpack
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def resolve_heeg_packet(raw: bytes) -> dict:
    """解析HEEG数据包"""
    try:
        header_length = int.from_bytes(raw[2:6], byteorder="little", signed=False)
        head = raw[:header_length]

        (_, header_length, total_length, time_stamp, channel_count,
         sample_rate, data_count_per_channel) = unpack("<H6I", head)

        data_size = data_count_per_channel * channel_count * 4
        b_datas = raw[header_length:header_length + data_size]
        datas = np.array(
            unpack(f"<{data_count_per_channel * channel_count}f", b_datas)
        ).reshape(channel_count, data_count_per_channel)

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
        print(f"解析错误: {e}")
        raise


def test_connection():
    """测试连接本地HEEG服务"""
    print("=" * 60)
    print("连接本地HEEG服务测试")
    print("=" * 60)
    print("\n目标: 127.0.0.1:8172")
    print("\n⚠️  确保NSH-R软件正在运行并采集数据\n")

    # 创建socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)

    try:
        print("[1/4] 连接TCP服务器...")
        sock.connect(('127.0.0.1', 8172))
        print("✅ 连接成功！")

        sock.setblocking(False)

        print("\n[2/4] 等待接收数据...")
        buffer = bytes()
        start_time = time.time()
        first_packet = True
        packet_count = 0

        while time.time() - start_time < 10:  # 运行10秒
            try:
                chunk = sock.recv(4096)
                if len(chunk) > 0:
                    buffer += chunk

                    # 尝试解析数据包
                    while len(buffer) >= 10:
                        # 查找包头
                        if buffer[:2] != bytes.fromhex('5AA5'):
                            buffer = buffer[1:]
                            continue

                        # 获取包长度
                        total_length = int.from_bytes(buffer[6:10], byteorder='little')

                        if len(buffer) < total_length:
                            break

                        # 提取完整包
                        packet = buffer[:total_length]
                        buffer = buffer[total_length:]

                        # 检查包尾
                        if packet[-2:] != bytes.fromhex('A55A'):
                            continue

                        # 解析数据
                        try:
                            data_struct = resolve_heeg_packet(packet)
                            packet_count += 1

                            if first_packet:
                                print("✅ 成功接收到数据包！")
                                print(f"\n[3/4] 数据包信息:")
                                print(f"  通道数: {data_struct['channelCount']}")
                                print(f"  采样率: {data_struct['sampleRate']} Hz")
                                print(f"  每包样本数: {data_struct['dataCountPerChannel']}")
                                print(f"  数据形状: {data_struct['datas'].shape}")
                                print(f"  时间戳: {data_struct['timeStamp']} ms")
                                if data_struct['trigger']:
                                    print(f"  Trigger: {data_struct['trigger']}")

                                # 显示前3个通道的前5个样本
                                print(f"\n  前3通道数据示例:")
                                for i in range(min(3, data_struct['channelCount'])):
                                    samples = data_struct['datas'][i, :5]
                                    print(f"    Ch{i + 1}: {samples}")

                                first_packet = False

                            if packet_count % 10 == 0:
                                print(f"\r  已接收: {packet_count} 个数据包", end='')

                        except Exception as e:
                            print(f"\n解析数据包失败: {e}")

            except BlockingIOError:
                time.sleep(0.01)
                continue
            except Exception as e:
                print(f"\n接收数据错误: {e}")
                break

        print(f"\n\n[4/4] 测试完成")
        print("=" * 60)
        print(f"✅ 成功接收 {packet_count} 个数据包")
        print("=" * 60)
        print("\n🎉 恭喜！HEEG设备连接成功！")
        print("\n现在可以集成到你的多模态采集系统了！")

        return True

    except socket.timeout:
        print("❌ 连接超时")
        return False
    except ConnectionRefusedError:
        print("❌ 连接被拒绝")
        print("\n请检查:")
        print("  1. NSH-R软件是否正在运行")
        print("  2. 是否已开始采集数据")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False
    finally:
        sock.close()


if __name__ == "__main__":
    print("\n")
    test_connection()
    print("\n")