"""
Shimmer EMG 单元测试脚本  v6
================================
修复记录：
  v1 → 连接超时改用线程+Event（避免非响应端口卡死）
  v2 → 数据接收改用 add_stream_callback 回调（pyshimmer 1.0.0 正确API）
       stop_streaming/shutdown 用线程+超时包裹
  v3 → monkey-patch _run_readloop 防止 queue.Empty 崩溃；
       连接前 reset_input_buffer 冲洗串口；start_streaming 加超时
  v4 → 主动调用 set_sensors / set_sampling_rate 配置设备（ConsensysPRO
       断开后设备恢复默认状态，否则只有 Timestamp）；
       自动发现所有实际通道；排除 Battery 和 ECG (Chip-2)
  v5 → 修复超时：configure_for_emg 移出连接限时线程，每条命令独立超时；
       新增陀螺仪（Gyro）：用于运动伪迹标记 + MDD 精神运动迟滞量化
  v6 → 双 Bug 根本修复：
       Bug-1（包解析错位）：monkey-patch shimmer.get_inquiry() 返回正确通道列表，
         彻底解决 Shimmer3R 固件 Inquiry 响应返回 n_ch=0 导致包错位/假采样率问题。
       Bug-2（ADS1292R MUX 未配置）：读取 ExG 寄存器后仅修改 MUX 位为 NORMAL
         （0x00）并关闭测试信号（CONFIG2[2]=0），确保芯片采集真实电极信号。
       新增校准：从设备读取出厂校准数据，将 Accel→m/s²、Gyro→deg/s、EMG→mV，
         CSV 列名与 Consensys 格式对齐。
       采样率升级：512→1000 Hz（符合 SENIAM 表面 EMG 标准）。

已启用通道：
  Timestamp          设备内部时间戳（总是存在）
  Low-Noise Accel X/Y/Z  内置低噪声加速度计（精细运动参考）
  Gyro X/Y/Z         陀螺仪角速度（运动伪迹检测 + MDD 运动量化）
  EMG CH1 (24-bit)   主 EMG 通道 → μV 换算
  EMG CH2 (24-bit)   参考/第二肌群 → μV 换算
  ExG Status         ADS1292R 电极接触状态字节

已排除：
  Battery            无需
  ECG (Chip-2全部)   无需
  Wide-Range Accel   与 Low-Noise 重叠，量程过大反而噪声更高
  External ADC       未接外部传感器，为悬空随机噪声

使用：
  python tests/test_emg_unit.py --port COM7
  python tests/test_emg_unit.py --port COM7 --duration 60
  python tests/test_emg_unit.py --port COM7 --duration 0     # 无限，Ctrl+C 停
  python tests/test_emg_unit.py --port COM7 --query          # 仅查询设备信息
"""

import argparse
import csv
import math
import os
import queue
import sys
import time
import threading
from collections import deque
from datetime import datetime

import serial
import serial.tools.list_ports

try:
    from pyshimmer import ShimmerBluetooth, EChannelType
    from pyshimmer.dev.channels import ESensorGroup
except ImportError:
    print("❌ pyshimmer 未安装：pip install pyshimmer")
    sys.exit(1)


# ── pyshimmer 1.0.0 兼容性补丁 ─────────────────────────────────────────────
#
# 问题：BluetoothRequestHandler.process_single_input_event() 的 else 分支对
#   任何非已知字节调用 _process_resp_from_queue()，命令队列空时抛 queue.Empty，
#   读循环线程崩溃 → start_streaming() 永久卡死。
# 修复：捕获 Empty，消耗1字节后继续循环，保持读线程存活。
#
def _patch_pyshimmer_readloop():
    from queue import Empty as _QE
    from pyshimmer.serial_base import ReadAbort

    _orig = ShimmerBluetooth._run_readloop

    def _patched(self):
        try:
            while True:
                try:
                    self._bluetooth.process_single_input_event()
                except _QE:
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


_patch_pyshimmer_readloop()


# ── 常量 ──────────────────────────────────────────────────────────

BAUDRATE              = 115200
RMS_WINDOW_MS         = 100       # RMS 滑动窗口（毫秒）
PRINT_INTERVAL        = 0.5       # 控制台刷新间隔（秒）
CONNECT_TIMEOUT       = 12.0      # serial+initialize 限时（秒）
CMD_TIMEOUT           = 10.0      # 单条 pyshimmer 命令超时（秒）
START_STREAM_TIMEOUT  = 10.0      # start_streaming() 超时（秒）

# 目标采样率（Hz）
# SENIAM 推荐：表面 EMG 至少 1000 Hz（奈奎斯特：EMG 有效频带 20~500 Hz）
# ADS1292R 支持档位：125 / 250 / 500 / 1000 / 2000 / 4000 / 8000 Hz
TARGET_SAMPLE_RATE = 1000.0

# ── Shimmer3 出厂默认校准参数（无法从设备读取时的回退值） ────────
# AllCalibration sensor index：0=Accel_LN, 1=Accel_WR, 2=Gyro, 3=Mag
# Shimmer3 alignment 矩阵按 ×100 整数存储（实际值 = stored/100）
# Accel_LN (Kionix KXRB5-2042 ±2g): sensitivity=16384 counts/g
# Gyro (MPU9150 ±500 dps):          sensitivity=65.536 counts/(deg/s)
ACCEL_LN_SENS_DEFAULT  = 16384.0   # counts / g
GYRO_SENS_DEFAULT      = 65.536    # counts / (deg/s)
G_TO_MS2               = 9.80665   # 1g → m/s²


# ── 校准辅助类 ────────────────────────────────────────────────────
class IMUCalibration:
    """
    Shimmer 三轴传感器校准：calibrated = (R/100) @ (raw - offset) / sensitivity
    其中 R 是对齐矩阵（stored ×100），sensitivity 为标量或3元素列表。
    """
    def __init__(self, offset, sensitivity_scalar, ali_mat_100):
        self.offset   = offset                          # [ox, oy, oz]
        self.sens     = sensitivity_scalar              # 单一灵敏度（counts/unit）
        # alignment matrix row-major, stored as int×100 → actual = /100
        R_raw = ali_mat_100
        self.R = [[R_raw[r*3+c]/100.0 for c in range(3)] for r in range(3)]

    def calibrate(self, raw_x, raw_y, raw_z):
        raw = [raw_x - self.offset[0],
               raw_y - self.offset[1],
               raw_z - self.offset[2]]
        result = [0.0, 0.0, 0.0]
        for i in range(3):
            for j in range(3):
                result[i] += self.R[i][j] * raw[j]
        return [v / self.sens for v in result]

    @classmethod
    def from_all_calibration(cls, all_cal, sens_num, sens_scalar):
        """从设备校准数据构建，sens_scalar 为该传感器的灵敏度（counts/unit）"""
        offset  = all_cal.get_offset_bias(sens_num)
        ali_mat = all_cal.get_ali_mat(sens_num)
        # 用传入的 sens_scalar 覆盖设备存储的灵敏度（单位换算更可靠）
        return cls(offset, sens_scalar, ali_mat)

    @classmethod
    def identity(cls, sens_scalar):
        """无校准回退：零偏置 + 单位矩阵 + 给定灵敏度"""
        return cls([0, 0, 0], sens_scalar, [100,0,0, 0,100,0, 0,0,100])

# ── 传感器配置 ────────────────────────────────────────────────────
REQUIRED_SENSORS = [
    ESensorGroup.EXG1_24BIT,   # EMG Chip-1，24-bit 精度
    ESensorGroup.ACCEL_LN,     # 低噪声三轴加速度计
    ESensorGroup.GYRO,         # 陀螺仪：运动伪迹检测 + MDD 精神运动迟滞量化
]

# 可选追加（取消注释即可启用）
EXTRA_SENSORS: list = [
    # ESensorGroup.ACCEL_WR,    # 宽量程加速度计（与 ACCEL_LN 重叠，不推荐）
    # ESensorGroup.CH_A7,       # External ADC 7（接外部 PPG 等才有意义）
]

# ── 数据包通道定义（顺序必须与 Shimmer3 固件包格式一致） ──────────
#
# 包顺序由 BtChannelsByIndex 决定（通过 InquiryCommand 响应验证）：
#   index 0-2:  ACCEL_LN_X/Y/Z
#   index 10-12: GYRO_MPU9150_X/Y/Z
#   index 29:   EXG_ADS1292R_1_STATUS
#   index 30-31: EXG_ADS1292R_1_CH1/CH2_24BIT
# TIMESTAMP 总是由 pyshimmer 自动前置（不占设备 index）
#
# 注意：若修改 REQUIRED_SENSORS，此列表也需同步更新！
STREAM_CHANNELS = [
    EChannelType.TIMESTAMP,                   # pyshimmer 自动前置
    EChannelType.ACCEL_LN_X,                  # BtChannelsByIndex 0
    EChannelType.ACCEL_LN_Y,                  # 1
    EChannelType.ACCEL_LN_Z,                  # 2
    EChannelType.GYRO_MPU9150_X,              # 10
    EChannelType.GYRO_MPU9150_Y,              # 11
    EChannelType.GYRO_MPU9150_Z,              # 12
    EChannelType.EXG_ADS1292R_1_STATUS,       # 29
    EChannelType.EXG_ADS1292R_1_CH1_24BIT,    # 30
    EChannelType.EXG_ADS1292R_1_CH2_24BIT,    # 31
]

# 原始通道名（解析数据包用）
STREAM_CHANNEL_NAMES = [
    "Shimmer_Timestamp",
    "Accel_LN_X_RAW", "Accel_LN_Y_RAW", "Accel_LN_Z_RAW",
    "Gyro_X_RAW",     "Gyro_Y_RAW",     "Gyro_Z_RAW",
    "EMG_Status_Chip1_no_units",
    "EMG_CH1_Chip1_RAW", "EMG_CH2_Chip1_RAW",
]

# CSV 最终输出列（校准后，与 Consensys 格式对齐）
CSV_COLUMNS = [
    "PC_Timestamp_Unix_ms",      # PC 时间戳（毫秒，与 Consensys 一致）
    "Shimmer_Timestamp",         # 设备内部时间戳
    "Accel_LN_X_m/s^2",         # 低噪声加速度计 X（校准后，m/s²）
    "Accel_LN_Y_m/s^2",
    "Accel_LN_Z_m/s^2",
    "Gyro_X_deg/s",              # 陀螺仪（校准后，deg/s）
    "Gyro_Y_deg/s",
    "Gyro_Z_deg/s",
    "EMG_Status_Chip1_no_units", # ADS1292R 状态字节（DRDY 等）
    "EMG_CH1_Chip1_mV",          # EMG CH1（校准后，mV）
    "EMG_CH2_Chip1_mV",          # EMG CH2（校准后，mV）
    "EMG_CH1_RMS_mV",            # CH1 RMS（100ms 滑动窗口）
    "EMG_CH2_RMS_mV",
]

EMG_CH1_TYPE = EChannelType.EXG_ADS1292R_1_CH1_24BIT
EMG_CH2_TYPE = EChannelType.EXG_ADS1292R_1_CH2_24BIT

# ADS1292R 24-bit → μV 换算  (Vref=2.42V, gain 由 ExG 寄存器决定)
# GAIN_MAP: 0→6, 1→1, 2→2, 3→3, 4→4, 5→8, 6→12
def make_scale_uv(gain: int) -> float:
    return (2.42 / (gain * (2**23 - 1))) * 1_000_000


# ── 连接 ──────────────────────────────────────────────────────────

def scan_ports() -> list:
    return [p.device for p in serial.tools.list_ports.comports()]


def safe_cmd(shimmer, method_name: str, args: tuple = (), timeout: float = CMD_TIMEOUT):
    """
    带独立超时的 pyshimmer 命令包装。
    pyshimmer 内部的 _process_and_wait() 没有超时，
    用此函数防止单条命令因设备无响应而永久阻塞。
    """
    result = {}
    done   = threading.Event()

    def _do():
        try:
            fn = getattr(shimmer, method_name)
            result["value"] = fn(*args)
        except Exception as e:
            result["error"] = str(e)
        finally:
            done.set()

    t = threading.Thread(target=_do, daemon=True)
    t.start()

    if not done.wait(timeout):
        raise TimeoutError(f"{method_name}() 超时（>{timeout:.0f}s），设备无响应")
    if "error" in result:
        raise RuntimeError(f"{method_name}() 失败：{result['error']}")
    return result.get("value")


def configure_for_emg(shimmer):
    """
    配置 Shimmer 设备进入 EMG 采集模式。
    返回 (actual_rate, accel_cal, gyro_cal, emg_scale_mv) 元组。
    在 initialize() 之后、start_streaming() 之前调用。
    """
    sensors = REQUIRED_SENSORS + EXTRA_SENSORS
    print(f"  → 启用传感器：{[s.name for s in sensors]}")
    safe_cmd(shimmer, "set_sensors", (sensors,))

    safe_cmd(shimmer, "set_sampling_rate", (TARGET_SAMPLE_RATE,))
    actual_rate = safe_cmd(shimmer, "get_sampling_rate") or TARGET_SAMPLE_RATE
    print(f"  → 采样率：{actual_rate:.1f} Hz")

    # 读取设备校准数据（用于 Accel/Gyro 单位转换）
    accel_cal = IMUCalibration.identity(ACCEL_LN_SENS_DEFAULT)
    gyro_cal  = IMUCalibration.identity(GYRO_SENS_DEFAULT)
    try:
        all_cal = safe_cmd(shimmer, "get_all_calibration")
        if all_cal is not None:
            accel_cal = IMUCalibration.from_all_calibration(all_cal, 0, ACCEL_LN_SENS_DEFAULT)
            gyro_cal  = IMUCalibration.from_all_calibration(all_cal, 2, GYRO_SENS_DEFAULT)
            print(f"  → 已读取设备校准数据")
            print(f"     Accel_LN offset={accel_cal.offset}")
            print(f"     Gyro     offset={gyro_cal.offset}")
    except Exception as e:
        print(f"  → 校准数据读取失败（{e}），使用出厂默认值")

    # ── 【核心修复 Bug-2：ADS1292R ExG 寄存器配置】 ──────────────────
    #
    # set_sensors(EXG1_24BIT) 只告诉 Shimmer 固件"打开 ExG 芯片供电"，
    # 但不配置 ADS1292R 内部的输入多路复用器（MUX）。
    # 芯片复位后 CH1SET/CH2SET 的 MUX 位默认为 0x05 = TEST_SIGNAL（内部测试信号）
    # 或 0x01 = SHORTED（短路）→ 采集到的全是芯片内部测试波形或饱和值，
    # 而不是真实的电极 EMG 信号。
    #
    # 修复：读取当前寄存器值，只修改关键位：
    #   1. CONFIG2[2] INT_TEST = 0   → 关闭内部测试信号
    #   2. CH1SET[7] PD1 = 0        → 通道1 上电（非省电模式）
    #   3. CH1SET[3:0] MUX = 0x0   → NORMAL 电极输入
    #   4. CH2SET 同上
    #   增益位 CH1SET[6:4] 保持 ConsensysPRO 设置的值不变。
    #
    emg_scale_mv = make_scale_uv(4) / 1000.0   # 默认 gain=4
    try:
        exg1 = safe_cmd(shimmer, "get_exg_register", (0,))
        if exg1 is not None:
            from pyshimmer.dev.exg import ExGMux
            gain = exg1.ch1_gain if exg1.ch1_gain > 0 else 4
            emg_scale_mv = make_scale_uv(gain) / 1000.0

            # 读出当前 10 字节原始数据
            raw = bytearray(exg1.binary)

            # Byte 1 = CONFIG2：关闭内部测试信号（bit2 = 0），保持参考缓冲开启
            raw[1] = 0xA0   # 10100000: REFBUF ON, VREF=2.42V, CLK_EN=0, INT_TEST=0

            # Byte 3 = CH1SET：保留增益位[6:4]，清零 PD[7] 和 MUX[3:0]
            gain_bits = raw[3] & 0x70   # 保留 bit6:4（增益）
            raw[3] = gain_bits | 0x00   # PD=0（上电），MUX=0000（NORMAL）

            # Byte 4 = CH2SET：同上
            gain_bits2 = raw[4] & 0x70
            raw[4] = gain_bits2 | 0x00  # PD=0, MUX=0000（NORMAL）

            # 写回全部 10 字节
            safe_cmd(shimmer, "set_exg_register", (0, 0, bytes(raw)))

            # 回读确认
            exg1_check = safe_cmd(shimmer, "get_exg_register", (0,))
            mux1 = exg1_check.ch1_mux.name if exg1_check else "未知"
            mux2 = exg1_check.ch2_mux.name if exg1_check else "未知"
            print(f"  → ExG Chip-1 配置完成：增益={gain}  "
                  f"CH1-MUX={mux1}  CH2-MUX={mux2}  "
                  f"换算={emg_scale_mv*1000:.5f} μV/LSB")
            if mux1 != "NORMAL" or mux2 != "NORMAL":
                print(f"  ⚠ 警告：MUX 不是 NORMAL！数据可能仍为测试信号")
        else:
            print(f"  → ExG 寄存器读取失败，使用默认增益4")
    except Exception as ex:
        print(f"  → ExG 寄存器配置失败（{ex}），使用默认增益4")

    return actual_rate, accel_cal, gyro_cal, emg_scale_mv


def query_device_info(shimmer):
    """查询并打印设备基本信息（--query 模式）"""
    try:
        fw_type, fw_ver = safe_cmd(shimmer, "get_firmware_version")
        print(f"\n  固件类型：{fw_type.name}  版本：{fw_ver}")
    except Exception as e:
        print(f"  固件查询失败：{e}")

    try:
        sr = safe_cmd(shimmer, "get_sampling_rate")
        print(f"  当前采样率：{sr:.1f} Hz")
    except Exception as e:
        print(f"  采样率查询失败：{e}")

    for chip_id, label in [(0, "EMG"), (1, "ECG")]:
        try:
            reg = safe_cmd(shimmer, "get_exg_register", (chip_id,))
            print(f"  ExG Chip-{chip_id+1} ({label})："
                  f"gain_CH1={reg.ch1_gain}  gain_CH2={reg.ch2_gain}  "
                  f"data_rate={reg.data_rate} Hz")
        except Exception as e:
            print(f"  ExG Chip-{chip_id+1} 查询失败：{e}")


def try_connect(port: str):
    """
    第一阶段：仅完成 serial + initialize()，受 CONNECT_TIMEOUT 限时。
    传感器配置（configure_for_emg）在此之后单独执行，每条命令有独立超时。
    """
    result = {}
    done   = threading.Event()

    def _do():
        _ser = None
        try:
            _ser = serial.Serial(port, baudrate=BAUDRATE, timeout=None)
            time.sleep(0.4)
            _ser.reset_input_buffer()   # 冲洗残留数据（防止 queue.Empty 崩溃）
            time.sleep(0.1)

            shim = ShimmerBluetooth(_ser)
            shim.initialize()

            result["shimmer"] = shim
            result["ser"]     = _ser
        except Exception as e:
            result["error"] = str(e)
            if _ser and _ser.is_open:
                try:
                    _ser.close()
                except Exception:
                    pass
        finally:
            done.set()

    t = threading.Thread(target=_do, daemon=True)
    t.start()

    if not done.wait(CONNECT_TIMEOUT):
        print(f"  ✗ {port} 超时（>{CONNECT_TIMEOUT:.0f}s），跳过")
        return None, None

    if "shimmer" in result:
        print(f"  ✓ 已连接：{port}")
        return result["shimmer"], result["ser"]
    else:
        print(f"  ✗ {port} 失败：{result.get('error', '未知错误')}")
        return None, None


def _patch_get_inquiry(shimmer):
    """
    【核心修复 Bug-1：get_inquiry() 返回空通道】

    Shimmer3R 固件的 INQUIRY 响应在 set_sensors() 后仍返回 n_ch=0，
    导致 pyshimmer 包解析器只识别 TIMESTAMP 通道：
      - 每个真实数据包（22字节有效载荷）被解析为多个"只含 Timestamp"的伪包
      - 采样率虚高到 ~1200 Hz，所有 Accel/Gyro/EMG 数据全部丢失

    修复方案：
      用 types.MethodType 猴子补丁 shimmer 实例的 get_inquiry()，
      让它不发任何串口命令，直接返回我们已知的正确通道列表。
      start_streaming() 调用 get_inquiry() → get_data_types() → set_stream_types()，
      整条正常路径依然走通，只是 Inquiry 这步不再问设备。
    """
    import types

    # get_inquiry 返回值格式：(sampling_rate, buf_size, [channels without TIMESTAMP])
    # TIMESTAMP 由 get_data_types() 自动前置，不要在这里列出
    expected_channels = [
        EChannelType.ACCEL_LN_X, EChannelType.ACCEL_LN_Y, EChannelType.ACCEL_LN_Z,
        EChannelType.GYRO_MPU9150_X, EChannelType.GYRO_MPU9150_Y, EChannelType.GYRO_MPU9150_Z,
        EChannelType.EXG_ADS1292R_1_STATUS,
        EChannelType.EXG_ADS1292R_1_CH1_24BIT,
        EChannelType.EXG_ADS1292R_1_CH2_24BIT,
    ]

    def patched_get_inquiry(self):
        return (TARGET_SAMPLE_RATE, 1, expected_channels)

    shimmer.get_inquiry = types.MethodType(patched_get_inquiry, shimmer)
    print("  → get_inquiry() 已补丁（绕过固件 Bug）")


def safe_start_streaming(shimmer):
    """
    start_streaming() 带超时包装。
    调用前必须先执行 _patch_get_inquiry(shimmer)。
    """
    err  = {}
    done = threading.Event()

    def _do():
        try:
            shimmer.start_streaming()
        except Exception as e:
            err["msg"] = str(e)
        finally:
            done.set()

    t = threading.Thread(target=_do, daemon=True)
    t.start()

    if not done.wait(START_STREAM_TIMEOUT):
        raise TimeoutError(
            f"start_streaming() 超时（>{START_STREAM_TIMEOUT:.0f}s）\n"
            "  可能原因：设备读循环崩溃或设备未响应。请重启设备后重试。"
        )
    if "msg" in err:
        raise RuntimeError(f"start_streaming() 失败：{err['msg']}")


def safe_stop(shimmer, label: str, timeout: float = 4.0):
    """带超时的 shimmer 命令，避免设备无响应时卡死"""
    done = threading.Event()

    def _do():
        try:
            fn = getattr(shimmer, label, None)
            if fn:
                fn()
        except Exception:
            pass
        finally:
            done.set()

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    if not done.wait(timeout):
        print(f"  ⚠ {label}() 超时（>{timeout:.0f}s），跳过")


# ── 采集器 ────────────────────────────────────────────────────────

class EMGCollector:

    def __init__(self, shimmer, out_csv: str, duration: int,
                 emg_scale_mv: float,
                 accel_cal: IMUCalibration,
                 gyro_cal:  IMUCalibration,
                 viewer=None):
        self.shimmer      = shimmer
        self.out_csv      = out_csv
        self.duration     = duration
        self._emg_mv      = emg_scale_mv   # mV/LSB
        self._accel_cal   = accel_cal
        self._gyro_cal    = gyro_cal
        self._viewer      = viewer         # 可选 RealtimeEMGTab 或 EMGViewerWindow

        self._pkt_queue  = queue.Queue(maxsize=50_000)
        self._n_samples  = 0
        self._start_time = 0.0
        self._last_print = 0.0

        # RMS 缓冲（单位：mV）
        win = max(1, int(TARGET_SAMPLE_RATE * RMS_WINDOW_MS / 1000))
        self._buf1 = deque(maxlen=win)
        self._buf2 = deque(maxlen=win)

        # 信号质量统计（mV）
        self._ch1_min = float('inf');  self._ch1_max = float('-inf')
        self._ch2_min = float('inf');  self._ch2_max = float('-inf')

    # ── 回调（在 pyshimmer 内部读线程调用） ──
    def _on_packet(self, pkt):
        try:
            self._pkt_queue.put_nowait(pkt)
        except queue.Full:
            pass

    # ── 主循环 ───────────────────────────────
    def run(self):
        self._start_time = time.time()
        self._last_print  = self._start_time

        print(f"\n{'='*60}")
        print(f"  开始采集 EMG 数据")
        print(f"  时长：{'无限（Ctrl+C 停止）' if self.duration == 0 else f'{self.duration} 秒'}")
        print(f"  采集通道：{STREAM_CHANNEL_NAMES}")
        print(f"  保存：{self.out_csv}")
        print(f"{'='*60}\n")

        self.shimmer.add_stream_callback(self._on_packet)
        print("  正在启动数据流（强制包格式）...", end="", flush=True)
        safe_start_streaming(self.shimmer)
        print(" ✓\n")

        with open(self.out_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction='ignore')
            writer.writeheader()
            f.flush()
            print(f"  表头写入完成，开始采集...\n")

            try:
                while True:
                    elapsed = time.time() - self._start_time
                    if self.duration > 0 and elapsed >= self.duration:
                        print(f"\n✓ 达到设定时长 {self.duration}s，停止")
                        break

                    try:
                        pkt = self._pkt_queue.get(timeout=0.5)
                    except queue.Empty:
                        if self._n_samples == 0:
                            print(f"\r  等待首个数据包... ({elapsed:.0f}s)", end="", flush=True)
                        continue

                    # 首包：打印原始值验证通道对齐
                    if self._n_samples == 0:
                        print()
                        self._validate_first_packet(pkt)

                    self._process(pkt, writer, f)

            except KeyboardInterrupt:
                print("\n\n⏹ 用户中断（Ctrl+C）")

        print("\n正在停止设备...", end="", flush=True)
        safe_stop(self.shimmer, "stop_streaming", timeout=4.0)
        safe_stop(self.shimmer, "shutdown",       timeout=3.0)
        print(" 完成")

        self._print_report()

    def _validate_first_packet(self, pkt):
        """打印首包各通道原始值，确认通道顺序对齐"""
        print("  首包通道验证：")
        for ch_type, name in zip(STREAM_CHANNELS, STREAM_CHANNEL_NAMES):
            try:
                val = pkt[ch_type]
                print(f"    {name:20s} = {val}")
            except (KeyError, Exception) as e:
                print(f"    {name:20s} ⚠ 未找到 ({e})")

    # ── 处理单个数据包 ─────────────────────────
    def _process(self, pkt, writer: csv.DictWriter, f):
        ts = time.time()
        self._n_samples += 1

        # 读取各通道原始值
        raw = {}
        for ch_type, name in zip(STREAM_CHANNELS, STREAM_CHANNEL_NAMES):
            try:
                raw[name] = pkt[ch_type]
            except (KeyError, Exception):
                raw[name] = None

        # 加速度计校准 → m/s²
        ax_raw = raw.get("Accel_LN_X_RAW") or 0
        ay_raw = raw.get("Accel_LN_Y_RAW") or 0
        az_raw = raw.get("Accel_LN_Z_RAW") or 0
        ax, ay, az = self._accel_cal.calibrate(ax_raw, ay_raw, az_raw)
        ax_ms2 = ax * G_TO_MS2
        ay_ms2 = ay * G_TO_MS2
        az_ms2 = az * G_TO_MS2

        # 陀螺仪校准 → deg/s
        gx_raw = raw.get("Gyro_X_RAW") or 0
        gy_raw = raw.get("Gyro_Y_RAW") or 0
        gz_raw = raw.get("Gyro_Z_RAW") or 0
        gx, gy, gz = self._gyro_cal.calibrate(gx_raw, gy_raw, gz_raw)

        # EMG → mV
        def to_mv(col_name):
            v = raw.get(col_name)
            return float(v) * self._emg_mv if v is not None else 0.0

        ch1_mv = to_mv("EMG_CH1_Chip1_RAW")
        ch2_mv = to_mv("EMG_CH2_Chip1_RAW")

        # RMS（mV）
        self._buf1.append(ch1_mv)
        self._buf2.append(ch2_mv)
        rms1 = math.sqrt(sum(v*v for v in self._buf1) / len(self._buf1)) if self._buf1 else 0
        rms2 = math.sqrt(sum(v*v for v in self._buf2) / len(self._buf2)) if self._buf2 else 0

        # 信号范围（mV）
        if ch1_mv != 0:
            self._ch1_min = min(self._ch1_min, ch1_mv)
            self._ch1_max = max(self._ch1_max, ch1_mv)
        if ch2_mv != 0:
            self._ch2_min = min(self._ch2_min, ch2_mv)
            self._ch2_max = max(self._ch2_max, ch2_mv)

        row = {
            "PC_Timestamp_Unix_ms":       f"{ts*1000:.3f}",
            "Shimmer_Timestamp":           raw.get("Shimmer_Timestamp"),
            "Accel_LN_X_m/s^2":           f"{ax_ms2:.6f}",
            "Accel_LN_Y_m/s^2":           f"{ay_ms2:.6f}",
            "Accel_LN_Z_m/s^2":           f"{az_ms2:.6f}",
            "Gyro_X_deg/s":               f"{gx:.6f}",
            "Gyro_Y_deg/s":               f"{gy:.6f}",
            "Gyro_Z_deg/s":               f"{gz:.6f}",
            "EMG_Status_Chip1_no_units":   raw.get("EMG_Status_Chip1_no_units"),
            "EMG_CH1_Chip1_mV":            f"{ch1_mv:.6f}",
            "EMG_CH2_Chip1_mV":            f"{ch2_mv:.6f}",
            "EMG_CH1_RMS_mV":              f"{rms1:.6f}",
            "EMG_CH2_RMS_mV":              f"{rms2:.6f}",
        }

        writer.writerow(row)

        # 推送到实时波形窗口（如有）
        if self._viewer is not None:
            try:
                self._viewer.push_sample(
                    ch1_mv, ch2_mv,
                    ax_ms2, ay_ms2, az_ms2,
                    gx, gy, gz,
                )
            except Exception:
                pass

        # 控制台刷新（仍以 μV 显示便于对比参考）
        if ts - self._last_print >= PRINT_INTERVAL:
            elapsed = ts - self._start_time
            rate = self._n_samples / elapsed if elapsed > 0 else 0
            bar = lambda v: "█" * min(20, int(v / 50)) + "░" * max(0, 20 - int(v / 50))
            print(
                f"\r  [{elapsed:6.1f}s] "
                f"样本:{self._n_samples:7d}  "
                f"实际:{rate:6.1f}Hz  "
                f"CH1 RMS:{rms1*1000:7.1f}μV {bar(rms1*1000)}  "
                f"CH2:{rms2*1000:7.1f}μV",
                end="", flush=True
            )
            self._last_print = ts
            if self._n_samples % 500 == 0:
                f.flush()

    # ── 最终报告 ──────────────────────────────
    def _print_report(self):
        elapsed = time.time() - self._start_time
        rate = self._n_samples / elapsed if elapsed > 0 else 0

        def quality_mv(vmin_mv, vmax_mv):
            amp_mv = vmax_mv - vmin_mv
            amp_uv = amp_mv * 1000
            if amp_uv <= 0:      return "⚠ 无信号（检查电极连接）"
            elif amp_uv < 50:    return f"⚠ 信号微弱  峰峰值={amp_uv:.0f}μV = {amp_mv:.3f}mV（检查贴片位置）"
            elif amp_uv < 5000:  return f"✓ 正常       峰峰值={amp_uv:.0f}μV = {amp_mv:.3f}mV"
            else:                return f"⚠ 可能有伪迹 峰峰值={amp_uv:.0f}μV = {amp_mv:.2f}mV（检查接地）"

        print(f"\n{'='*60}")
        print("  EMG 采集报告")
        print(f"{'='*60}")
        print(f"  总时长：     {elapsed:.1f} 秒")
        print(f"  总样本数：   {self._n_samples}")
        print(f"  实际采样率：{rate:.1f} Hz")
        print(f"  CSV 文件：  {self.out_csv}")
        print(f"  CSV 列格式：与 Consensys 对齐（mV / m/s² / deg/s）")
        print()
        if self._ch1_max > self._ch1_min:
            print(f"  CH1：{quality_mv(self._ch1_min, self._ch1_max)}")
        else:
            print("  CH1：⚠ 未采集到有效数据")
        if self._ch2_max > self._ch2_min:
            print(f"  CH2：{quality_mv(self._ch2_min, self._ch2_max)}")
        else:
            print("  CH2：─ 无数据（CH2 未启用或无电极）")
        print()
        print("  [信号质量参考（与 Consensys 单位一致）]")
        print("  • 静息不发力：  0.01～0.05 mV RMS  （基线）")
        print("  • 轻度握拳发力：0.05～0.5  mV RMS  （正常激活）")
        print("  • 最大自主收缩：0.5 ～5.0  mV RMS  （强激活）")
        print("  • 规律50Hz正弦波 → 接地电极没贴好")
        print(f"{'='*60}\n")


# ── 入口 ──────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Shimmer EMG 单元测试 v6")
    ap.add_argument("--port",     default=None, help="COM端口，如 COM7（不填则自动扫描）")
    ap.add_argument("--duration", type=int, default=30,
                    help="采集时长（秒），0=无限 Ctrl+C停止（默认30）")
    ap.add_argument("--query",    action="store_true",
                    help="仅查询设备信息（固件版本/采样率/ExG寄存器），不采集数据")
    ap.add_argument("--realtime", action="store_true",
                    help="同步弹出实时波形窗口（需要 PyQt5 + pyqtgraph）")
    args = ap.parse_args()

    # 输出路径
    out_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "emg_test"))
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"emg_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

    # 确定端口列表
    if args.port:
        ports = [args.port]
    else:
        ports = scan_ports()
        print(f"扫描到 {len(ports)} 个 COM 口：{ports}")
        if not ports:
            print("❌ 未发现 COM 口，请检查蓝牙配对")
            sys.exit(1)

    # 第一阶段：连接（serial + initialize，受 CONNECT_TIMEOUT 限时）
    shimmer, ser = None, None
    for i, port in enumerate(ports, 1):
        print(f"[{i}/{len(ports)}] 尝试 {port}（最多等 {CONNECT_TIMEOUT:.0f}s）...")
        shimmer, ser = try_connect(port)
        if shimmer:
            break

    if shimmer is None:
        print("\n❌ 未找到 Shimmer EMG 设备，请检查：")
        print("  1. 设备已开机（蓝灯闪烁）")
        print("  2. 已完成 Windows 蓝牙配对")
        print("  3. ConsensysPRO 已关闭（会占用 COM 口）")
        sys.exit(1)

    try:
        if args.query:
            # 仅查询模式（不配置传感器，直接读设备信息）
            query_device_info(shimmer)
        else:
            # 第二阶段：配置传感器 + ADS1292R 寄存器 + 读取校准数据
            print("  正在配置传感器...")
            actual_rate, accel_cal, gyro_cal, emg_scale_mv = configure_for_emg(shimmer)

            # 第三阶段：补丁 get_inquiry()（修复包解析 Bug）
            _patch_get_inquiry(shimmer)
            print("  ✓ 设备配置完成\n")

            # 第四阶段：采集（可选实时波形窗口）
            viewer = None
            if args.realtime:
                try:
                    import sys as _sys
                    from PyQt5.QtWidgets import QApplication
                    _app = QApplication.instance() or QApplication(_sys.argv)
                    # 导入路径需指向项目根目录
                    _proj = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
                    if _proj not in _sys.path:
                        _sys.path.insert(0, _proj)
                    from app.monitors.emg_tab import EMGViewerWindow
                    viewer = EMGViewerWindow(fs=actual_rate)
                    viewer.show()
                    print("  ✓ 实时波形窗口已启动\n")
                except Exception as _e:
                    print(f"  ⚠ 无法启动实时窗口（{_e}），继续无界面采集\n")

            collector = EMGCollector(
                shimmer, out_csv, args.duration,
                emg_scale_mv=emg_scale_mv,
                accel_cal=accel_cal,
                gyro_cal=gyro_cal,
                viewer=viewer,
            )
            if viewer:
                import sys as _sys
                from PyQt5.QtWidgets import QApplication
                # 采集在后台线程，Qt 事件循环在主线程
                import threading as _thr
                _collect_done = threading.Event()
                def _run_collect():
                    collector.run()
                    _collect_done.set()
                _thr.Thread(target=_run_collect, daemon=True).start()
                _app = QApplication.instance()
                while not _collect_done.is_set():
                    _app.processEvents()
                    time.sleep(0.02)
            else:
                collector.run()

    except (TimeoutError, RuntimeError) as e:
        print(f"\n❌ {e}")
    finally:
        safe_stop(shimmer, "shutdown", timeout=3.0)
        if ser and ser.is_open:
            try:
                ser.close()
            except Exception:
                pass
        print("串口已关闭。")


if __name__ == "__main__":
    main()
