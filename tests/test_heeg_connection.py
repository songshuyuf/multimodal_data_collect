#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HEEG设备连接测试脚本
简化版本，用于快速测试连接
"""

import time
import socket
import sys


def test_connection(hostname='127.0.0.1', port=8172, timeout=5):
    """
    测试HEEG服务器连接

    Args:
        hostname: 服务器地址
        port: 端口号
        timeout: 超时时间(秒)
    """
    print("=" * 60)
    print("HEEG设备连接测试")
    print("=" * 60)
    print(f"目标地址: {hostname}:{port}")
    print(f"超时时间: {timeout}秒")
    print("-" * 60)

    # 创建socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        print("\n[1/3] 正在连接TCP服务器...")
        sock.connect((hostname, port))
        print("✅ TCP连接成功！")

        print("\n[2/3] 等待接收数据包...")
        sock.setblocking(False)

        start_time = time.time()
        received_data = False

        while time.time() - start_time < timeout:
            try:
                data = sock.recv(4096)
                if len(data) > 0:
                    received_data = True
                    print(f"✅ 接收到数据! 大小: {len(data)} bytes")
                    print(f"   前20字节(HEX): {data[:20].hex()}")

                    # 检查包头
                    if data[:2] == bytes.fromhex('5AA5'):
                        print("✅ 数据包头正确 (5AA5)")
                    else:
                        print(f"⚠️  数据包头异常: {data[:2].hex()}")

                    break
            except BlockingIOError:
                time.sleep(0.1)
                continue
            except Exception as e:
                print(f"❌ 接收数据时出错: {e}")
                break

        if not received_data:
            print(f"❌ 超时未收到数据 ({timeout}秒)")
            print("\n可能的原因:")
            print("  1. NSH-R软件未启动数据转发")
            print("  2. EEG设备未连接")
            print("  3. 软件设置中TCP服务未开启")
            return False

        print("\n[3/3] 连接测试完成")
        print("=" * 60)
        print("✅ 测试通过！EEG设备连接正常")
        print("=" * 60)
        return True

    except socket.timeout:
        print(f"❌ 连接超时 ({timeout}秒)")
        print("\n请检查:")
        print("  1. NSH-R软件是否已启动")
        print("  2. 软件是否开启了TCP转发服务")
        print("  3. 端口号是否正确(默认8172)")
        return False

    except ConnectionRefusedError:
        print("❌ 连接被拒绝")
        print("\n请检查:")
        print("  1. NSH-R软件是否已启动")
        print("  2. TCP服务器是否运行在 127.0.0.1:8172")
        print("  3. 防火墙是否阻止了连接")
        return False

    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

    finally:
        sock.close()
        print("\n连接已关闭")


def test_extended(hostname='127.0.0.1', port=8172):
    """
    扩展测试：尝试解析数据包
    """
    print("\n" + "=" * 60)
    print("扩展测试: 解析数据包")
    print("=" * 60)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)

    try:
        sock.connect((hostname, port))
        sock.setblocking(False)

        buffer = bytes()
        start_time = time.time()
        packet_count = 0

        print("接收数据包中... (10秒)")

        while time.time() - start_time < 10:
            try:
                chunk = sock.recv(4096)
                buffer += chunk

                # 尝试解析包
                while len(buffer) >= 10:
                    # 查找包头
                    if buffer[:2] != bytes.fromhex('5AA5'):
                        buffer = buffer[1:]
                        continue

                    # 读取包长度
                    total_length = int.from_bytes(buffer[6:10], byteorder='little')

                    if len(buffer) < total_length:
                        break  # 等待更多数据

                    # 提取完整包
                    packet = buffer[:total_length]
                    buffer = buffer[total_length:]

                    # 检查包尾
                    if packet[-2:] == bytes.fromhex('A55A'):
                        packet_count += 1

                        if packet_count <= 3:  # 只详细显示前3个包
                            print(f"\n📦 数据包 #{packet_count}")
                            print(f"   包大小: {total_length} bytes")

                            # 解析头部
                            if total_length >= 28:
                                header_len = int.from_bytes(packet[2:6], byteorder='little')
                                timestamp = int.from_bytes(packet[10:14], byteorder='little')
                                channel_count = int.from_bytes(packet[14:18], byteorder='little')
                                sample_rate = int.from_bytes(packet[18:22], byteorder='little')
                                samples = int.from_bytes(packet[22:26], byteorder='little')

                                print(f"   时间戳: {timestamp} ms")
                                print(f"   通道数: {channel_count}")
                                print(f"   采样率: {sample_rate} Hz")
                                print(f"   样本数: {samples}")

            except BlockingIOError:
                time.sleep(0.01)
                continue

        print(f"\n总共接收到 {packet_count} 个有效数据包")

        if packet_count > 0:
            print("✅ 数据流正常！")
            return True
        else:
            print("❌ 未接收到有效数据包")
            return False

    except Exception as e:
        print(f"❌ 扩展测试失败: {e}")
        return False
    finally:
        sock.close()


if __name__ == "__main__":
    print("\n")
    print("=" * 60)
    print("  Neuracle HEEG 设备连接测试工具")
    print("=" * 60)
    print("\n⚠️  测试前请确保:")
    print("   1. NSH-R软件已启动")
    print("   2. EEG设备已连接")
    print("   3. 软件中已开启TCP数据转发")
    print("\n按 Enter 继续...")
    input()

    # 基础连接测试
    success = test_connection()

    if success:
        print("\n是否进行扩展测试? (解析数据包内容)")
        print("输入 'y' 继续，其他键跳过: ", end='')
        choice = input().strip().lower()

        if choice == 'y':
            test_extended()

    print("\n测试完成！")
    print("\n" + "=" * 60)