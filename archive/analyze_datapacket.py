"""
使用 ShimmerGSRDevice 的校准功能
检查它是否有 get_calibrated_data() 或类似方法
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).parent
core_path = project_root / 'core'
if str(core_path) not in sys.path:
    sys.path.insert(0, str(core_path))

print("=" * 60)
print("检查 ShimmerGSRDevice 的校准方法")
print("=" * 60)

try:
    import core.config as core_config
    from core.shimmer_device import ShimmerGSRDevice

    # 创建设备
    shimmer = ShimmerGSRDevice(core_config.SHIMMER_CONFIG)

    print("\nShimmerGSRDevice 的所有方法:")
    methods = [m for m in dir(shimmer) if not m.startswith('_')]
    for method in methods:
        attr = getattr(shimmer, method)
        if callable(attr):
            print(f"  ✓ {method}()")
        else:
            print(f"  - {method}")

    # 连接
    com_ports = shimmer._list_com_ports()
    if not com_ports or not shimmer.connect(com_ports[0]):
        print("\n✗ 连接失败")
        sys.exit(1)

    print(f"\n✓ 已连接到 {com_ports[0]}")

    # 启动数据流
    if not shimmer.start_streaming():
        print("✗ 启动失败")
        shimmer.disconnect()
        sys.exit(1)

    print("✓ 数据流已启动")

    # 读取一个数据包
    print("\n等待数据包...")
    data = None
    for _ in range(1000):
        success, d = shimmer.read_data()
        if success and d:
            data = d
            break
        time.sleep(0.01)

    if not data:
        print("✗ 未收到数据")
        shimmer.stop_streaming()
        shimmer.disconnect()
        sys.exit(1)

    print("✓ 收到数据包")

    print("\n" + "=" * 60)
    print("DataPacket 分析")
    print("=" * 60)

    # 检查 DataPacket 的方法
    print("\nDataPacket 的方法:")
    data_methods = [m for m in dir(data) if not m.startswith('__')]
    for method in data_methods:
        attr = getattr(data, method)
        if callable(attr):
            print(f"  ✓ {method}()")
        else:
            print(f"  - {method}")

    # 尝试调用可能的校准方法
    print("\n" + "=" * 60)
    print("尝试获取校准数据")
    print("=" * 60)

    # 方法1: 检查 data 是否有 calibrated_values
    if hasattr(data, 'calibrated_values'):
        print("\n✓ data.calibrated_values 存在")
        print(f"  {data.calibrated_values}")

    # 方法2: 检查 data 是否有 get_calibrated_data
    if hasattr(data, 'get_calibrated_data'):
        print("\n✓ data.get_calibrated_data() 存在")
        try:
            cal_data = data.get_calibrated_data()
            print(f"  {cal_data}")
        except Exception as e:
            print(f"  调用失败: {e}")

    # 方法3: 检查 shimmer 是否有校准方法
    if hasattr(shimmer, 'calibrate_data'):
        print("\n✓ shimmer.calibrate_data() 存在")
        try:
            cal_data = shimmer.calibrate_data(data)
            print(f"  {cal_data}")
        except Exception as e:
            print(f"  调用失败: {e}")

    if hasattr(shimmer, 'get_calibrated_data'):
        print("\n✓ shimmer.get_calibrated_data() 存在")
        try:
            cal_data = shimmer.get_calibrated_data(data)
            print(f"  {cal_data}")
        except Exception as e:
            print(f"  调用失败: {e}")

    # 方法4: 检查 shimmer_device.py 的源代码提示
    print("\n" + "=" * 60)
    print("查看 shimmer_device.py 中可能的提示")
    print("=" * 60)

    # 读取 shimmer_device.py
    shimmer_file = core_path / 'shimmer_device.py'
    if shimmer_file.exists():
        print(f"\n✓ 找到文件: {shimmer_file}")

        with open(shimmer_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 搜索关键词
        keywords = ['calibrat', 'GSR_Conductance', 'GSR_Resistance', 'cal(', 'convert']

        print("\n关键代码片段:")
        lines = content.split('\n')
        for i, line in enumerate(lines):
            for keyword in keywords:
                if keyword.lower() in line.lower():
                    # 显示前后3行
                    start = max(0, i-2)
                    end = min(len(lines), i+3)
                    print(f"\n  [{i+1}] 找到 '{keyword}':")
                    for j in range(start, end):
                        prefix = ">>>" if j == i else "   "
                        print(f"    {prefix} {lines[j]}")
                    break
    else:
        print(f"✗ 未找到文件: {shimmer_file}")

    shimmer.stop_streaming()
    shimmer.disconnect()

    print("\n" + "=" * 60)

except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()