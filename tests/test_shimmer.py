"""
Shimmer 数据采集 - 最终正确版本
"""

import sys
import time
import csv
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 60)
print("Shimmer GSR 数据采集 - 最终版")
print("=" * 60)

try:
    import devices.config as core_config
    from devices.shimmer_gsr import ShimmerGSRDevice

    # 创建设备
    shimmer = ShimmerGSRDevice(core_config.SHIMMER_CONFIG)

    # 连接
    com_ports = shimmer._list_com_ports()
    if not com_ports or not shimmer.connect(com_ports[0]):
        print("✗ 连接失败")
        sys.exit(1)

    print(f"✓ 已连接到 {com_ports[0]}")

    # 获取通道信息
    info = shimmer.get_device_info()
    channel_names = info.get('channel_names', [])

    print(f"\n通道列表 ({len(channel_names)} 个):")
    for i, name in enumerate(channel_names):
        print(f"  [{i}] {name}")

    # 启动数据流
    if not shimmer.start_streaming():
        print("✗ 启动失败")
        shimmer.disconnect()
        sys.exit(1)

    print("\n✓ 数据流已启动")

    # 创建 CSV
    csv_file = open('./test_shimmer_data.csv', 'w', newline='', encoding='utf-8')
    csv_writer = csv.writer(csv_file)

    headers = ['Timestamp'] + channel_names
    csv_writer.writerow(headers)

    print("\n开始采集 500 个数据包...")
    print("=" * 60)

    packet_count = 0
    max_packets = 500

    while packet_count < max_packets:
        try:
            success, data = shimmer.read_data()

            if not success or not data:
                time.sleep(0.001)
                continue

            timestamp = time.time()

            # ========== 正确解包 extract_sample_from_packet ==========
            try:
                result = shimmer.extract_sample_from_packet(data)

                # extract_sample_from_packet 返回 (sample, packet_timestamp)
                if isinstance(result, tuple) and len(result) == 2:
                    sample, packet_timestamp = result
                else:
                    sample = result

                # 第一个数据包：显示详细信息
                if packet_count == 0:
                    print(f"\n[第1个数据包]")
                    print(f"  返回类型: {type(result)}")
                    print(f"  sample 类型: {type(sample)}")
                    print(f"  sample 长度: {len(sample)}")
                    print(f"\n  校准数据:")
                    for i, value in enumerate(sample):
                        ch_name = channel_names[i] if i < len(channel_names) else f"未知_{i}"
                        print(f"    [{i}] {ch_name:30s} = {value}")
                    print("=" * 60)

                # 构建数据行
                row = [timestamp] + list(sample)

            except Exception as e:
                print(f"\n✗ 提取样本失败: {e}")
                import traceback
                traceback.print_exc()
                row = [timestamp] + [0] * len(channel_names)
            # =========================================================

            # 写入 CSV
            csv_writer.writerow(row)

            packet_count += 1

            if packet_count % 50 == 0:
                csv_file.flush()
                print(f"[进度] {packet_count} / {max_packets} 包")

                # 显示最新数据
                if isinstance(sample, (list, tuple)) and len(sample) >= 2:
                    gsr_cond = sample[0]
                    gsr_res = sample[1]
                    print(f"  最新: GSR_Cond={gsr_cond:.6f}, GSR_Res={gsr_res:.2f}")

            time.sleep(0.001)

        except KeyboardInterrupt:
            print("\n用户中断")
            break

        except Exception as e:
            print(f"\n采集错误: {e}")
            import traceback
            traceback.print_exc()
            break

    # 停止
    shimmer.stop_streaming()
    csv_file.close()
    shimmer.disconnect()

    print("\n" + "=" * 60)
    print(f"✓ 测试完成！ 总采集: {packet_count} 包")
    print(f"  数据文件: ./test_shimmer_data.csv")

    # 显示数据预览
    print("\n数据预览 (前5行):")
    with open('./test_shimmer_data.csv', 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i < 6:
                parts = line.strip().split(',')
                if i == 0:
                    # 表头
                    print(f"  {parts[0]:<20s} {parts[1]:<20s} {parts[2]:<20s} {parts[3]:<15s}")
                else:
                    # 数据行
                    try:
                        ts = parts[0]
                        v1 = parts[1] if len(parts) > 1 else '0'
                        v2 = parts[2] if len(parts) > 2 else '0'
                        v3 = parts[3] if len(parts) > 3 else '0'
                        print(f"  {ts:<20s} {v1:<20s} {v2:<20s} {v3:<15s}")
                    except:
                        print(f"  {line.strip()}")

    print("=" * 60)

except Exception as e:
    print(f"\n✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()