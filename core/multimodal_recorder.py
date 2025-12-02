"""
多模态同步录制系统 - 重构版
修复了GUI阻塞和实时显示问题
"""

import os
import time
import threading
import logging
from datetime import datetime
from collections import deque
import cv2
import sounddevice as sd
import numpy as np
import wave

# 兼容导入
try:
    from .shimmer_device import ShimmerGSRDevice
    from .lsl_manager import LSLStreamManager
    from .data_saver import DataSaver
    from .config import SHIMMER_CONFIG, LSL_CONFIG, DATA_SAVING_CONFIG
except ImportError:
    from shimmer_device import ShimmerGSRDevice
    from lsl_manager import LSLStreamManager
    from data_saver import DataSaver
    from config import SHIMMER_CONFIG, LSL_CONFIG, DATA_SAVING_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class MultimodalRecorder:
    """多模态同步录制器 - 重构版"""

    def __init__(self, config):
        """初始化多模态录制系统"""
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 状态标志
        self.is_ready = False
        self.is_recording = False

        # 线程锁（用于线程安全）
        self._lock = threading.Lock()

        # 模态就绪标志
        self.shimmer_ready = False
        self.video_ready = False
        self.audio_ready = False

        # 录制线程
        self._shimmer_thread = None
        self._video_thread = None
        self._audio_thread = None

        # 统计信息
        self.video_frame_count = 0

        # 共享数据（线程安全访问）
        self.current_video_frame = None
        self.audio_buffer = deque(maxlen=20000)  # 使用deque提高性能

        # 实时数据（固定大小缓冲区）
        max_buffer = 500  # 最多保留500个样本点
        self.realtime_data = {
            'gsr': deque(maxlen=max_buffer),
            'ppg': deque(maxlen=max_buffer),
            'hr': 0,
            'accel_x': deque(maxlen=max_buffer),
            'accel_y': deque(maxlen=max_buffer),
            'accel_z': deque(maxlen=max_buffer)
        }

        # 模态组件
        self.shimmer_device = None
        self.shimmer_lsl = None
        self.shimmer_saver = None

        self.video_cap = None
        self.video_writer = None

        self.audio_stream = None

        # 会话信息
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.data_dirs = self._create_data_directories()

    def _create_data_directories(self):
        """创建数据目录"""
        base_dir = self.config.get('output_directory', './data')

        dirs = {
            'shimmer': os.path.join(base_dir, 'shimmer'),
            'video': os.path.join(base_dir, 'video'),
            'audio': os.path.join(base_dir, 'audio'),
        }

        for dir_path in dirs.values():
            os.makedirs(dir_path, exist_ok=True)

        self.logger.info(f"数据目录已创建: {base_dir}")
        return dirs

    def initialize(self):
        """初始化所有模态"""
        self.logger.info("=" * 60)
        self.logger.info("多模态同步录制系统")
        self.logger.info("=" * 60)

        # 初始化Shimmer
        self.logger.info("\n[1/3] 初始化Shimmer GSR+...")
        if self._initialize_shimmer():
            self.shimmer_ready = True
            self.logger.info("✓ Shimmer就绪")
        else:
            self.logger.error("✗ Shimmer初始化失败")

        # 初始化视频
        self.logger.info("\n[2/3] 初始化视频采集...")
        if self._initialize_video():
            self.video_ready = True
            self.logger.info("✓ 视频就绪")
        else:
            self.logger.error("✗ 视频初始化失败")

        # 初始化音频
        self.logger.info("\n[3/3] 初始化音频采集...")
        if self._initialize_audio():
            self.audio_ready = True
            self.logger.info("✓ 音频就绪")
        else:
            self.logger.error("✗ 音频初始化失败")

        # 检查是否全部就绪
        self.is_ready = self.shimmer_ready and self.video_ready and self.audio_ready

        if self.is_ready:
            self.logger.info("\n✓ 所有模态已就绪!")
            self.logger.info("=" * 60 + "\n")
        else:
            self.logger.error("\n✗ 部分模态初始化失败,请检查")

        return self.is_ready

    def _initialize_shimmer(self):
        """初始化Shimmer设备"""
        try:
            # 创建设备
            self.shimmer_device = ShimmerGSRDevice(SHIMMER_CONFIG)

            # 连接设备
            if not self.shimmer_device.connect():
                return False

            # 创建LSL
            channel_names = self.shimmer_device.get_channel_names()
            sampling_rate = SHIMMER_CONFIG['sampling_rate']

            self.shimmer_lsl = LSLStreamManager(LSL_CONFIG, channel_names, sampling_rate)
            self.shimmer_lsl.create_outlet()

            # 创建数据保存器
            shimmer_config = {
                **DATA_SAVING_CONFIG,
                'output_directory': self.data_dirs['shimmer'],
                'device_id': SHIMMER_CONFIG.get('device_id', 'A5E0'),
            }
            self.shimmer_saver = DataSaver(shimmer_config, channel_names, sampling_rate)

            return True

        except Exception as e:
            self.logger.error(f"Shimmer初始化错误: {e}")
            return False

    def _initialize_video(self):
        """初始化视频采集"""
        try:
            camera_id = self.config.get('video_camera_id', 0)
            fps = self.config.get('video_fps', 30)
            width = self.config.get('video_width', 640)
            height = self.config.get('video_height', 480)

            self.video_cap = cv2.VideoCapture(camera_id)
            self.video_cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.video_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.video_cap.set(cv2.CAP_PROP_FPS, fps)

            if not self.video_cap.isOpened():
                self.logger.error("无法打开摄像头")
                return False

            # 测试读取一帧
            ret, frame = self.video_cap.read()
            if not ret:
                self.logger.error("无法读取视频帧")
                return False

            return True

        except Exception as e:
            self.logger.error(f"视频初始化错误: {e}")
            return False

    def _initialize_audio(self):
        """初始化音频采集"""
        try:
            # 检查音频设备
            devices = sd.query_devices()
            if len(devices) == 0:
                self.logger.error("未找到音频设备")
                return False

            self.logger.info(f"检测到音频设备: {devices[0]['name']}")
            return True

        except Exception as e:
            self.logger.error(f"音频初始化错误: {e}")
            return False

    def start_recording(self):
        """开始录制 - 非阻塞版本"""
        if not self.is_ready:
            self.logger.error("系统未就绪")
            return False

        if self.is_recording:
            self.logger.warning("已经在录制中")
            return False

        self.logger.info("=" * 60)
        self.logger.info("▶️ 开始数据采集...")

        with self._lock:
            self.is_recording = True
            self.video_frame_count = 0

        # 启动Shimmer录制（如果可用）
        if self.shimmer_ready and self.shimmer_device:
            self.shimmer_device.start_streaming()
            self._shimmer_thread = threading.Thread(
                target=self._shimmer_recording_loop,
                daemon=True,
                name="ShimmerRecording"
            )
            self._shimmer_thread.start()
            self.logger.info("✓ Shimmer录制线程已启动")

        # 启动视频录制（如果可用）
        if self.video_ready and self.video_cap:
            self._video_thread = threading.Thread(
                target=self._video_recording_loop,
                daemon=True,
                name="VideoRecording"
            )
            self._video_thread.start()
            self.logger.info("✓ 视频录制线程已启动")

        # 启动音频录制（如果可用）
        if self.audio_ready:
            self._audio_thread = threading.Thread(
                target=self._audio_recording_loop,
                daemon=True,
                name="AudioRecording"
            )
            self._audio_thread.start()
            self.logger.info("✓ 音频录制线程已启动")

        self.logger.info("=" * 60)
        return True

    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            self.logger.warning("当前未在录制")
            return

        self.logger.info("=" * 60)
        self.logger.info("⏹️ 停止数据采集...")

        with self._lock:
            self.is_recording = False

        # 等待所有线程结束
        threads = [self._shimmer_thread, self._video_thread, self._audio_thread]
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=2)

        # 停止Shimmer
        if self.shimmer_device:
            self.shimmer_device.stop_streaming()
            if hasattr(self.shimmer_saver, '_flush_buffer'):
                self.shimmer_saver._flush_buffer()

        # 保存视频
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

        # 保存音频
        self._save_audio()

        self.logger.info("✓ 录制已停止")
        self.logger.info(f"数据已保存到: {self.config.get('output_directory', './data')}")
        self.logger.info("=" * 60)

        # 生成新的会话ID
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _shimmer_recording_loop(self):
        """Shimmer录制循环 - 线程安全版本"""
        self.logger.info("Shimmer录制线程运行中...")

        while True:
            # 检查录制状态（线程安全）
            with self._lock:
                if not self.is_recording:
                    break

            # 读取数据
            has_data, packet = self.shimmer_device.read_data()

            if has_data and packet:
                sample, timestamp = self.shimmer_device.extract_sample_from_packet(packet)

                if sample:
                    # 推送到LSL
                    if self.shimmer_lsl:
                        self.shimmer_lsl.push_sample(sample, timestamp)

                    # 保存数据
                    self.shimmer_saver.add_sample(sample, timestamp)

                    # 更新实时数据（线程安全）
                    try:
                        if len(sample) > 0:
                            self.realtime_data['gsr'].append(sample[0])
                        if len(sample) > 2:
                            self.realtime_data['ppg'].append(sample[2])
                        if len(sample) > 5:
                            self.realtime_data['accel_x'].append(sample[3])
                            self.realtime_data['accel_y'].append(sample[4])
                            self.realtime_data['accel_z'].append(sample[5])
                        if len(sample) >= 20 and sample[19] > 0:
                            self.realtime_data['hr'] = sample[19]
                    except Exception as e:
                        self.logger.error(f"更新realtime_data失败: {e}")

            time.sleep(0.001)

        self.logger.info("Shimmer录制线程已退出")

    def _video_recording_loop(self):
        """视频录制循环 - 线程安全版本"""
        self.logger.info("视频录制线程运行中...")

        fps = self.config.get('video_fps', 30)
        width = self.config.get('video_width', 640)
        height = self.config.get('video_height', 480)

        # 创建视频写入器
        output_path = os.path.join(
            self.data_dirs['video'],
            f'video_{self.session_id}.mp4'
        )

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        local_frame_count = 0

        while True:
            # 检查录制状态（线程安全）
            with self._lock:
                if not self.is_recording:
                    break

            ret, frame = self.video_cap.read()
            if not ret:
                self.logger.warning("读取视频帧失败")
                break

            # 写入视频
            self.video_writer.write(frame)

            # 更新共享帧（线程安全）
            with self._lock:
                self.current_video_frame = frame.copy()
                self.video_frame_count = local_frame_count

            local_frame_count += 1

            # 控制帧率
            time.sleep(0.01)

        self.logger.info(f"视频录制完成: {local_frame_count} 帧")

    def _audio_recording_loop(self):
        """音频录制循环"""
        self.logger.info("音频录制线程运行中...")

        sample_rate = self.config.get('audio_sample_rate', 44100)
        channels = self.config.get('audio_channels', 1)

        # 清空缓冲区
        self.audio_buffer.clear()

        def audio_callback(indata, frames, time_info, status):
            with self._lock:
                if self.is_recording:
                    # 直接扩展到deque（自动限制大小）
                    self.audio_buffer.extend(indata.flatten().tolist())

        with sd.InputStream(
                samplerate=sample_rate,
                channels=channels,
                callback=audio_callback
        ):
            while True:
                with self._lock:
                    if not self.is_recording:
                        break
                time.sleep(0.1)

        self.logger.info("音频录制线程已退出")

    def _save_audio(self):
        """保存音频文件"""
        if len(self.audio_buffer) == 0:
            return

        try:
            output_path = os.path.join(
                self.data_dirs['audio'],
                f'audio_{self.session_id}.wav'
            )

            sample_rate = self.config.get('audio_sample_rate', 44100)
            channels = self.config.get('audio_channels', 1)

            # 转换为numpy数组
            audio_data = np.array(list(self.audio_buffer), dtype=np.float32)
            audio_data = np.int16(audio_data * 32767)

            with wave.open(output_path, 'w') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data.tobytes())

            self.logger.info(f"音频已保存: {len(self.audio_buffer)} 样本")

        except Exception as e:
            self.logger.error(f"保存音频失败: {e}")

    def cleanup(self):
        """清理资源"""
        self.logger.info("清理资源...")

        # 停止录制（如果正在录制）
        if self.is_recording:
            self.stop_recording()

        # 断开设备
        if self.shimmer_device:
            self.shimmer_device.disconnect()

        if self.video_cap:
            self.video_cap.release()

        cv2.destroyAllWindows()

        self.logger.info("系统已清理")


# 独立测试
if __name__ == "__main__":
    config = {
        'output_directory': './data',
        'video_camera_id': 0,
        'video_fps': 30,
        'video_width': 640,
        'video_height': 480,
        'audio_sample_rate': 44100,
        'audio_channels': 1,
    }

    recorder = MultimodalRecorder(config)

    if recorder.initialize():
        print("\n按Enter键开始录制...")
        input()

        recorder.start_recording()

        print("录制中... 按Enter键停止")
        input()

        recorder.stop_recording()
        recorder.cleanup()
    else:
        print("初始化失败")