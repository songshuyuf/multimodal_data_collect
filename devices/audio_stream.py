"""
音频采集LSL流
使用麦克风采集音频并通过LSL推送
"""

import sounddevice as sd
import numpy as np
import time
from pylsl import StreamInfo, StreamOutlet, local_clock
import logging
import wave

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class AudioLSLStream:
    """音频LSL流"""

    def __init__(self, sample_rate=44100, channels=1, chunk_size=1024):
        """
        初始化音频流

        Args:
            sample_rate: 采样率 (Hz)
            channels: 通道数 (1=单声道, 2=立体声)
            chunk_size: 每次读取的样本数
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.outlet = None
        self.is_streaming = False
        self.audio_buffer = []

    def start(self):
        """启动音频采集和LSL流"""
        # 创建LSL流
        info = StreamInfo(
            name='AudioStream',
            type='Audio',
            channel_count=self.channels,
            nominal_srate=self.sample_rate,
            channel_format='float32',
            source_id='microphone_001'
        )

        # 添加元数据
        desc = info.desc()
        desc.append_child_value("sample_rate", str(self.sample_rate))
        desc.append_child_value("channels", str(self.channels))

        self.outlet = StreamOutlet(info, chunk_size=self.chunk_size)
        self.is_streaming = True

        logging.info(f"音频LSL流已启动: {self.sample_rate}Hz, {self.channels}通道")
        return True

    def audio_callback(self, indata, frames, time_info, status):
        """音频回调函数"""
        if status:
            logging.warning(f"音频状态: {status}")

        if self.is_streaming:
            # 推送到LSL
            timestamp = local_clock()

            # 转换数据格式
            audio_data = indata.flatten().tolist()

            # 推送音频块
            self.outlet.push_chunk(indata.tolist(), timestamp)

            # 保存到缓冲区(用于保存文件)
            self.audio_buffer.extend(audio_data)

    def run(self, duration=None, save_audio=False, output_path="audio_output.wav"):
        """
        运行音频采集

        Args:
            duration: 持续时间(秒),None=无限
            save_audio: 是否保存音频文件
            output_path: 音频保存路径
        """
        if not self.is_streaming:
            logging.error("请先调用start()启动流")
            return

        start_time = time.time()

        try:
            with sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    callback=self.audio_callback,
                    blocksize=self.chunk_size
            ):
                logging.info("音频采集中... 按Ctrl+C停止")

                if duration:
                    time.sleep(duration)
                else:
                    while self.is_streaming:
                        time.sleep(0.1)

        except KeyboardInterrupt:
            logging.info("用户中断")

        finally:
            # 保存音频文件
            if save_audio and len(self.audio_buffer) > 0:
                self._save_audio(output_path)

            logging.info("音频采集完成")

    def _save_audio(self, output_path):
        """保存音频到WAV文件"""
        try:
            audio_data = np.array(self.audio_buffer, dtype=np.float32)

            # 归一化到16位整数
            audio_data = np.int16(audio_data * 32767)

            with wave.open(output_path, 'w') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())

            logging.info(f"音频已保存到: {output_path}")
        except Exception as e:
            logging.error(f"保存音频失败: {e}")

    def stop(self):
        """停止采集"""
        self.is_streaming = False
        logging.info("音频流已停止")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='音频LSL流采集')
    parser.add_argument('--rate', type=int, default=44100, help='采样率')
    parser.add_argument('--channels', type=int, default=1, help='通道数')
    parser.add_argument('--duration', type=float, default=None, help='持续时间(秒)')
    parser.add_argument('--save', action='store_true', help='保存音频文件')
    parser.add_argument('--output', type=str, default='audio_output.wav', help='输出文件名')

    args = parser.parse_args()

    audio_stream = AudioLSLStream(
        sample_rate=args.rate,
        channels=args.channels
    )

    if audio_stream.start():
        audio_stream.run(
            duration=args.duration,
            save_audio=args.save,
            output_path=args.output
        )
        audio_stream.stop()