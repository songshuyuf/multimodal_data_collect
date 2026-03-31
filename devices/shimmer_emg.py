"""
Shimmer EMG 设备驱动  ── ShimmerEMGDevice
==========================================
与 ShimmerGSRDevice 保持相同的对外接口：
  connect(port)  /  disconnect()
  start_streaming(callback)  /  stop_streaming()

数据回调字典字段：
  timestamp        : float  – Unix 时间（秒）
  emg_ch1_mv       : float  – CH1 EMG（mV，已校准）
  emg_ch2_mv       : float  – CH2 EMG（mV，已校准）
  accel_x_ms2      : float  – 加速度 X（m/s²）
  accel_y_ms2      : float  – 加速度 Y
  accel_z_ms2      : float  – 加速度 Z
  gyro_x_dps       : float  – 陀螺仪 X（deg/s）
  gyro_y_dps       : float  – Y
  gyro_z_dps       : float  – Z
  emg_status       : int    – ADS1292R 状态字节

复用 test_emg_unit.py 中的所有补丁逻辑：
  - _patch_pyshimmer_readloop  防止 queue.Empty 崩溃
  - _patch_get_inquiry         绕过固件 Inquiry Bug
  - set_exg_register           强制 MUX=NORMAL
  - IMUCalibration             从设备读取出厂校准
"""

import logging
import math
import threading
import time
from typing import Callable, Optional

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)

try:
    from pyshimmer import ShimmerBluetooth, EChannelType
    from pyshimmer.dev.channels import ESensorGroup, ChDataTypeAssignment
    _PYSHIMMER = True
except ImportError:
    _PYSHIMMER = False
    logger.warning("pyshimmer 未安装，EMG 设备不可用")


# ── 常量 ──────────────────────────────────────────────────
BAUDRATE            = 115200
TARGET_SAMPLE_RATE  = 1000.0      # Hz
CONNECT_TIMEOUT     = 20.0
CMD_TIMEOUT         = 20.0
START_TIMEOUT       = 15.0

ACCEL_LN_SENS       = 16384.0     # counts / g
GYRO_SENS           = 65.536      # counts / (deg/s)
G_TO_MS2            = 9.80665
VREF                = 2.42        # ADS1292R 参考电压


# ── IMU 校准辅助 ──────────────────────────────────────────
class _IMUCal:
    def __init__(self, offset, sens, ali_100):
        self.offset = offset
        self.sens   = sens
        self.R = [[ali_100[r*3+c]/100.0 for c in range(3)] for r in range(3)]

    def calibrate(self, x, y, z):
        raw = [x - self.offset[0], y - self.offset[1], z - self.offset[2]]
        res = [sum(self.R[i][j] * raw[j] for j in range(3)) for i in range(3)]
        return [v / self.sens for v in res]

    @classmethod
    def default_accel(cls):
        return cls([0,0,0], ACCEL_LN_SENS, [100,0,0, 0,100,0, 0,0,100])

    @classmethod
    def default_gyro(cls):
        return cls([0,0,0], GYRO_SENS,     [100,0,0, 0,100,0, 0,0,100])


# ── 补丁函数（与 test_emg_unit.py 保持一致） ─────────────
def _patch_readloop():
    """防止 queue.Empty 导致读循环崩溃"""
    from queue import Empty
    from pyshimmer.serial_base import ReadAbort
    _orig = ShimmerBluetooth._run_readloop

    def _patched(self):
        try:
            while True:
                try:
                    self._bluetooth.process_single_input_event()
                except Empty:
                    try:
                        self._bluetooth._serial.read_byte()
                    except Exception:
                        pass
                except ReadAbort:
                    raise
                except Exception:
                    pass
        except ReadAbort:
            pass

    ShimmerBluetooth._run_readloop = _patched


def _patch_inquiry(shimmer, fs: float):
    """绕过 Shimmer3R 固件的 Inquiry Bug（返回 n_ch=0）"""
    import types
    channels = [
        EChannelType.ACCEL_LN_X, EChannelType.ACCEL_LN_Y, EChannelType.ACCEL_LN_Z,
        EChannelType.GYRO_MPU9150_X, EChannelType.GYRO_MPU9150_Y, EChannelType.GYRO_MPU9150_Z,
        EChannelType.EXG_ADS1292R_1_STATUS,
        EChannelType.EXG_ADS1292R_1_CH1_24BIT,
        EChannelType.EXG_ADS1292R_1_CH2_24BIT,
    ]
    def patched(self):
        return (fs, 1, channels)
    shimmer.get_inquiry = types.MethodType(patched, shimmer)


def _safe_cmd(shimmer, method: str, args=(), timeout=CMD_TIMEOUT):
    """带超时的 pyshimmer 命令"""
    result, done = {}, threading.Event()
    def _do():
        try:
            result["v"] = getattr(shimmer, method)(*args)
        except Exception as e:
            result["e"] = str(e)
        finally:
            done.set()
    threading.Thread(target=_do, daemon=True).start()
    if not done.wait(timeout):
        raise TimeoutError(f"{method} 超时（>{timeout:.0f}s）")
    if "e" in result:
        raise RuntimeError(f"{method} 失败：{result['e']}")
    return result.get("v")


# ─────────────────────────────────────────────────────────
class ShimmerEMGDevice:
    """
    Shimmer3 ExG EMG 设备管理类。
    接口与 ShimmerGSRDevice 一致，可直接替换。
    """

    def __init__(self, config: dict = None):
        self._config     = config or {}
        self._shimmer    = None
        self._ser        = None
        self._connected  = False
        self._streaming  = False
        self._callback: Optional[Callable] = None
        self._status_fn: Optional[Callable] = None

        self._accel_cal  = _IMUCal.default_accel()
        self._gyro_cal   = _IMUCal.default_gyro()
        self._emg_mv_lsb = (VREF / (4 * (2**23 - 1))) * 1000.0   # mV/LSB，默认 gain=4

        if _PYSHIMMER:
            _patch_readloop()

    def set_status_callback(self, fn: Callable):
        """注入状态回调，_configure() 阶段会通过它报告进度"""
        self._status_fn = fn

    def _status(self, msg: str):
        if self._status_fn:
            try:
                self._status_fn(msg)
            except Exception:
                pass
        logger.info(msg)

    # ── 工具 ─────────────────────────────────────────────
    @staticmethod
    def _list_com_ports():
        return [p.device for p in serial.tools.list_ports.comports()]

    @property
    def is_connected(self):
        return self._connected

    # ── 连接 ─────────────────────────────────────────────
    def connect(self, port: str) -> bool:
        """尝试连接指定 COM 口，成功返回 True"""
        if not _PYSHIMMER:
            logger.error("pyshimmer 未安装")
            return False
        try:
            result, done = {}, threading.Event()

            def _do():
                try:
                    ser = serial.Serial(port, baudrate=BAUDRATE, timeout=None)
                    time.sleep(0.4)
                    ser.reset_input_buffer()
                    time.sleep(0.1)
                    shim = ShimmerBluetooth(ser)
                    shim.initialize()
                    result["shimmer"] = shim
                    result["ser"]     = ser
                except Exception as e:
                    result["error"] = str(e)
                    try:
                        if "ser" in result:
                            result["ser"].close()
                    except Exception:
                        pass
                finally:
                    done.set()

            threading.Thread(target=_do, daemon=True).start()
            if not done.wait(CONNECT_TIMEOUT):
                logger.error(f"[EMG] {port} 连接超时（>{CONNECT_TIMEOUT:.0f}s）")
                return False

            if "error" in result:
                logger.error(f"[EMG] {port} 连接失败：{result['error']}")
                return False

            self._shimmer = result["shimmer"]
            self._ser     = result["ser"]

            _patch_inquiry(self._shimmer, TARGET_SAMPLE_RATE)

            self._connected = True
            logger.info(f"[EMG] ✓ 已连接：{port}")
            return True

        except Exception as e:
            logger.error(f"[EMG] connect 异常：{e}")
            return False

    def _configure(self):
        """配置传感器、采样率、ADS1292R 寄存器，读取校准数据。
        允许部分步骤失败——连接本身仍然有效。
        """
        actual_rate = TARGET_SAMPLE_RATE

        self._status("    [EMG 配置 1/4] 设置传感器...")
        sensors = [ESensorGroup.EXG1_24BIT, ESensorGroup.ACCEL_LN, ESensorGroup.GYRO]
        for attempt in range(2):
            try:
                _safe_cmd(self._shimmer, "set_sensors", (sensors,))
                break
            except Exception as e:
                if attempt == 0:
                    self._status(f"    [EMG] set_sensors 第1次失败（{e}），2s 后重试...")
                    time.sleep(2)
                else:
                    self._status(f"    [EMG] set_sensors 重试仍失败（{e}），跳过")

        self._status("    [EMG 配置 2/4] 设置采样率...")
        try:
            _safe_cmd(self._shimmer, "set_sampling_rate", (TARGET_SAMPLE_RATE,))
            actual_rate = _safe_cmd(self._shimmer, "get_sampling_rate") or TARGET_SAMPLE_RATE
            self._status(f"    [EMG] 采样率：{actual_rate:.1f} Hz")
        except Exception as e:
            self._status(f"    [EMG] 采样率设置失败（{e}），使用默认值")

        self._status("    [EMG 配置 3/4] 读取校准数据...")
        try:
            cal = _safe_cmd(self._shimmer, "get_all_calibration")
            if cal:
                self._accel_cal = _IMUCal(
                    cal.get_offset_bias(0), ACCEL_LN_SENS, cal.get_ali_mat(0))
                self._gyro_cal  = _IMUCal(
                    cal.get_offset_bias(2), GYRO_SENS,     cal.get_ali_mat(2))
        except Exception as e:
            self._status(f"    [EMG] 校准数据读取失败（{e}），使用默认值")

        self._status("    [EMG 配置 4/4] 配置 ADS1292R 寄存器...")
        try:
            exg = _safe_cmd(self._shimmer, "get_exg_register", (0,))
            if exg:
                raw = bytearray(exg.binary)
                raw[1] = 0xA0
                raw[3] = (raw[3] & 0x70) | 0x00
                raw[4] = (raw[4] & 0x70) | 0x00
                _safe_cmd(self._shimmer, "set_exg_register", (0, 0, bytes(raw)))
                gain = exg.ch1_gain or 4
                self._emg_mv_lsb = (VREF / (gain * (2**23 - 1))) * 1000.0
                self._status(f"    [EMG] ADS1292R 配置完成，增益={gain}")
        except Exception as e:
            self._status(f"    [EMG] ExG 寄存器配置失败（{e}），使用默认值")

        _patch_inquiry(self._shimmer, actual_rate)

    # ── 流式采集 ─────────────────────────────────────────
    def start_streaming(self, callback: Callable):
        """启动数据流，每帧调用 callback(data_dict)"""
        if not self._connected or not self._shimmer:
            raise RuntimeError("未连接设备")
        self._callback = callback
        self._streaming = True
        self._shimmer.add_stream_callback(self._on_packet)

        err, done = {}, threading.Event()
        def _do():
            try:
                self._shimmer.start_streaming()
            except Exception as e:
                err["msg"] = str(e)
            finally:
                done.set()

        threading.Thread(target=_do, daemon=True).start()
        if not done.wait(START_TIMEOUT):
            raise TimeoutError("start_streaming 超时")
        if "msg" in err:
            raise RuntimeError(f"start_streaming 失败：{err['msg']}")
        logger.info("[EMG] 数据流已启动")

    def _on_packet(self, pkt):
        """pyshimmer 回调 → 解析 → 调用上层 callback"""
        if not self._streaming or not self._callback:
            return
        try:
            ts = time.time()

            def _get(ch):
                try:
                    return float(pkt[ch])
                except Exception:
                    return 0.0

            # 原始值
            ax_r = _get(EChannelType.ACCEL_LN_X)
            ay_r = _get(EChannelType.ACCEL_LN_Y)
            az_r = _get(EChannelType.ACCEL_LN_Z)
            gx_r = _get(EChannelType.GYRO_MPU9150_X)
            gy_r = _get(EChannelType.GYRO_MPU9150_Y)
            gz_r = _get(EChannelType.GYRO_MPU9150_Z)
            c1_r = _get(EChannelType.EXG_ADS1292R_1_CH1_24BIT)
            c2_r = _get(EChannelType.EXG_ADS1292R_1_CH2_24BIT)
            stat = _get(EChannelType.EXG_ADS1292R_1_STATUS)

            # 校准
            ax, ay, az = self._accel_cal.calibrate(ax_r, ay_r, az_r)
            gx, gy, gz = self._gyro_cal.calibrate(gx_r, gy_r, gz_r)
            ch1_mv = c1_r * self._emg_mv_lsb
            ch2_mv = c2_r * self._emg_mv_lsb

            self._callback({
                "timestamp":   ts,
                "emg_ch1_mv":  ch1_mv,
                "emg_ch2_mv":  ch2_mv,
                "accel_x_ms2": ax * G_TO_MS2,
                "accel_y_ms2": ay * G_TO_MS2,
                "accel_z_ms2": az * G_TO_MS2,
                "gyro_x_dps":  gx,
                "gyro_y_dps":  gy,
                "gyro_z_dps":  gz,
                "emg_status":  int(stat),
            })
        except Exception as e:
            logger.debug(f"[EMG] 数据包解析错误：{e}")

    def stop_streaming(self):
        """停止数据流"""
        self._streaming = False
        if self._shimmer:
            done = threading.Event()
            def _do():
                try:
                    self._shimmer.stop_streaming()
                except Exception:
                    pass
                finally:
                    done.set()
            threading.Thread(target=_do, daemon=True).start()
            done.wait(timeout=4.0)
        logger.info("[EMG] 数据流已停止")

    def disconnect(self):
        """断开连接并释放资源"""
        self.stop_streaming()
        if self._shimmer:
            done = threading.Event()
            def _do():
                try:
                    self._shimmer.shutdown()
                except Exception:
                    pass
                finally:
                    done.set()
            threading.Thread(target=_do, daemon=True).start()
            done.wait(timeout=3.0)
            self._shimmer = None
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
        self._connected = False
        logger.info("[EMG] 已断开连接")

    def get_device_info(self) -> dict:
        """返回设备信息字典"""
        return {
            "type":        "Shimmer3 ExG EMG",
            "sampling_rate": TARGET_SAMPLE_RATE,
            "channels":    ["EMG_CH1", "EMG_CH2", "Accel_X/Y/Z", "Gyro_X/Y/Z"],
        }
