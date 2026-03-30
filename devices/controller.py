"""
设备控制器 - 重构版
统一数据保存到会话目录，简化代码结构
"""

import os
import sys
import json
import logging
import threading
import time
import csv
from pathlib import Path
from typing import Optional, Dict, Callable, List
from datetime import datetime
import numpy as np

# ── 端口记忆配置 ──────────────────────────────────────
_PORT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "device_ports.json",
)


def _load_port_config() -> dict:
    try:
        with open(_PORT_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_port_config(key: str, port: str):
    cfg = _load_port_config()
    cfg[key] = {"port": port}
    os.makedirs(os.path.dirname(_PORT_CONFIG_PATH), exist_ok=True)
    with open(_PORT_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# ==================== 设备模块导入 ====================
CORE_AVAILABLE = False
HEEG_AVAILABLE = False
SHIMMER_AVAILABLE = False
SHIMMER_EMG_AVAILABLE = False
DATA_SAVER_AVAILABLE = False

try:
    import devices.config as core_config
    from devices.heeg import NeuracleHEEGDevice
    CORE_AVAILABLE = True
    HEEG_AVAILABLE = True
    print("✓ Core模块加载成功")
    print("✓ HEEG驱动已加载")
except Exception as e:
    print(f"⚠ Core模块不可用: {e}")
    print("→ 将使用模拟模式运行")

try:
    from devices.shimmer_gsr import ShimmerGSRDevice
    SHIMMER_AVAILABLE = True
    print("✓ Shimmer GSR驱动已加载")
except ImportError as e:
    print(f"⚠ Shimmer GSR驱动不可用: {e}")

try:
    from devices.shimmer_emg import ShimmerEMGDevice
    SHIMMER_EMG_AVAILABLE = True
    print("✓ Shimmer EMG驱动已加载")
except ImportError as e:
    print(f"⚠ Shimmer EMG驱动不可用: {e}")

try:
    from devices.data_saver import DataSaver
    DATA_SAVER_AVAILABLE = True
    print("✓ 数据保存器已加载")
except ImportError as e:
    print(f"⚠ 数据保存器不可用: {e}")

from devices.mock import MockHEEGDevice, MockShimmerDevice


class DeviceController:
    """设备控制器 - 管理所有采集设备"""

    def __init__(self, session_paths: Dict[str, str] = None, use_mock_devices: bool = True):
        """
        初始化设备控制器

        Args:
            session_paths: 会话数据路径字典
            use_mock_devices: 是否使用模拟设备
        """
        self.logger = logging.getLogger(__name__)
        self.session_paths = session_paths
        self.use_mock_devices = use_mock_devices

        # 设备状态
        self.devices_initialized = False
        self.is_recording = False

        # 设备连接状态
        self.shimmer_connected = False
        self.shimmer_emg_connected = False
        self.video_connected = False
        self.audio_connected = False
        self.heeg_connected = False

        # 设备实例
        self.heeg_device = None
        self.shimmer_device = None
        self.shimmer_emg_device = None
        self.video_stream = None
        self.audio_stream = None

        # EMG 实时回调（由 realtime_emg_tab 注入）
        self.emg_realtime_callback: Optional[Callable] = None

        # 状态回调
        self.status_callback: Optional[Callable] = None

        # 采集线程
        self.recording_thread = None
        self.video_thread = None
        self.audio_thread = None
        self.start_time = None

        # 统计信息
        self.heeg_packet_count = 0
        self.heeg_sample_count = 0
        self.shimmer_packet_count = 0
        self.shimmer_sample_count = 0
        self.shimmer_emg_packet_count = 0
        self.video_frame_count = 0
        self.audio_sample_count = 0

        # 实时数据
        self.latest_video_frame = None
        self.latest_audio_data = None
        self.frame_lock = threading.Lock()
        self.audio_lock = threading.Lock()

        # 数据文件
        self.heeg_csv_file = None
        self.heeg_csv_writer = None
        self.shimmer_csv_file = None
        self.shimmer_csv_writer = None
        self.shimmer_emg_csv_file = None
        self.shimmer_emg_csv_writer = None
        self.video_writer = None
        self.audio_wave_file = None

        if self.use_mock_devices:
            print("\n" + "=" * 60)
            print("⚠️  模拟设备模式")
            print("=" * 60 + "\n")

    def set_status_callback(self, callback: Callable):
        """设置状态回调"""
        self.status_callback = callback

    def _update_status(self, message: str):
        """更新状态"""
        if self.status_callback:
            self.status_callback(message)
        self.logger.info(message)

    # ==================== 设备初始化 ====================

    def initialize_shimmer(self) -> bool:
        """初始化 Shimmer GSR+ —— 优先上次成功端口，失败再全扫描"""
        try:
            self._update_status("正在初始化 Shimmer GSR+ 设备...")

            if CORE_AVAILABLE and SHIMMER_AVAILABLE:
                from devices.shimmer_gsr import ShimmerGSRDevice
                import devices.config as core_config

                self.shimmer_device = ShimmerGSRDevice(core_config.SHIMMER_CONFIG)
                all_ports = self.shimmer_device._list_com_ports()

                if not all_ports:
                    self._update_status("✗ 未检测到任何 COM 端口")
                    return False

                saved = _load_port_config().get("shimmer_gsr", {}).get("port")
                if saved and saved in all_ports:
                    ordered = [saved] + [p for p in all_ports if p != saved]
                    self._update_status(f"记忆端口 {saved}，优先尝试")
                else:
                    ordered = all_ports
                    self._update_status(
                        f"扫描到 {len(all_ports)} 个 COM 口，逐一尝试..."
                    )

                _GSR_PORT_TIMEOUT = 15.0

                for port in ordered:
                    self._update_status(f"  → 尝试 {port}（最多 {_GSR_PORT_TIMEOUT:.0f}s）...")

                    _res, _evt = {}, threading.Event()

                    def _try(p=port):
                        try:
                            _res["ok"] = self.shimmer_device.connect(p)
                        except Exception as e:
                            _res["err"] = str(e)
                        finally:
                            _evt.set()

                    threading.Thread(target=_try, daemon=True).start()

                    if not _evt.wait(timeout=_GSR_PORT_TIMEOUT):
                        self._update_status(
                            f"    {port} 连接超时（>{_GSR_PORT_TIMEOUT:.0f}s），跳过"
                        )
                        try:
                            if (hasattr(self.shimmer_device, 'serial_obj')
                                    and self.shimmer_device.serial_obj
                                    and self.shimmer_device.serial_obj.is_open):
                                self.shimmer_device.serial_obj.close()
                        except Exception:
                            pass
                        self.shimmer_device = ShimmerGSRDevice(core_config.SHIMMER_CONFIG)
                        continue

                    if "err" in _res:
                        self._update_status(f"    {port} 出错（{_res['err']}），跳过")
                        continue

                    if _res.get("ok"):
                        self.shimmer_connected = True
                        _save_port_config("shimmer_gsr", port)
                        self._update_status(f"✓ Shimmer GSR+ 已连接（{port}）")
                        try:
                            info = self.shimmer_device.get_device_info()
                            self._update_status(
                                f"  → 采样率: {info.get('sampling_rate', 'N/A')} Hz"
                            )
                        except Exception:
                            pass
                        return True
                    else:
                        self._update_status(f"    {port} 无响应，跳过")

                self._update_status("✗ 所有 COM 口均未能连接 Shimmer 设备")
                return False

            else:
                time.sleep(0.5)
                self.shimmer_connected = True
                self._update_status("✓ Shimmer GSR+ 已连接（模拟）")
                return True

        except Exception as e:
            self._update_status(f"✗ Shimmer GSR 连接失败: {e}")
            return False

    def initialize_shimmer_emg(self) -> bool:
        """初始化 Shimmer EMG —— 优先上次成功端口，排除 GSR 占用口"""
        try:
            self._update_status("正在初始化 Shimmer EMG 设备...")

            if CORE_AVAILABLE and SHIMMER_EMG_AVAILABLE:
                from devices.shimmer_emg import ShimmerEMGDevice

                used_port = None
                if self.shimmer_device and hasattr(self.shimmer_device, '_ser') \
                        and self.shimmer_device._ser:
                    try:
                        used_port = self.shimmer_device._ser.port
                    except Exception:
                        pass

                import serial.tools.list_ports
                com_ports = [p.device for p in serial.tools.list_ports.comports()]
                if used_port:
                    com_ports = [p for p in com_ports if p != used_port]

                if not com_ports:
                    self._update_status("✗ 未检测到可用 COM 端口（EMG）")
                    return False

                saved = _load_port_config().get("shimmer_emg", {}).get("port")
                if saved and saved in com_ports:
                    ordered = [saved] + [p for p in com_ports if p != saved]
                    self._update_status(f"记忆端口 {saved}，优先尝试")
                else:
                    ordered = com_ports
                    self._update_status(
                        f"扫描 {len(com_ports)} 个 COM 口寻找 EMG 设备..."
                    )

                self.shimmer_emg_device = ShimmerEMGDevice()
                if hasattr(self.shimmer_emg_device, 'set_status_callback'):
                    self.shimmer_emg_device.set_status_callback(self._update_status)

                _EMG_PORT_TIMEOUT = 60.0

                for port in ordered:
                    self._update_status(
                        f"  → 尝试 {port}（连接+配置，最多 {_EMG_PORT_TIMEOUT:.0f}s）..."
                    )

                    _res, _evt = {}, threading.Event()

                    def _try(p=port):
                        try:
                            _res["ok"] = self.shimmer_emg_device.connect(p)
                        except Exception as e:
                            _res["err"] = str(e)
                        finally:
                            _evt.set()

                    threading.Thread(target=_try, daemon=True).start()

                    if not _evt.wait(timeout=_EMG_PORT_TIMEOUT):
                        self._update_status(
                            f"    {port} 连接超时（>{_EMG_PORT_TIMEOUT:.0f}s），跳过"
                        )
                        try:
                            if (self.shimmer_emg_device._ser
                                    and self.shimmer_emg_device._ser.is_open):
                                self.shimmer_emg_device._ser.close()
                        except Exception:
                            pass
                        self.shimmer_emg_device = ShimmerEMGDevice()
                        if hasattr(self.shimmer_emg_device, 'set_status_callback'):
                            self.shimmer_emg_device.set_status_callback(
                                self._update_status
                            )
                        continue

                    if "err" in _res:
                        self._update_status(f"    {port} 出错（{_res['err']}），跳过")
                        continue

                    if _res.get("ok"):
                        self.shimmer_emg_connected = True
                        _save_port_config("shimmer_emg", port)
                        self._update_status(f"✓ Shimmer EMG 已连接（{port}）")
                        info = self.shimmer_emg_device.get_device_info()
                        self._update_status(
                            f"  → 采样率: {info.get('sampling_rate', 'N/A')} Hz"
                        )
                        return True
                    else:
                        self._update_status(f"    {port} 无响应，跳过")

                self._update_status("✗ 所有 COM 口均未能连接 EMG 设备")
                return False

            else:
                time.sleep(0.5)
                self.shimmer_emg_connected = True
                self._update_status("✓ Shimmer EMG 已连接（模拟）")
                return True

        except Exception as e:
            self._update_status(f"✗ Shimmer EMG 连接失败: {e}")
            return False

    def initialize_video(self, camera_id: Optional[int] = None) -> bool:
        """初始化视频设备（同步等待摄像头真正打开）"""
        try:
            self._update_status("正在初始化视频设备...")

            if CORE_AVAILABLE:
                if camera_id is None:
                    import cv2, sys as _sys
                    backend = cv2.CAP_DSHOW if _sys.platform == "win32" else cv2.CAP_ANY
                    for i in range(4):
                        cap = cv2.VideoCapture(i, backend)
                        if cap.isOpened():
                            ret, _ = cap.read()
                            cap.release()
                            if ret:
                                camera_id = i
                                break
                        else:
                            cap.release()
                    time.sleep(0.3)

                if camera_id is None:
                    self._update_status("✗ 未检测到可用摄像头")
                    return False

                ready_event = threading.Event()
                result = {}

                def create_stream():
                    from devices.video_stream import VideoLSLStream
                    self.video_stream = VideoLSLStream(camera_id, 30, (640, 480))
                    if self.video_stream.start():
                        self.video_connected = True
                        result["ok"] = True
                        self._update_status(f"✓ 视频设备已连接 (camera {camera_id})")
                    else:
                        result["ok"] = False
                        self._update_status("✗ 视频设备打开失败（已重试多次）")
                    ready_event.set()

                threading.Thread(target=create_stream, daemon=True).start()
                ready_event.wait(timeout=15.0)

                return result.get("ok", False)
            else:
                self.video_connected = True
                self._update_status("✓ 视频设备已连接 (模拟)")
                return True

        except Exception as e:
            self._update_status(f"✗ 视频连接失败: {e}")
            return False

    def initialize_audio(self) -> bool:
        """初始化音频设备"""
        try:
            self._update_status("正在初始化音频设备...")

            if CORE_AVAILABLE:
                from devices.audio_stream import AudioLSLStream
                self.audio_stream = AudioLSLStream(44100, 1, 1024)
                if self.audio_stream.start():
                    self.audio_connected = True
                    self._update_status("✓ 音频设备已连接")
                    return True
            else:
                self.audio_connected = True
                self._update_status("✓ 音频设备已连接 (模拟)")
                return True

            return False

        except Exception as e:
            self._update_status(f"✗ 音频连接失败: {e}")
            return False

    def initialize_heeg(self) -> bool:
        """初始化HEEG设备"""
        try:
            self._update_status("正在初始化 Neuracle HEEG 设备...")

            if self.use_mock_devices or not HEEG_AVAILABLE:
                self.heeg_device = MockHEEGDevice(2000, 64)
                if self.heeg_device.connect():
                    self.heeg_connected = True
                    self._update_status("✓ HEEG设备已连接（模拟）")
                    return True
                return False

            from devices.heeg import NeuracleHEEGDevice
            self.heeg_device = NeuracleHEEGDevice(
                hostname='127.0.0.1', port=8172
            )
            if self.heeg_device.connect(max_retries=3):
                self.heeg_connected = True
                info = self.heeg_device.get_device_info()
                self._update_status(
                    f"✓ HEEG 已连接（{info['channel_count']}ch, "
                    f"{info['sample_rate']}Hz）"
                )
                return True
            else:
                self._update_status(
                    "✗ HEEG 连接失败，请检查 NSH-R 软件是否运行"
                )
                return False

        except Exception as e:
            self._update_status(f"✗ HEEG初始化失败: {e}")
            return False

    # ==================== 数据采集 ====================

    def start_recording(self) -> bool:
        """开始录制"""
        try:
            self._update_status("开始录制...")

            if not any([self.shimmer_connected, self.shimmer_emg_connected,
                       self.video_connected, self.audio_connected,
                       self.heeg_connected]):
                self._update_status("✗ 没有设备连接")
                return False

            # ========== 获取会话目录 ==========
            if hasattr(self, 'session_paths') and self.session_paths:
                first_path = list(self.session_paths.values())[0]
                session_dir = os.path.dirname(os.path.dirname(first_path))
            else:
                session_dir = './data/default_session'
                print(f"[警告] 使用默认路径: {session_dir}")

            print(f"[数据保存] 会话目录: {session_dir}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 创建数据文件
            self._create_data_files(session_dir, timestamp)

            # 初始化状态
            self.is_recording = True
            self.start_time = datetime.now()
            self._reset_counters()

            # 启动线程
            self._start_capture_threads()
            self._start_device_streams()

            # 启动主采集线程
            self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
            self.recording_thread.start()

            self._update_status("✓ 录制已开始")
            return True

        except Exception as e:
            self._update_status(f"✗ 开始录制失败: {e}")
            self.logger.error(f"开始录制失败: {e}", exc_info=True)
            return False

    def _create_data_files(self, session_dir: str, timestamp: str):
        """创建数据文件"""
        # HEEG
        if self.heeg_connected and self.heeg_device:
            heeg_dir = os.path.join(session_dir, 'heeg')
            os.makedirs(heeg_dir, exist_ok=True)

            heeg_path = os.path.join(heeg_dir, f'heeg_{timestamp}.csv')
            self.heeg_csv_file = open(heeg_path, 'w', newline='', encoding='utf-8')
            self.heeg_csv_writer = csv.writer(self.heeg_csv_file)

            headers = ['Timestamp'] + [f'Ch{i+1}' for i in range(64)]
            self.heeg_csv_writer.writerow(headers)
            self._update_status(f"✓ HEEG: {heeg_path}")
            print(f"[数据保存] HEEG: {heeg_path}")

            sync_path = os.path.join(heeg_dir, f'heeg_sync_{timestamp}.csv')
            self._heeg_sync_file = open(sync_path, 'w', newline='', encoding='utf-8')
            self._heeg_sync_writer = csv.writer(self._heeg_sync_file)
            self._heeg_sync_writer.writerow([
                'system_time_sec', 'heeg_timestamp_ms',
            ])
            self._heeg_sync_count = 0
            print(f"[数据保存] HEEG 时间对齐: {sync_path}")

        # Shimmer
        if self.shimmer_connected:
            shimmer_dir = os.path.join(session_dir, 'shimmer')
            os.makedirs(shimmer_dir, exist_ok=True)

            shimmer_path = os.path.join(shimmer_dir, f'shimmer_{timestamp}.csv')
            self.shimmer_csv_file = open(shimmer_path, 'w', newline='', encoding='utf-8')
            self.shimmer_csv_writer = csv.writer(self.shimmer_csv_file)

            # ========== 修复：使用正确的表头 ==========
            headers = [
                'Timestamp',
                'GSR_Conductance', 'GSR_Resistance', 'PPG',
                'Accel_X', 'Accel_Y', 'Accel_Z',
                'Gyro_X', 'Gyro_Y', 'Gyro_Z',
                'Mag_X', 'Mag_Y', 'Mag_Z',
                'Temperature', 'Pressure',
                'HeartRate', 'Battery'
            ]
            # =========================================

            self.shimmer_csv_writer.writerow(headers)
            self._update_status(f"✓ Shimmer: {shimmer_path}")
            print(f"[数据保存] Shimmer: {shimmer_path}")

        # Shimmer EMG
        if self.shimmer_emg_connected:
            emg_dir = os.path.join(session_dir, 'shimmer_emg')
            os.makedirs(emg_dir, exist_ok=True)
            emg_path = os.path.join(emg_dir, f'emg_{timestamp}.csv')
            self.shimmer_emg_csv_file = open(emg_path, 'w', newline='', encoding='utf-8')
            self.shimmer_emg_csv_writer = csv.writer(self.shimmer_emg_csv_file)
            self.shimmer_emg_csv_writer.writerow([
                'Timestamp',
                'EMG_CH1_mV', 'EMG_CH2_mV',
                'Accel_X_ms2', 'Accel_Y_ms2', 'Accel_Z_ms2',
                'Gyro_X_dps', 'Gyro_Y_dps', 'Gyro_Z_dps',
                'EMG_Status',
            ])
            self._update_status(f"✓ EMG: {emg_path}")
            print(f"[数据保存] EMG: {emg_path}")

        # 视频
        if self.video_connected:
            import cv2
            video_dir = os.path.join(session_dir, 'video')
            os.makedirs(video_dir, exist_ok=True)

            video_path = os.path.join(video_dir, f'video_{timestamp}.avi')
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(video_path, fourcc, 30, (640, 480))
            self._update_status(f"✓ 视频: {video_path}")
            print(f"[数据保存] 视频: {video_path}")

        # 音频
        if self.audio_connected:
            import wave
            audio_dir = os.path.join(session_dir, 'audio')
            os.makedirs(audio_dir, exist_ok=True)

            audio_path = os.path.join(audio_dir, f'audio_{timestamp}.wav')
            self.audio_wave_file = wave.open(audio_path, 'wb')

            # ========== 使用检测的通道数 ==========
            self.audio_wave_file.setnchannels(getattr(self, 'audio_channels', 1))  # ← 改这里
            # ====================================

            self.audio_wave_file.setsampwidth(2)
            self.audio_wave_file.setframerate(44100)
            self._update_status(f"✓ 音频: {audio_path}")
            print(f"[数据保存] 音频: {audio_path}")

    def _reset_counters(self):
        """重置计数器"""
        self.video_frame_count = 0
        self.audio_sample_count = 0
        self.heeg_packet_count = 0
        self.heeg_sample_count = 0
        self.shimmer_packet_count = 0
        self.shimmer_sample_count = 0
        self.shimmer_emg_packet_count = 0

    def _start_capture_threads(self):
        """启动采集线程"""
        if self.video_connected and self.video_stream:
            self.video_thread = threading.Thread(target=self._video_capture_loop, daemon=True)
            self.video_thread.start()
            self._update_status("✓ 视频采集已启动")

        if self.audio_connected and self.audio_stream:
            self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
            self.audio_thread.start()
            self._update_status("✓ 音频采集已启动")

    def _start_device_streams(self):
        """启动设备数据流"""
        # HEEG
        if self.heeg_connected and self.heeg_device:
            if self.heeg_device.start_streaming():
                self._update_status("✓ HEEG 数据流已启动")
                if hasattr(self.heeg_device, 'set_data_callback'):
                    self.heeg_device.set_data_callback(self._heeg_data_callback)

        # Shimmer GSR
        if self.shimmer_connected and self.shimmer_device:
            if self.shimmer_device.start_streaming():
                self._update_status("✓ Shimmer GSR 数据流已启动")
                if hasattr(self.shimmer_device, 'set_data_callback'):
                    self.shimmer_device.set_data_callback(self._shimmer_data_callback)

        # Shimmer EMG
        if self.shimmer_emg_connected and self.shimmer_emg_device:
            try:
                self.shimmer_emg_device.start_streaming(self._shimmer_emg_data_callback)
                self._update_status("✓ Shimmer EMG 数据流已启动")
            except Exception as e:
                self._update_status(f"✗ Shimmer EMG 数据流启动失败: {e}")

    def _recording_loop(self):
        """主采集循环"""
        print("[录制] 主采集线程已启动")

        while self.is_recording:
            try:
                if self.shimmer_connected and self.shimmer_device:
                    try:
                        success, data = self.shimmer_device.read_data()

                        if not success or not data:
                            continue

                        if self.shimmer_csv_writer:
                            timestamp = time.time()

                            # ========== 使用 extract_sample_from_packet ==========
                            result = self.shimmer_device.extract_sample_from_packet(data)

                            # 解包
                            if isinstance(result, tuple) and len(result) == 2:
                                sample, packet_timestamp = result
                            else:
                                sample = result

                            # 写入 CSV
                            row = [timestamp] + list(sample)
                            self.shimmer_csv_writer.writerow(row)
                            # ====================================================

                            # 定期刷新
                            if self.shimmer_packet_count % 10 == 0:
                                self.shimmer_csv_file.flush()

                            self.shimmer_packet_count += 1

                            if self.shimmer_packet_count % 100 == 0:
                                print(f"[Shimmer] 已采集 {self.shimmer_packet_count} 包")

                    except Exception as e:
                        if self.shimmer_packet_count == 0:
                            print(f"[Shimmer] 错误: {e}")
                            import traceback
                            traceback.print_exc()

                time.sleep(0.001)

            except Exception as e:
                self.logger.error(f"录制循环错误: {e}")
                time.sleep(0.1)

        print(f"[录制] 停止，共 {self.shimmer_packet_count} 包")

    def _video_capture_loop(self):
        """视频采集循环（含自动恢复）"""
        import cv2, sys as _sys
        print("[视频] 采集线程已启动")

        consecutive_failures = 0
        MAX_CONSECUTIVE = 30
        REOPEN_BACKOFF = 1.0

        while self.is_recording and self.video_connected:
            try:
                if self.video_stream and self.video_stream.cap and self.video_stream.cap.isOpened():
                    ret, frame = self.video_stream.cap.read()
                    if ret:
                        consecutive_failures = 0
                        with self.frame_lock:
                            self.latest_video_frame = frame.copy()
                            self.video_frame_count += 1
                        if self.video_writer:
                            self.video_writer.write(frame)
                    else:
                        consecutive_failures += 1
                else:
                    consecutive_failures += 1

                if consecutive_failures >= MAX_CONSECUTIVE:
                    print(f"[视频] 连续 {consecutive_failures} 次读帧失败，尝试重新打开摄像头...")
                    self._reopen_video_capture()
                    consecutive_failures = 0
                    time.sleep(REOPEN_BACKOFF)
                    continue

                time.sleep(1 / 30)

            except Exception as e:
                self.logger.error(f"视频采集错误: {e}")
                consecutive_failures += 1
                time.sleep(0.1)

        print(f"[视频] 采集线程已停止，共 {self.video_frame_count} 帧")

    def _reopen_video_capture(self):
        """尝试重新打开摄像头"""
        try:
            if self.video_stream and self.video_stream.cap:
                self.video_stream.cap.release()
                self.video_stream.cap = None
            time.sleep(0.5)
            if self.video_stream:
                ok = self.video_stream.start()
                if ok:
                    print("[视频] 摄像头重新打开成功")
                else:
                    print("[视频] 摄像头重新打开失败")
        except Exception as e:
            print(f"[视频] 重新打开摄像头出错: {e}")

    def _audio_capture_loop(self):
        """音频采集循环"""
        import sounddevice as sd
        print("[音频] 采集线程已启动")

        # ========== 添加：自动检测通道数 ==========
        try:
            default_device = sd.query_devices(kind='input')
            max_channels = int(default_device['max_input_channels'])
            channels = min(2, max_channels)  # 优先立体声

            print(f"[音频] 设备: {default_device['name']}")
            print(f"[音频] 通道: {channels} (设备最大: {max_channels})")
        except Exception as e:
            print(f"[音频] 设备检测失败: {e}")
            channels = 1

        # 保存通道数
        self.audio_channels = channels

        # ==========================================

        def audio_callback(indata, frames, time_info, status):
            if self.is_recording and self.audio_connected:
                with self.audio_lock:
                    audio_data = indata.flatten()
                    self.latest_audio_data = audio_data.copy()
                    self.audio_sample_count += len(audio_data)

                    if self.audio_wave_file:
                        audio_int16 = (audio_data * 32767).astype(np.int16)
                        self.audio_wave_file.writeframes(audio_int16.tobytes())

        try:
            # ========== 修改这里：使用检测的通道数 ==========
            with sd.InputStream(
                    samplerate=44100,
                    channels=channels,  # ← 改这里！从 1 改为 channels
                    callback=audio_callback,
                    blocksize=1024
            ):
                while self.is_recording and self.audio_connected:
                    time.sleep(0.1)
            # ============================================
        except Exception as e:
            self.logger.error(f"音频采集错误: {e}")

        print("[音频] 采集线程已停止")

    def _heeg_data_callback(self, data_struct: Dict):
        """HEEG数据回调"""
        try:
            self.heeg_packet_count += 1
            self.heeg_sample_count += data_struct['dataCountPerChannel']

            if self.heeg_csv_writer:
                num_samples = data_struct['dataCountPerChannel']

                for i in range(num_samples):
                    timestamp = time.time()
                    row = [timestamp]
                    for ch in range(data_struct['channelCount']):
                        row.append(data_struct['datas'][ch, i])
                    self.heeg_csv_writer.writerow(row)

                if self.heeg_packet_count % 100 == 0:
                    self.heeg_csv_file.flush()
                    print(f"[HEEG] 已采集 {self.heeg_packet_count} 个数据包")

            if hasattr(self, '_heeg_sync_writer') and self._heeg_sync_writer:
                self._heeg_sync_count += 1
                if self._heeg_sync_count % 50 == 1:
                    self._heeg_sync_writer.writerow([
                        f"{time.time():.6f}",
                        data_struct.get('timeStamp', 0),
                    ])
                    if self._heeg_sync_count % 500 == 1:
                        self._heeg_sync_file.flush()

        except Exception as e:
            self.logger.error(f"HEEG回调错误: {e}")

    def _shimmer_data_callback(self, data: dict):
        """Shimmer数据回调"""
        try:
            self.shimmer_packet_count += 1

            if self.shimmer_csv_writer:
                row = [
                    data.get('timestamp', time.time()),
                    data.get('gsr_conductance', 0.0),
                    data.get('gsr_resistance', 0.0),
                    data.get('ppg', 0.0),
                    data.get('accel_x', 0.0),
                    data.get('accel_y', 0.0),
                    data.get('accel_z', 0.0),
                    data.get('gyro_x', 0.0),
                    data.get('gyro_y', 0.0),
                    data.get('gyro_z', 0.0),
                    data.get('mag_x', 0.0),
                    data.get('mag_y', 0.0),
                    data.get('mag_z', 0.0),
                    data.get('temperature', 0.0),
                    data.get('pressure', 0.0),
                    data.get('heart_rate', 0.0),
                    data.get('battery', 0.0)
                ]
                self.shimmer_csv_writer.writerow(row)

                if self.shimmer_packet_count % 50 == 0:
                    self.shimmer_csv_file.flush()

                if self.shimmer_packet_count % 100 == 0:
                    print(f"[Shimmer] 已采集 {self.shimmer_packet_count} 个数据包")

        except Exception as e:
            self.logger.error(f"Shimmer GSR 回调错误: {e}")

    def _shimmer_emg_data_callback(self, data: dict):
        """Shimmer EMG 数据回调 —— 写 CSV + 推送到实时前端"""
        try:
            self.shimmer_emg_packet_count += 1

            if self.shimmer_emg_csv_writer:
                row = [
                    data.get('timestamp',   time.time()),
                    data.get('emg_ch1_mv',  0.0),
                    data.get('emg_ch2_mv',  0.0),
                    data.get('accel_x_ms2', 0.0),
                    data.get('accel_y_ms2', 0.0),
                    data.get('accel_z_ms2', 0.0),
                    data.get('gyro_x_dps',  0.0),
                    data.get('gyro_y_dps',  0.0),
                    data.get('gyro_z_dps',  0.0),
                    data.get('emg_status',  0),
                ]
                self.shimmer_emg_csv_writer.writerow(row)
                if self.shimmer_emg_packet_count % 100 == 0:
                    self.shimmer_emg_csv_file.flush()

            # 推送到实时可视化前端
            if self.emg_realtime_callback:
                try:
                    self.emg_realtime_callback(data)
                except Exception:
                    pass

        except Exception as e:
            self.logger.error(f"Shimmer EMG 回调错误: {e}")

    def stop_recording(self) -> Dict:
        """停止录制"""
        try:
            self._update_status("停止录制...")
            self.is_recording = False

            # 等待线程结束
            for thread in [self.recording_thread, self.video_thread, self.audio_thread]:
                if thread and thread.is_alive():
                    thread.join(timeout=2)

            # 停止数据流
            if self.heeg_connected and self.heeg_device:
                self.heeg_device.stop_streaming()
                self._update_status("✓ HEEG 数据流已停止")

            if self.shimmer_connected and self.shimmer_device:
                self.shimmer_device.stop_streaming()
                self._update_status("✓ Shimmer GSR 数据流已停止")

            if self.shimmer_emg_connected and self.shimmer_emg_device:
                self.shimmer_emg_device.stop_streaming()
                self._update_status("✓ Shimmer EMG 数据流已停止")

            # 计算时长
            duration = 0
            if self.start_time:
                duration = (datetime.now() - self.start_time).total_seconds()

            # 关闭文件
            self._close_data_files()

            # 输出统计
            self._print_statistics(duration)

            return {
                'duration': duration,
                'video_frames': self.video_frame_count,
                'audio_samples': self.audio_sample_count,
                'heeg_packets': self.heeg_packet_count,
                'heeg_samples': self.heeg_sample_count,
                'shimmer_packets': self.shimmer_packet_count,
            }

        except Exception as e:
            self._update_status(f"✗ 停止录制失败: {e}")
            return {'duration': 0}

    def _close_data_files(self):
        """关闭数据文件"""
        if self.heeg_csv_file:
            self.heeg_csv_file.close()
            self._update_status("✓ HEEG数据已保存")
            print("[数据保存] HEEG文件已关闭")
            self.heeg_csv_file = None
            self.heeg_csv_writer = None

        if hasattr(self, '_heeg_sync_file') and self._heeg_sync_file:
            self._heeg_sync_file.close()
            self._heeg_sync_file = None
            self._heeg_sync_writer = None
            print("[数据保存] HEEG 时间对齐文件已关闭")

        if self.shimmer_csv_file:
            self.shimmer_csv_file.close()
            self._update_status("✓ Shimmer GSR 数据已保存")
            print("[数据保存] Shimmer GSR 文件已关闭")
            self.shimmer_csv_file = None
            self.shimmer_csv_writer = None

        if self.shimmer_emg_csv_file:
            self.shimmer_emg_csv_file.close()
            self._update_status("✓ Shimmer EMG 数据已保存")
            print("[数据保存] Shimmer EMG 文件已关闭")
            self.shimmer_emg_csv_file = None
            self.shimmer_emg_csv_writer = None

        if self.video_writer:
            self.video_writer.release()
            self._update_status("✓ 视频已保存")
            print("[数据保存] 视频文件已关闭")
            self.video_writer = None

        if self.audio_wave_file:
            self.audio_wave_file.close()
            self._update_status("✓ 音频已保存")
            print("[数据保存] 音频文件已关闭")
            self.audio_wave_file = None

    def _print_statistics(self, duration: float):
        """打印统计信息"""
        self._update_status(f"✓ 录制已停止 (时长: {duration:.1f}秒)")

        if self.video_connected:
            self._update_status(f"  视频: {self.video_frame_count} 帧")
        if self.audio_connected:
            self._update_status(f"  音频: {self.audio_sample_count} 样本")
        if self.heeg_connected:
            self._update_status(f"  HEEG: {self.heeg_packet_count} 包, {self.heeg_sample_count} 样本")
        if self.shimmer_connected:
            self._update_status(f"  Shimmer GSR: {self.shimmer_packet_count} 包")
        if self.shimmer_emg_connected:
            self._update_status(f"  Shimmer EMG: {self.shimmer_emg_packet_count} 包")

    # ==================== 断开连接 ====================

    def disconnect_shimmer(self) -> bool:
        """断开 Shimmer GSR"""
        try:
            if self.shimmer_device:
                self.shimmer_device.disconnect()
                self.shimmer_device = None
            self.shimmer_connected = False
            self._update_status("Shimmer GSR 已断开")
            return True
        except Exception as e:
            self.logger.error(f"断开 Shimmer GSR 失败: {e}")
            return False

    def disconnect_shimmer_emg(self) -> bool:
        """断开 Shimmer EMG"""
        try:
            if self.shimmer_emg_device:
                self.shimmer_emg_device.disconnect()
                self.shimmer_emg_device = None
            self.shimmer_emg_connected = False
            self._update_status("Shimmer EMG 已断开")
            return True
        except Exception as e:
            self.logger.error(f"断开 Shimmer EMG 失败: {e}")
            return False

    def disconnect_video(self) -> bool:
        """断开视频"""
        try:
            if self.video_stream:
                self.video_stream.stop()
                self.video_stream = None
            self.video_connected = False
            self._update_status("视频已断开")
            return True
        except Exception as e:
            self.logger.error(f"断开视频失败: {e}")
            return False

    def disconnect_audio(self) -> bool:
        """断开音频"""
        try:
            if self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream = None
            self.audio_connected = False
            self._update_status("音频已断开")
            return True
        except Exception as e:
            self.logger.error(f"断开音频失败: {e}")
            return False

    def disconnect_heeg(self) -> bool:
        """断开HEEG"""
        try:
            if self.heeg_device:
                self.heeg_device.disconnect()
                self.heeg_device = None
            self.heeg_connected = False
            self._update_status("HEEG已断开")
            return True
        except Exception as e:
            self._update_status(f"✗ 断开HEEG失败: {e}")
            return False

    # ==================== 实时数据 ====================

    @property
    def heeg_ready(self) -> bool:
        """EEG Tab 用来判断设备是否可用"""
        if not self.heeg_connected or not self.heeg_device:
            return False
        if hasattr(self.heeg_device, 'state'):
            from devices.heeg import HEEGState
            return self.heeg_device.state in (HEEGState.READY, HEEGState.RUNNING)
        return True

    def get_realtime_heeg_data(self, num_samples: int = 2000):
        """获取 EEG 实时数据供前端绘图

        Returns:
            numpy array (channels, samples) 或 None
        """
        if not self.heeg_connected or not self.heeg_device:
            return None
        if hasattr(self.heeg_device, 'get_latest_data'):
            return self.heeg_device.get_latest_data(num_samples)
        return None

    def get_latest_video_frame(self):
        """获取最新视频帧"""
        with self.frame_lock:
            if self.latest_video_frame is not None:
                return self.latest_video_frame.copy()
        return None

    def get_video_fps(self) -> float:
        """计算实时视频帧率"""
        if self.start_time and self.video_frame_count > 0:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            if elapsed > 0:
                return self.video_frame_count / elapsed
        return 0.0

    def get_latest_audio_data(self, buffer_size: int = 4000):
        """获取最新音频数据"""
        with self.audio_lock:
            if self.latest_audio_data is not None:
                data = self.latest_audio_data
                if len(data) > buffer_size:
                    return data[-buffer_size:]
                return data
        return None

    # ==================== 辅助方法 ====================

    def cleanup(self):
        """清理资源"""
        try:
            self._update_status("清理设备资源...")

            if self.is_recording:
                self.stop_recording()

            if self.shimmer_connected:
                self.disconnect_shimmer()
            if self.shimmer_emg_connected:
                self.disconnect_shimmer_emg()
            if self.video_connected:
                self.disconnect_video()
            if self.audio_connected:
                self.disconnect_audio()
            if self.heeg_connected:
                self.disconnect_heeg()

            self._update_status("✓ 资源清理完成")

        except Exception as e:
            self.logger.error(f"清理资源失败: {e}")
