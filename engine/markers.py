"""
Marker 管理器
负责实验事件标记的发送、记录与硬件 trigger 同步
"""

import os
import csv
import time
import logging
import threading
from typing import Dict, Optional, Callable, List

logger = logging.getLogger(__name__)

# ── Trigger 码映射（HEEG 串口 trigger 使用 1-255） ──────────
TRIGGER_CODES: Dict[str, int] = {
    # 实验级
    "EXPERIMENT_START": 1,
    "EXPERIMENT_END": 2,

    # 静息态
    "TASK_REST_START": 10,
    "TASK_REST_END": 11,
    "STIM_REST_EYES_CLOSE": 12,
    "STIM_REST_EYES_OPEN": 13,

    # Dot-probe
    "TASK_DOTPROBE_START": 20,
    "TASK_DOTPROBE_END": 21,
    "STIM_FACE_ON": 22,
    "STIM_FACE_OFF": 23,
    "STIM_PROBE_ON": 24,

    # 绘画欣赏
    "TASK_PAINTING_START": 30,
    "TASK_PAINTING_END": 31,
    "STIM_PAINT_ON": 32,
    "STIM_PAINT_OFF": 33,

    # 音乐聆听
    "TASK_MUSIC_START": 40,
    "TASK_MUSIC_END": 41,
    "STIM_MUSIC_ON": 42,
    "STIM_MUSIC_OFF": 43,

    # VR 视频
    "TASK_VIDEO_START": 50,
    "TASK_VIDEO_END": 51,
    "STIM_VIDEO_ON": 52,
    "STIM_VIDEO_OFF": 53,

    # 语音朗读
    "TASK_VOICE_READING_START": 60,
    "TASK_VOICE_READING_END": 61,
    "STIM_READING_ON": 62,
    "STIM_READING_OFF": 63,

    # 语音访谈
    "TASK_VOICE_INTERVIEW_START": 70,
    "TASK_VOICE_INTERVIEW_END": 71,
    "STIM_QUESTION_ON": 72,
    "STIM_QUESTION_OFF": 73,

    # 图像描述
    "TASK_VOICE_DESCRIBE_START": 80,
    "TASK_VOICE_DESCRIBE_END": 81,
    "STIM_IMAGE_ON": 82,
    "STIM_IMAGE_OFF": 83,

    # 被试反应
    "RESP_KEY_LEFT": 100,
    "RESP_KEY_RIGHT": 101,
    "RESP_KEY_SPACE": 102,
    "RESP_TIMEOUT": 103,

    # 休息
    "REST_BREAK_START": 200,
    "REST_BREAK_END": 201,
}

# 保留旧名称常量以兼容
class MarkerNames:
    """Marker 命名常量"""
    EXPERIMENT_START = "EXPERIMENT_START"
    EXPERIMENT_END = "EXPERIMENT_END"

    TASK_REST_START = "TASK_REST_START"
    TASK_REST_END = "TASK_REST_END"
    TASK_DOTPROBE_START = "TASK_DOTPROBE_START"
    TASK_DOTPROBE_END = "TASK_DOTPROBE_END"
    TASK_PAINTING_START = "TASK_PAINTING_START"
    TASK_PAINTING_END = "TASK_PAINTING_END"
    TASK_MUSIC_START = "TASK_MUSIC_START"
    TASK_MUSIC_END = "TASK_MUSIC_END"
    TASK_VIDEO_START = "TASK_VIDEO_START"
    TASK_VIDEO_END = "TASK_VIDEO_END"
    TASK_VOICE_READING_START = "TASK_VOICE_READING_START"
    TASK_VOICE_READING_END = "TASK_VOICE_READING_END"
    TASK_VOICE_INTERVIEW_START = "TASK_VOICE_INTERVIEW_START"
    TASK_VOICE_INTERVIEW_END = "TASK_VOICE_INTERVIEW_END"
    TASK_VOICE_DESCRIBE_START = "TASK_VOICE_DESCRIBE_START"
    TASK_VOICE_DESCRIBE_END = "TASK_VOICE_DESCRIBE_END"

    STIM_REST_EYES_OPEN = "STIM_REST_EYES_OPEN"
    STIM_REST_EYES_CLOSE = "STIM_REST_EYES_CLOSE"
    STIM_FACE_ON = "STIM_FACE_ON"
    STIM_FACE_OFF = "STIM_FACE_OFF"
    STIM_PROBE_ON = "STIM_PROBE_ON"
    STIM_PAINT_ON = "STIM_PAINT_ON"
    STIM_PAINT_OFF = "STIM_PAINT_OFF"
    STIM_MUSIC_ON = "STIM_MUSIC_ON"
    STIM_MUSIC_OFF = "STIM_MUSIC_OFF"
    STIM_VIDEO_ON = "STIM_VIDEO_ON"
    STIM_VIDEO_OFF = "STIM_VIDEO_OFF"
    STIM_READING_ON = "STIM_READING_ON"
    STIM_READING_OFF = "STIM_READING_OFF"
    STIM_QUESTION_ON = "STIM_QUESTION_ON"
    STIM_QUESTION_OFF = "STIM_QUESTION_OFF"
    STIM_IMAGE_ON = "STIM_IMAGE_ON"
    STIM_IMAGE_OFF = "STIM_IMAGE_OFF"

    RESP_KEY_LEFT = "RESP_KEY_LEFT"
    RESP_KEY_RIGHT = "RESP_KEY_RIGHT"
    RESP_KEY_SPACE = "RESP_KEY_SPACE"
    RESP_TIMEOUT = "RESP_TIMEOUT"

    REST_BREAK_START = "REST_BREAK_START"
    REST_BREAK_END = "REST_BREAK_END"


# ── 任务名 → (START marker, END marker) 的映射 ───────────────
_TASK_MARKER_MAP: Dict[str, tuple] = {
    "rest":            ("TASK_REST_START",           "TASK_REST_END"),
    "dotprobe":        ("TASK_DOTPROBE_START",       "TASK_DOTPROBE_END"),
    "painting":        ("TASK_PAINTING_START",       "TASK_PAINTING_END"),
    "music":           ("TASK_MUSIC_START",          "TASK_MUSIC_END"),
    "video":           ("TASK_VIDEO_START",          "TASK_VIDEO_END"),
    "voice_reading":   ("TASK_VOICE_READING_START",  "TASK_VOICE_READING_END"),
    "voice_interview": ("TASK_VOICE_INTERVIEW_START","TASK_VOICE_INTERVIEW_END"),
    "voice_describe":  ("TASK_VOICE_DESCRIBE_START", "TASK_VOICE_DESCRIBE_END"),
    "break":           ("REST_BREAK_START",          "REST_BREAK_END"),
}


def task_start_marker(task_name: str) -> str:
    return _TASK_MARKER_MAP.get(task_name, (f"TASK_{task_name.upper()}_START",))[0]


def task_end_marker(task_name: str) -> str:
    pair = _TASK_MARKER_MAP.get(task_name)
    if pair:
        return pair[1]
    return f"TASK_{task_name.upper()}_END"


class MarkerManager:
    """
    Marker 管理器（单例）

    功能：
    1. send_marker() → 内存日志 + CSV 写入 + 回调 + 串口 trigger
    2. set_session_dir() 后自动创建 markers CSV 文件
    3. set_trigger_port() 后启用硬件 trigger 发送
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.marker_log: List[Dict] = []
        self._log_lock = threading.Lock()
        self._callbacks: List[Callable] = []
        self._cb_lock = threading.Lock()

        self._csv_file = None
        self._csv_writer = None
        self._csv_lock = threading.Lock()

        self._trigger_serial = None

        logger.info("MarkerManager 已初始化")

    # ── 会话目录 ──────────────────────────────────────────────

    def set_session_dir(self, session_dir: str):
        """开启 CSV 实时写入，旧文件自动关闭"""
        self.close_csv()
        self.clear()
        os.makedirs(session_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(session_dir, f"markers_{ts}.csv")
        self._csv_file = open(path, "w", newline="", encoding="utf-8")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow([
            "system_time", "time_sec", "marker_name", "trigger_code", "extra",
        ])
        logger.info(f"Marker CSV → {path}")

    def close_csv(self):
        with self._csv_lock:
            if self._csv_file:
                try:
                    self._csv_file.close()
                except Exception:
                    pass
                self._csv_file = None
                self._csv_writer = None

    # ── 串口 trigger（预留，明天确认硬件后启用） ─────────────

    def set_trigger_port(self, port: str, baudrate: int = 115200):
        """连接 HEEG trigger 盒子的串口"""
        try:
            import serial
            self._trigger_serial = serial.Serial(port, baudrate, timeout=0.1)
            logger.info(f"HEEG trigger 串口已连接: {port}")
        except Exception as e:
            logger.warning(f"HEEG trigger 串口失败: {e}")
            self._trigger_serial = None

    def close_trigger_port(self):
        if self._trigger_serial:
            try:
                self._trigger_serial.close()
            except Exception:
                pass
            self._trigger_serial = None

    # ── 发送 Marker ──────────────────────────────────────────

    def send_marker(self, marker_name: str, **kwargs):
        ts = time.time()
        code = TRIGGER_CODES.get(marker_name, 0)

        marker = {"name": marker_name, "timestamp": ts,
                  "trigger_code": code, **kwargs}

        with self._log_lock:
            self.marker_log.append(marker)

        extra = "; ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        with self._csv_lock:
            if self._csv_writer:
                t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                ms = f"{ts % 1:.3f}"[2:]
                self._csv_writer.writerow([
                    f"{t_str}.{ms}", f"{ts:.6f}", marker_name, code, extra,
                ])
                self._csv_file.flush()

        if self._trigger_serial and code > 0:
            try:
                self._trigger_serial.write(bytes([code]))
                time.sleep(0.005)
                self._trigger_serial.write(bytes([0]))
            except Exception as e:
                logger.warning(f"串口 trigger 发送失败: {e}")

        with self._cb_lock:
            for cb in self._callbacks:
                try:
                    cb(marker)
                except Exception as e:
                    logger.error(f"Marker 回调错误: {e}")

        logger.debug(f"[Marker] {marker_name} (code={code}) @ {ts:.3f}")

    # ── 回调注册 ──────────────────────────────────────────────

    def register_callback(self, callback: Callable[[Dict], None]):
        with self._cb_lock:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[Dict], None]):
        with self._cb_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    # ── 日志 ─────────────────────────────────────────────────

    def get_marker_log(self) -> List[Dict]:
        with self._log_lock:
            return self.marker_log.copy()

    def clear(self):
        with self._log_lock:
            self.marker_log.clear()

    def get_statistics(self) -> Dict:
        with self._log_lock:
            total = len(self.marker_log)
        with self._cb_lock:
            cbs = len(self._callbacks)
        return {"total_markers": total, "callback_count": cbs}
