"""
HEEG连接诊断脚本
放在项目根目录运行，检查为什么GUI程序无法连接HEEG
"""

import sys
from pathlib import Path

print("=" * 70)
print("HEEG 连接诊断")
print("=" * 70)
print()

# 1. 检查项目结构
print("1. 检查项目结构...")
project_root = Path(__file__).parent
core_path = project_root / 'core'
gui_path = project_root / 'gui'

print(f"   项目根目录: {project_root}")
print(f"   Core目录存在: {core_path.exists()}")
print(f"   GUI目录存在: {gui_path.exists()}")

if core_path.exists():
    core_files = list(core_path.glob('*.py'))
    print(f"   Core目录文件: {len(core_files)}个")
    for f in core_files:
        print(f"     - {f.name}")

    # 检查关键文件
    heeg_file = core_path / 'neuracle_heeg_device.py'
    config_file = core_path / 'config.py'
    print(f"   neuracle_heeg_device.py: {'✓' if heeg_file.exists() else '✗'}")
    print(f"   config.py: {'✓' if config_file.exists() else '✗'}")
print()

# 2. 尝试导入Core模块
print("2. 尝试导入Core模块...")
sys.path.insert(0, str(core_path))

try:
    import config as core_config

    print("   ✓ config导入成功")

    # 检查HEEG配置
    if hasattr(core_config, 'HEEG_CONFIG'):
        heeg_config = core_config.HEEG_CONFIG
        print(f"   ✓ HEEG配置存在")
        print(f"     - hostname: {heeg_config.get('hostname')}")
        print(f"     - port: {heeg_config.get('port')}")
    else:
        print("   ✗ HEEG_CONFIG不存在")
except ImportError as e:
    print(f"   ✗ config导入失败: {e}")
print()

# 3. 尝试导入HEEG驱动
print("3. 尝试导入HEEG驱动...")
try:
    from neuracle_heeg_device import NeuracleHEEGDevice

    print("   ✓ NeuracleHEEGDevice导入成功")
    print(f"   类路径: {NeuracleHEEGDevice.__module__}")
except ImportError as e:
    print(f"   ✗ NeuracleHEEGDevice导入失败: {e}")
    import traceback

    traceback.print_exc()
print()

# 4. 尝试连接HEEG
print("4. 尝试连接HEEG设备...")
print("   (需要NSH-R软件正在运行并采集数据)")
print()

try:
    from core.neuracle_heeg_device import NeuracleHEEGDevice
    import config as core_config

    heeg_config = core_config.HEEG_CONFIG
    device = NeuracleHEEGDevice(
        hostname=heeg_config['hostname'],
        port=heeg_config['port']
    )

    print(f"   → 连接到 {heeg_config['hostname']}:{heeg_config['port']}...")

    if device.connect(max_retries=2):
        print("   ✓ TCP连接成功")

        # 等待设备就绪
        import time

        print("   → 等待设备就绪...")

        for i in range(5):
            info = device.get_device_info()
            print(
                f"     [{i + 1}s] 状态: {info['state']}, 通道: {info['channel_count']}, 采样率: {info['sample_rate']}")

            if info['state'] in ['READY', 'RUNNING']:
                print("   ✓ 设备就绪！")
                break

            time.sleep(1)
        else:
            print("   ✗ 5秒后设备仍未就绪")
            print("     可能原因: NSH-R未开始采集或数据发送未启用")

        device.disconnect()
    else:
        print("   ✗ TCP连接失败")
        print("     请检查:")
        print("     1. NSH-R软件是否运行")
        print("     2. 运行 netstat -ano | findstr 8172")

except Exception as e:
    print(f"   ✗ 连接测试失败: {e}")
    import traceback

    traceback.print_exc()

print()
print("=" * 70)
print("诊断完成")
print("=" * 70)