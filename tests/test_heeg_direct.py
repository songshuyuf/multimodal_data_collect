#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接连接EEG设备测试
使用设备IP: 192.168.3.88
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入测试函数
from test_heeg_connection import test_connection, test_extended

if __name__ == "__main__":
    print("\n")
    print("=" * 60)
    print("  直接连接Neuracle HEEG设备测试")
    print("=" * 60)
    print("\n📍 设备信息:")
    print("   IP地址: 192.168.3.88")
    print("   端口: 8172")
    print("   通道数: 64")
    print("   采样率: 2000 Hz")
    print("\n⚠️  确保:")
    print("   1. NSH-R软件显示设备'在线'")
    print("   2. 你的电脑与设备在同一网络")
    print("\n按 Enter 继续...")
    input()

    # 使用设备IP测试
    DEVICE_IP = '192.168.3.88'
    DEVICE_PORT = 8172

    print(f"\n尝试连接 {DEVICE_IP}:{DEVICE_PORT}...")

    success = test_connection(hostname=DEVICE_IP, port=DEVICE_PORT)

    if success:
        print("\n是否进行扩展测试? (解析数据包内容)")
        print("输入 'y' 继续，其他键跳过: ", end='')
        choice = input().strip().lower()

        if choice == 'y':
            test_extended(hostname=DEVICE_IP, port=DEVICE_PORT)

    print("\n测试完成！")