#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测网络中的LSL流
Neuracle设备可能通过LSL输出数据
"""

try:
    from pylsl import resolve_streams, StreamInlet
    import time

    print("=" * 60)
    print("LSL流检测工具")
    print("=" * 60)
    print("\n正在搜索网络中的LSL流...")
    print("(搜索10秒，请等待...)\n")

    # 搜索所有LSL流
    streams = resolve_streams(wait_time=10.0)

    if len(streams) == 0:
        print("❌ 未找到任何LSL流")
        print("\n可能原因:")
        print("  1. NSH-R软件未启用LSL输出")
        print("  2. 设备不支持LSL")
        print("  3. 需要在软件中手动启用")
    else:
        print(f"✅ 找到 {len(streams)} 个LSL流:\n")

        for i, stream in enumerate(streams):
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"流 #{i + 1}")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"  名称: {stream.name()}")
            print(f"  类型: {stream.type()}")
            print(f"  通道数: {stream.channel_count()}")
            print(f"  采样率: {stream.nominal_srate()} Hz")
            print(f"  来源: {stream.source_id()}")
            print(f"  主机: {stream.hostname()}")

            # 如果是EEG流，尝试接收数据
            if stream.type().lower() == 'eeg':
                print(f"\n  🧪 这是EEG流！尝试接收数据...")
                try:
                    inlet = StreamInlet(stream, max_buflen=1)
                    sample, timestamp = inlet.pull_sample(timeout=5.0)

                    if sample:
                        print(f"  ✅ 成功接收到数据!")
                        print(f"     样本长度: {len(sample)}")
                        print(f"     时间戳: {timestamp:.3f}")
                        print(f"     前5个通道值: {sample[:5]}")
                    else:
                        print(f"  ⚠️  连接成功但5秒内未收到数据")

                except Exception as e:
                    print(f"  ❌ 接收数据失败: {e}")

        print(f"\n{'━' * 60}")
        print("\n💡 如果找到了EEG流，你可以直接使用LSL接收数据！")
        print("   这比TCP更简单、更标准！")

except ImportError:
    print("❌ 未安装pylsl库")
    print("\n请安装:")
    print("  pip install pylsl")
except Exception as e:
    print(f"❌ 错误: {e}")

print("\n" + "=" * 60)