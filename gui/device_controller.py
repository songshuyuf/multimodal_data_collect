"""
设备控制器 - 重构版
修复了线程阻塞和GUI冻结问题
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
    project_root = Path(__file__).parent.parent
    core_path = project_root / 'core'

    if str(core_path) not in sys.path:
        sys.path.insert(0, str(core_path))

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

        # 多模态录制器
        self.recorder = None

        # 状态回调
        self.status_callback: Optional[Callable] = None

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
                time.sleep(1)
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
        """开始录制 - 重构版，非阻塞"""
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

            if CORE_AVAILABLE:
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

                # 创建录制器（如果不存在）
                if not self.recorder:
                    self._update_status("创建 MultimodalRecorder...")
                    self.recorder = multimodal_recorder.MultimodalRecorder(config)

                    self._update_status("初始化设备...")
                    if not self.recorder.initialize():
                        self._update_status("✗ 设备初始化失败")
                        return False

                # 开始录制（非阻塞）
                self._update_status("启动录制...")
                if self.recorder.start_recording():
                    self.is_recording = True
                    self._update_status("✓ 采集已启动")
                else:
                    self._update_status("✗ 启动录制失败")
                    return False
            else:
                # 模拟模式
                self.is_recording = True
                self._update_status("✓ 采集已开始 (模拟模式)")

            self._update_status("=" * 50)
            return True

        except Exception as e:
            self._update_status(f"✗ 启动录制失败: {str(e)}")
            self.logger.error(f"启动录制失败: {e}", exc_info=True)
            self.is_recording = False
            return False

    def stop_recording(self) -> dict:
        """停止录制"""
        try:
            if not self.is_recording:
                self._update_status("当前未在录制")
                return {}

            self._update_status("=" * 50)
            self._update_status("⏹️ 停止数据采集...")

            stats = {
                'duration': 0,
                'devices': self.get_connected_devices(),
                'shimmer_samples': 0,
                'video_frames': 0,
                'audio_samples': 0
            }

            if CORE_AVAILABLE and self.recorder:
                # 停止录制
                self.recorder.stop_recording()

                # 获取统计信息
                if hasattr(self.recorder, 'video_frame_count'):
                    stats['video_frames'] = self.recorder.video_frame_count
                if hasattr(self.recorder, 'audio_buffer'):
                    stats['audio_samples'] = len(self.recorder.audio_buffer)

            self.is_recording = False
            self._update_status("✓ 采集已停止")
            self._update_status("=" * 50)

            return stats

        except Exception as e:
            self._update_status(f"✗ 停止录制失败: {str(e)}")
            self.logger.error(f"停止录制失败: {e}")
            return {}

    def cleanup(self):
        """清理资源"""
        try:
            if self.is_recording:
                self.stop_recording()

            # 清理录制器
            if self.recorder:
                self.recorder.cleanup()
                self.recorder = None

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