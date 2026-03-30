"""
音频采集测试脚本
测试麦克风是否能正常录音
"""

import sys
import time
import wave
import numpy as np
from pathlib import Path

# 添加路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("音频采集测试")
print("=" * 60)

try:
    import pyaudio

    # 音频参数
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    RECORD_SECONDS = 10

    print("\n1. 初始化 PyAudio...")
    p = pyaudio.PyAudio()

    # 列出所有音频设备
    print("\n2. 可用音频设备:")
    print("-" * 60)
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"\n设备 {i}: {info['name']}")
        print(f"  输入通道: {info['maxInputChannels']}")
        print(f"  输出通道: {info['maxOutputChannels']}")
        print(f"  默认采样率: {info['defaultSampleRate']}")

        # 标记默认设备
        if i == p.get_default_input_device_info()['index']:
            print(f"  >>> 默认输入设备 <<<")
        if i == p.get_default_output_device_info()['index']:
            print(f"  >>> 默认输出设备 <<<")

    print("\n" + "=" * 60)

    # 获取默认输入设备
    default_input = p.get_default_input_device_info()
    device_index = default_input['index']
    device_name = default_input['name']

    print(f"\n3. 使用设备: [{device_index}] {device_name}")
    print(f"   采样率: {RATE} Hz")
    print(f"   通道数: {CHANNELS}")
    print(f"   格式: 16-bit PCM")

    # 打开音频流
    print(f"\n4. 打开音频流...")
    try:
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK
        )
        print("✓ 音频流已打开")
    except Exception as e:
        print(f"✗ 打开音频流失败: {e}")
        p.terminate()
        sys.exit(1)

    # 录制音频
    print(f"\n5. 开始录制 {RECORD_SECONDS} 秒...")
    print("   请对着麦克风说话或制造声音！")
    print("=" * 60)

    frames = []
    max_amplitude = 0
    min_amplitude = 32767

    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)

            # 分析音频数据
            audio_data = np.frombuffer(data, dtype=np.int16)
            current_max = np.max(np.abs(audio_data))
            current_min = np.min(audio_data)

            max_amplitude = max(max_amplitude, current_max)
            min_amplitude = min(min_amplitude, current_min)

            # 每秒显示一次进度
            if i % (RATE // CHUNK) == 0:
                seconds = i // (RATE // CHUNK)

                # 计算 dB
                if current_max > 0:
                    db = 20 * np.log10(current_max / 32767.0)
                else:
                    db = -120

                # 显示音量条
                volume_bar = "█" * int((current_max / 32767.0) * 50)
                print(f"  [{seconds:2d}s] 音量: {db:6.1f} dB  {volume_bar}")

        except Exception as e:
            print(f"\n✗ 读取音频数据失败: {e}")
            break

    print("=" * 60)
    print("✓ 录制完成")

    # 停止录制
    stream.stop_stream()
    stream.close()
    p.terminate()

    # 分析结果
    print(f"\n6. 音频分析:")
    print(f"  最大振幅: {max_amplitude} / 32767")
    print(f"  最小振幅: {min_amplitude}")

    if max_amplitude > 0:
        max_db = 20 * np.log10(max_amplitude / 32767.0)
        print(f"  最大音量: {max_db:.1f} dB")
    else:
        print(f"  最大音量: -∞ dB (无声音)")

    # 判断录音是否成功
    print(f"\n7. 录音质量判断:")
    if max_amplitude < 100:
        print("  ✗ 几乎无声音 (振幅 < 100)")
        print("  可能原因:")
        print("    - 麦克风未连接或已禁用")
        print("    - 麦克风音量设置过低")
        print("    - 选错了输入设备")
        print("    - 麦克风权限未授予")
    elif max_amplitude < 1000:
        print("  ⚠ 声音太小 (振幅 < 1000)")
        print("  建议提高麦克风音量")
    else:
        print("  ✓ 录音正常")

    # 保存 WAV 文件
    print(f"\n8. 保存音频文件...")
    wav_file = './test_audio.wav'

    wf = wave.open(wav_file, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    print(f"✓ 已保存: {wav_file}")
    print(f"  文件大小: {len(b''.join(frames))} 字节")

    # 提示播放
    print(f"\n9. 测试播放:")
    print(f"  可以用播放器打开 {wav_file} 检查录音效果")
    print(f"  命令: start {wav_file}  (Windows)")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

except ImportError as e:
    print(f"\n✗ 导入失败: {e}")
    print("  请确保已安装 pyaudio:")
    print("  pip install pyaudio")

except Exception as e:
    print(f"\n✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()