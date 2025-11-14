"""
多模态同步录制系统
统一控制Shimmer GSR+、视频、音频的同步采集
"""

"""
多模态同步录制系统
统一控制Shimmer GSR+、视频、音频的同步采集
"""

"""
多模态同步录制系统
统一控制Shimmer GSR+、视频、音频的同步采集
"""

import os
import time
import threading
import logging
from datetime import datetime
from pynput import keyboard
import cv2
import sounddevice as sd
import numpy as np
import wave

# 兼容导入：同时支持相对导入和绝对导入
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

# 可视化（可选）
try:
    try:
        from .realtime_visualizer import RealtimeVisualizer
    except ImportError:
        from realtime_visualizer import RealtimeVisualizer
    VISUALIZER_AVAILABLE = True
except ImportError:
    VISUALIZER_AVAILABLE = False
    print("注意: 实时可视化功能已禁用")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MultimodalRecorder:
    """多模态同步录制器"""

    def __init__(self, config):
        """
        初始化多模态录制系统

        Args:
            config: 配置字典
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 状态标志
        self.is_ready = False
        self.is_recording = False
        self.should_stop = False

        # 模态就绪标志
        self.shimmer_ready = False
        self.video_ready = False
        self.audio_ready = False
        self.video_frame_count = 0
        self.current_video_frame = None  # 共享当前视频帧

        self.realtime_data = {  # 共享实时数据
            'gsr': [],
            'ppg': [],
            'hr': 0,
            'accel_x': [],
            'accel_y': [],
            'accel_z': []
        }

        # 模态组件
        self.shimmer_device = None
        self.shimmer_lsl = None
        self.shimmer_saver = None

        self.video_cap = None
        self.video_writer = None

        self.audio_stream = None
        self.audio_buffer = []

        # 会话信息
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.data_dirs = self._create_data_directories()

        # 键盘监听
        self.keyboard_listener = None
        # 可视化器
        self.visualizer = None

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

        # 初始化可视化 (在独立线程中运行)
        # 初始化可视化 - 暂时禁用独立线程模式
        if self.is_ready:
            self.logger.info("\n[4/4] 数据共享模式已启用")
            self.logger.info("✓ 实时数据将通过GUI显示")

            time.sleep(1)  # 等待窗口创建
            self.logger.info("✓ 可视化就绪")
            self.logger.info("✓ 所有模态已就绪!")
            self.logger.info("按 [空格键] 开始录制")
            self.logger.info("再次按 [空格键] 停止录制")
            self.logger.info("按 [ESC] 或 [Ctrl+C] 退出系统")
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
                'device_id': SHIMMER_CONFIG.get('device_id', 'A5E0'),  # 添加device_id
            }
            self.shimmer_saver = DataSaver(shimmer_config, channel_names, sampling_rate)

            # 强制创建CSV文件
            if hasattr(self.shimmer_saver, '_create_csv_file'):
                self.shimmer_saver._create_csv_file()

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
        """开始录制"""
        print("=" * 60)  # ← 添加
        print("DEBUG: start_recording 被调用")  # ← 添加
        print(f"DEBUG: self.is_ready = {self.is_ready}")  # ← 添加
        print(f"DEBUG: self.is_recording = {self.is_recording}")  # ← 添加
        print(f"DEBUG: shimmer_ready = {self.shimmer_ready}")  # ← 添加
        print(f"DEBUG: video_ready = {self.video_ready}")  # ← 添加
        print(f"DEBUG: audio_ready = {self.audio_ready}")  # ← 添加
        print("=" * 60)  # ← 添加

        if not self.is_ready:
            self.logger.warning("系统未就绪,无法开始录制")
            print("DEBUG: 系统未就绪，退出")  # ← 添加
            return

        if self.is_recording:
            self.logger.warning("已在录制中")
            print("DEBUG: 已在录制中，退出")  # ← 添加
            return

        self.logger.info("\n" + "=" * 60)
        self.logger.info(f"开始录制 - 会话ID: {self.session_id}")
        self.logger.info("=" * 60)

        self.is_recording = True
        print("DEBUG: 设置 is_recording = True")  # ← 添加

        # 启动Shimmer
        if self.shimmer_ready:
            print("DEBUG: 准备启动 Shimmer 线程")  # ← 添加
            self.shimmer_device.start_streaming()
            threading.Thread(target=self._shimmer_recording_loop, daemon=True).start()
            print("DEBUG: Shimmer 线程已启动")  # ← 添加

        # 启动视频
        if self.video_ready:
            print("DEBUG: 准备启动 Video 线程")  # ← 添加
            threading.Thread(target=self._video_recording_loop, daemon=True).start()
            print("DEBUG: Video 线程已启动")  # ← 添加

        # 启动音频
        if self.audio_ready:
            print("DEBUG: 准备启动 Audio 线程")  # ← 添加
            threading.Thread(target=self._audio_recording_loop, daemon=True).start()
            print("DEBUG: Audio 线程已启动")  # ← 添加

        self.logger.info("✓ 所有模态已开始录制")
        print("DEBUG: start_recording 完成")  # ← 添加

    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            return

        self.logger.info("\n停止录制中...")
        self.is_recording = False

        # 等待线程结束
        time.sleep(0.5)

        # 停止Shimmer
        if self.shimmer_ready:
            self.shimmer_device.stop_streaming()
         #   self.shimmer_saver.stop()
            if hasattr(self.shimmer_saver, '_flush_buffer'):
                self.shimmer_saver._flush_buffer()
        # 保存视频

        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

        # 保存音频
        self._save_audio()

        self.logger.info("=" * 60)
        self.logger.info("✓ 录制已停止")
        self.logger.info(f"数据已保存到: {self.config.get('output_directory', './data')}")
        self.logger.info("=" * 60)
        self.logger.info("\n按 [空格键] 开始新的录制")
        self.logger.info("按 [ESC] 或 [Ctrl+C] 退出系统\n")

        # 生成新的会话ID
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _shimmer_recording_loop(self):
        """Shimmer录制循环"""
        print("DEBUG Shimmer: 录制循环已启动")  # ← 添加

        while self.is_recording:
            has_data, packet = self.shimmer_device.read_data()

            if has_data and packet:
                sample, timestamp = self.shimmer_device.extract_sample_from_packet(packet)

                if sample:
                    print(f"DEBUG Shimmer: 收到样本，长度: {len(sample)}")  # ← 添加

                    # 推送到LSL
                    if self.shimmer_lsl and hasattr(self.shimmer_lsl, 'outlet') and self.shimmer_lsl.outlet:
                        self.shimmer_lsl.push_sample(sample, timestamp)

                    # 保存数据
                    self.shimmer_saver.add_sample(sample, timestamp)

                    # ← 修改：不管长度如何，都尝试更新
                    try:
                        max_len = 500

                        # GSR (索引0) - 添加安全检查
                        if len(sample) > 0:
                            self.realtime_data['gsr'].append(sample[0])
                            if len(self.realtime_data['gsr']) > max_len:
                                self.realtime_data['gsr'].pop(0)
                            print(f"DEBUG Shimmer: GSR已更新，当前长度: {len(self.realtime_data['gsr'])}")  # ← 添加

                        # PPG (索引2)
                        if len(sample) > 2:
                            self.realtime_data['ppg'].append(sample[2])
                            if len(self.realtime_data['ppg']) > max_len:
                                self.realtime_data['ppg'].pop(0)

                        # 加速度计 (索引3,4,5)
                        if len(sample) > 5:
                            self.realtime_data['accel_x'].append(sample[3])
                            if len(self.realtime_data['accel_x']) > max_len:
                                self.realtime_data['accel_x'].pop(0)

                            self.realtime_data['accel_y'].append(sample[4])
                            if len(self.realtime_data['accel_y']) > max_len:
                                self.realtime_data['accel_y'].pop(0)

                            self.realtime_data['accel_z'].append(sample[5])
                            if len(self.realtime_data['accel_z']) > max_len:
                                self.realtime_data['accel_z'].pop(0)

                        # 心率 (索引19 - PPGtoHR)
                        if len(sample) >= 20 and sample[19] > 0:
                            self.realtime_data['hr'] = sample[19]

                    except Exception as e:
                        print(f"DEBUG Shimmer: 更新realtime_data失败: {e}")  # ← 添加
                        import traceback
                        traceback.print_exc()

                    # 更新可视化（如果存在）
                    if self.visualizer:
                        self.visualizer.add_sample(sample, timestamp)

            time.sleep(0.001)

        print("DEBUG Shimmer: 录制循环已结束")  # ← 添加

    def _video_recording_loop(self):
        """视频录制循环"""
        print("DEBUG Video Loop: 录制循环已启动")  # ← 添加

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

        self.video_frame_count = 0

        print(f"DEBUG Video Loop: 开始读取帧，摄像头状态: {self.video_cap.isOpened()}")  # ← 添加

        while self.is_recording:
            ret, frame = self.video_cap.read()
            if not ret:
                print("DEBUG Video Loop: 读取帧失败")  # ← 添加
                break

            # 写入视频
            self.video_writer.write(frame)

            # 保存当前帧供GUI使用
            self.current_video_frame = frame.copy()

            if self.video_frame_count % 30 == 0:  # 每30帧打印一次
                print(f"DEBUG Video Loop: 已录制 {self.video_frame_count} 帧")  # ← 添加

            self.video_frame_count += 1

            # 添加短暂延迟，避免占用过多CPU
            time.sleep(0.01)

        self.logger.info(f"视频录制完成: {self.video_frame_count} 帧")
        print("DEBUG Video Loop: 录制循环已结束")  # ← 添加

    def _audio_recording_loop(self):
        """音频录制循环"""
        sample_rate = self.config.get('audio_sample_rate', 44100)
        channels = self.config.get('audio_channels', 1)

        self.audio_buffer = []

        def audio_callback(indata, frames, time_info, status):
            if self.is_recording:
                self.audio_buffer.extend(indata.flatten().tolist())

        with sd.InputStream(
                samplerate=sample_rate,
                channels=channels,
                callback=audio_callback
        ):
            while self.is_recording:
                time.sleep(0.1)

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

            audio_data = np.array(self.audio_buffer, dtype=np.float32)
            audio_data = np.int16(audio_data * 32767)

            with wave.open(output_path, 'w') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data.tobytes())

            self.logger.info(f"音频已保存: {len(self.audio_buffer)} 样本")

        except Exception as e:
            self.logger.error(f"保存音频失败: {e}")

    def _on_key_press(self, key):
        """键盘按键处理"""
        try:
            if key == keyboard.Key.space:
                if not self.is_recording:
                    self.start_recording()
                else:
                    self.stop_recording()

            elif key == keyboard.Key.esc:
                self.logger.info("\n退出系统...")
                self.should_stop = True
                return False  # 停止监听

        except Exception as e:
            self.logger.error(f"按键处理错误: {e}")

    def run(self):
        """运行系统"""
        if not self.initialize():
            self.logger.error("初始化失败,退出")
            return

        # 启动键盘监听
        self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        self.keyboard_listener.start()

        try:
            # 主循环
            while not self.should_stop:
                time.sleep(0.1)

        except KeyboardInterrupt:
            self.logger.info("\n收到中断信号...")

        finally:
            # 清理
            if self.is_recording:
                self.stop_recording()

            self.cleanup()

    def cleanup(self):
        """清理资源"""
        self.logger.info("清理资源...")

        if self.shimmer_device:
            self.shimmer_device.disconnect()

        if self.video_cap:
            self.video_cap.release()

        cv2.destroyAllWindows()

        if self.keyboard_listener:
            self.keyboard_listener.stop()

        self.logger.info("系统已退出")


if __name__ == "__main__":
    # 配置
    config = {
        'output_directory': './data',

        # 视频配置
        'video_camera_id': 0,
        'video_fps': 30,
        'video_width': 640,
        'video_height': 480,

        # 音频配置
        'audio_sample_rate': 44100,
        'audio_channels': 1,
    }

    # 创建并运行录制器
    recorder = MultimodalRecorder(config)
    recorder.run()