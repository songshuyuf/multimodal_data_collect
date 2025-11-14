"""
设备控制器
封装core/模块，为GUI提供统一的设备控制接口
"""

"""
设备控制器
封装core/模块，为GUI提供统一的设备控制接口
"""

"""
设备控制器
封装core/模块，为GUI提供统一的设备控制接口
"""

import os
import sys
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Callable
from datetime import datetime

# 添加core目录到Python路径
CORE_AVAILABLE = False
try:
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    core_path = project_root / 'core'

    # 添加core目录到sys.path
    if str(core_path) not in sys.path:
        sys.path.insert(0, str(core_path))

    # 现在可以直接导入core下的模块了
    import multimodal_recorder
    import config as core_config

    CORE_AVAILABLE = True
    print("✓ Core模块加载成功")

except Exception as e:
    CORE_AVAILABLE = False
    print(f"⚠ Core模块不可用: {e}")
    print("→ 将使用模拟模式运行")


class DeviceController:
    """设备控制器 - 管理所有采集设备"""

    def __init__(self, session_paths: Dict[str, str]):
        """
        初始化设备控制器

        Args:
            session_paths: 会话数据路径字典 {'shimmer': path, 'video': path, 'audio': path}
        """
        self.logger = logging.getLogger(__name__)
        self.session_paths = session_paths

        # 设备状态
        self.devices_initialized = False
        self.is_recording = False

        # 设备连接状态
        self.shimmer_connected = False
        self.video_connected = False
        self.audio_connected = False

        # 多模态录制器（如果core可用）
        self.recorder = None

        # 状态回调
        self.status_callback: Optional[Callable] = None

        # 采集线程
        self.recording_thread = None
        self.start_time = None

    def set_status_callback(self, callback: Callable):
        """设置状态更新回调函数"""
        self.status_callback = callback

    def _update_status(self, message: str):
        """更新状态"""
        if self.status_callback:
            self.status_callback(message)
        self.logger.info(message)

    def initialize_shimmer(self) -> bool:
        """初始化Shimmer设备"""
        try:
            self._update_status("正在初始化 Shimmer GSR+ 设备...")

            if CORE_AVAILABLE:
                # TODO: 实际的Shimmer初始化
                # 这里需要根据你的shimmer_device.py实现
                time.sleep(1)  # 模拟初始化时间
                self.shimmer_connected = True
                self._update_status("✓ Shimmer GSR+ 已连接")
            else:
                # 模拟模式
                time.sleep(0.5)
                self.shimmer_connected = True
                self._update_status("✓ Shimmer GSR+ 已连接 (模拟模式)")

            return True

        except Exception as e:
            self._update_status(f"✗ Shimmer连接失败: {str(e)}")
            self.logger.error(f"Shimmer初始化失败: {e}")
            return False

    def initialize_video(self) -> bool:
        """初始化视频设备"""
        try:
            self._update_status("正在初始化视频设备...")

            if CORE_AVAILABLE:
                # TODO: 实际的视频初始化
                import cv2
                cap = cv2.VideoCapture(0)
                if cap.isOpened():
                    cap.release()
                    self.video_connected = True
                    self._update_status("✓ 视频设备已连接")
                else:
                    self._update_status("✗ 未检测到摄像头")
                    return False
            else:
                # 模拟模式
                time.sleep(0.5)
                self.video_connected = True
                self._update_status("✓ 视频设备已连接 (模拟模式)")

            return True

        except Exception as e:
            self._update_status(f"✗ 视频设备连接失败: {str(e)}")
            self.logger.error(f"视频初始化失败: {e}")
            return False

    def initialize_audio(self) -> bool:
        """初始化音频设备"""
        try:
            self._update_status("正在初始化音频设备...")

            if CORE_AVAILABLE:
                # TODO: 实际的音频初始化
                import sounddevice as sd
                devices = sd.query_devices()
                if len(devices) > 0:
                    self.audio_connected = True
                    self._update_status("✓ 音频设备已连接")
                else:
                    self._update_status("✗ 未检测到音频设备")
                    return False
            else:
                # 模拟模式
                time.sleep(0.5)
                self.audio_connected = True
                self._update_status("✓ 音频设备已连接 (模拟模式)")

            return True

        except Exception as e:
            self._update_status(f"✗ 音频设备连接失败: {str(e)}")
            self.logger.error(f"音频初始化失败: {e}")
            return False

    def disconnect_shimmer(self) -> bool:
        """断开Shimmer设备"""
        try:
            self.shimmer_connected = False
            self._update_status("Shimmer GSR+ 已断开")
            return True
        except Exception as e:
            self.logger.error(f"断开Shimmer失败: {e}")
            return False

    def disconnect_video(self) -> bool:
        """断开视频设备"""
        try:
            self.video_connected = False
            self._update_status("视频设备已断开")
            return True
        except Exception as e:
            self.logger.error(f"断开视频失败: {e}")
            return False

    def disconnect_audio(self) -> bool:
        """断开音频设备"""
        try:
            self.audio_connected = False
            self._update_status("音频设备已断开")
            return True
        except Exception as e:
            self.logger.error(f"断开音频失败: {e}")
            return False

    def get_connected_devices(self) -> list:
        """获取已连接的设备列表"""
        devices = []
        if self.shimmer_connected:
            devices.append('shimmer')
        if self.video_connected:
            devices.append('video')
        if self.audio_connected:
            devices.append('audio')
        return devices

    def start_recording(self) -> bool:
        """开始录制"""
        try:
            if self.is_recording:
                self._update_status("已经在录制中")
                return False

            connected = self.get_connected_devices()
            if not connected:
                self._update_status("✗ 没有连接的设备")
                return False

            self._update_status("=" * 50)
            self._update_status("▶️ 开始数据采集...")
            self._update_status(f"已连接设备: {', '.join([d.upper() for d in connected])}")

            self.is_recording = True
            self.start_time = datetime.now()

            if CORE_AVAILABLE:
                # 启动实际的录制
                self.recording_thread = threading.Thread(
                    target=self._recording_worker,
                    daemon=True
                )
                self.recording_thread.start()
                self._update_status("✓ 采集线程已启动")
            else:
                # 模拟模式
                self._update_status("✓ 采集已开始 (模拟模式)")

            self._update_status("=" * 50)
            return True

        except Exception as e:
            self._update_status(f"✗ 启动录制失败: {str(e)}")
            self.logger.error(f"启动录制失败: {e}")
            self.is_recording = False
            return False

    def stop_recording(self) -> dict:
        """
        停止录制

        Returns:
            采集统计信息
        """
        try:
            if not self.is_recording:
                self._update_status("当前未在录制")
                return {}

            self._update_status("=" * 50)
            self._update_status("⏹️ 停止数据采集...")

            self.is_recording = False

            # 等待录制线程结束
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=5)

            # 计算时长
            if self.start_time:
                duration = (datetime.now() - self.start_time).total_seconds()
            else:
                duration = 0

            stats = {
                'duration': int(duration),
                'devices': self.get_connected_devices(),
                'shimmer_samples': 0,  # TODO: 从实际采集获取
                'video_frames': 0,
                'audio_samples': 0
            }

            self._update_status(f"✓ 采集已停止，时长: {int(duration)}秒")
            self._update_status("=" * 50)

            return stats

        except Exception as e:
            self._update_status(f"✗ 停止录制失败: {str(e)}")
            self.logger.error(f"停止录制失败: {e}")
            return {}

    def _recording_worker(self):
        """录制工作线程"""
        try:
            print("=" * 60)
            print("DEBUG Worker: 录制线程已启动")
            print("=" * 60)

            self._update_status("录制线程运行中...")

            if CORE_AVAILABLE:
                try:
                    # 准备配置
                    config = {
                        'output_directory': str(Path(self.session_paths['shimmer']).parent),
                        'video_camera_id': 0,
                        'video_fps': 30,
                        'video_width': 640,
                        'video_height': 480,
                        'audio_sample_rate': 44100,
                        'audio_channels': 1,
                    }

                    print("DEBUG Worker: 创建 MultimodalRecorder")

                    # 创建录制器
                    self.recorder = multimodal_recorder.MultimodalRecorder(config)

                    print("DEBUG Worker: 调用完整的 initialize()")

                    # 直接调用完整初始化
                    if self.recorder.initialize():
                        print("DEBUG Worker: 初始化成功")

                        print("DEBUG Worker: 准备调用 start_recording()")

                        # 开始录制
                        self.recorder.start_recording()

                        print("DEBUG Worker: start_recording() 已返回")
                        print(f"DEBUG Worker: recorder.is_recording = {self.recorder.is_recording}")

                        self._update_status("✓ 实际采集已启动")

                        # 保持录制状态
                        while self.is_recording:
                            time.sleep(0.1)

                        print("DEBUG Worker: 退出录制循环")

                        # 停止录制
                        if self.recorder.is_recording:
                            print("DEBUG Worker: 调用 stop_recording()")
                            self.recorder.stop_recording()

                        self._update_status("✓ 实际采集已停止")
                    else:
                        print("DEBUG Worker: 初始化失败")
                        self._update_status("✗ 设备初始化失败")

                except Exception as e:
                    self._update_status(f"录制错误: {e}")
                    self.logger.error(f"录制失败: {e}", exc_info=True)
                    print(f"DEBUG Worker: 发生异常: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # 模拟模式
                while self.is_recording:
                    time.sleep(1)

            print("DEBUG Worker: 录制线程即将结束")
            self._update_status("录制线程已停止")

        except Exception as e:
            self._update_status(f"录制线程错误: {str(e)}")
            self.logger.error(f"录制线程错误: {e}", exc_info=True)
            print(f"DEBUG Worker: 线程错误: {e}")
            import traceback
            traceback.print_exc()


    def cleanup(self):
        """清理资源"""
        try:
            if self.is_recording:
                self.stop_recording()

            # 断开所有设备
            if self.shimmer_connected:
                self.disconnect_shimmer()
            if self.video_connected:
                self.disconnect_video()
            if self.audio_connected:
                self.disconnect_audio()

            self._update_status("设备控制器已清理")

        except Exception as e:
            self.logger.error(f"清理失败: {e}")