"""设备检测/连接面板 — Fluent Design 版，每个模态一个独立卡片"""

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtCore import Qt, pyqtSignal

from qfluentwidgets import (
    HeaderCardWidget, SimpleCardWidget,
    PrimaryPushButton, PushButton, ToolButton, TransparentPushButton,
    StrongBodyLabel, CaptionLabel, BodyLabel,
    InfoBadge, InfoLevel,
    FluentIcon as FIF,
)

DEVICE_DEFS = [
    ("heeg",        "EEG 脑电",   FIF.HEART,      "Neuracle HEEG-16"),
    ("shimmer",     "GSR / PPG",  FIF.IOT,        "Shimmer GSR+"),
    ("shimmer_emg", "EMG 肌电",   FIF.CALORIES,   "Shimmer EMG"),
    ("video",       "摄像头",     FIF.CAMERA,      "USB Camera"),
    ("audio",       "麦克风",     FIF.MICROPHONE,  "Default Input"),
]


class DevicePanel(HeaderCardWidget):
    """Fluent 设备检测/连接卡片 — 每个模态独立方框"""

    device_controller_ready = pyqtSignal(object)
    log_message = pyqtSignal(str)

    _sig_detect_done = pyqtSignal(dict)
    _sig_set_row = pyqtSignal(str, str)
    _sig_connect_done = pyqtSignal()

    IDLE = "idle"
    SCANNING = "scanning"
    FOUND = "found"
    NOT_FOUND = "not_found"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

    _BADGE_MAP = {
        "idle":       ("未检测",   "warning"),
        "scanning":   ("检测中…", "warning"),
        "found":      ("已找到",   "success"),
        "not_found":  ("未找到",   "error"),
        "connecting": ("连接中…", "warning"),
        "connected":  ("已连接",   "success"),
        "error":      ("失败",     "error"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("设备检测")

        self.device_controller = None
        self._rows = {}
        self._badges = {}
        self._row_states = {}
        self._shimmer_lock = threading.Lock()

        self._sig_detect_done.connect(self._apply_detect_results)
        self._sig_set_row.connect(self._set_row_state)
        self._sig_connect_done.connect(self._after_connect_all)

        self._build_device_cards()
        self._build_action_buttons()

    def _build_device_cards(self):
        grid = QGridLayout()
        grid.setSpacing(8)

        for idx, (key, name, icon, model) in enumerate(DEVICE_DEFS):
            card = SimpleCardWidget()
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(12, 10, 12, 10)
            card_lay.setSpacing(6)

            top_row = QHBoxLayout()
            top_row.setSpacing(8)
            icon_btn = ToolButton(icon)
            icon_btn.setFixedSize(28, 28)
            icon_btn.setEnabled(False)
            top_row.addWidget(icon_btn)

            name_lbl = StrongBodyLabel(name)
            top_row.addWidget(name_lbl)
            top_row.addStretch()

            badge = InfoBadge.warning("未检测")
            badge.setFixedHeight(22)
            self._badges[key] = badge
            self._row_states[key] = self.IDLE
            top_row.addWidget(badge)
            card_lay.addLayout(top_row)

            model_lbl = CaptionLabel(model)
            card_lay.addWidget(model_lbl)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(6)
            btn_connect = PushButton("连接")
            btn_connect.setFixedHeight(28)
            btn_connect.clicked.connect(
                lambda _, k=key: self._on_connect_one(k)
            )
            btn_row.addWidget(btn_connect)

            btn_disconnect = TransparentPushButton("断开")
            btn_disconnect.setFixedHeight(28)
            btn_disconnect.clicked.connect(
                lambda _, k=key: self._on_disconnect_one(k)
            )
            btn_row.addWidget(btn_disconnect)
            card_lay.addLayout(btn_row)

            self._rows[key] = card

            row_pos = idx // 3
            col_pos = idx % 3
            grid.addWidget(card, row_pos, col_pos)

        self.viewLayout.addLayout(grid)

    def _build_action_buttons(self):
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_detect = PushButton(FIF.SEARCH, "检测所有设备")
        self._btn_detect.setFixedHeight(38)
        self._btn_detect.clicked.connect(self._on_detect_all)
        btn_row.addWidget(self._btn_detect)

        self._btn_connect_all = PrimaryPushButton(FIF.LINK, "一键连接全部")
        self._btn_connect_all.setFixedHeight(38)
        self._btn_connect_all.setEnabled(False)
        self._btn_connect_all.clicked.connect(self._on_connect_all)
        btn_row.addWidget(self._btn_connect_all)

        self._btn_disconnect_all = PushButton("断开全部")
        self._btn_disconnect_all.setFixedHeight(38)
        self._btn_disconnect_all.setEnabled(False)
        self._btn_disconnect_all.clicked.connect(self._on_disconnect_all)
        btn_row.addWidget(self._btn_disconnect_all)

        self.viewLayout.addLayout(btn_row)

        self._conn_count_lbl = CaptionLabel("0 / 5 已连接")
        self._conn_count_lbl.setAlignment(Qt.AlignCenter)
        self.viewLayout.addWidget(self._conn_count_lbl)

    # ═══════════════════════════════════════════════════════════
    #  Badge 状态管理
    # ═══════════════════════════════════════════════════════════

    def _update_badge(self, key: str, state: str):
        self._row_states[key] = state
        text, level_name = self._BADGE_MAP.get(state, ("未知", "warning"))
        badge = self._badges[key]
        badge.setText(text)

        level_map = {
            "success": InfoLevel.SUCCESS,
            "warning": InfoLevel.WARNING,
            "error":   InfoLevel.ERROR,
        }
        badge.setLevel(level_map.get(level_name, InfoLevel.WARNING))

    # ═══════════════════════════════════════════════════════════
    #  业务逻辑（保留自旧版）
    # ═══════════════════════════════════════════════════════════

    def _ensure_device_controller(self):
        if self.device_controller is None:
            from devices.controller import DeviceController
            self.device_controller = DeviceController()
            self.device_controller.set_status_callback(
                lambda msg: self.log_message.emit(msg)
            )
            self.device_controller_ready.emit(self.device_controller)

    def _on_detect_all(self):
        self._btn_detect.setEnabled(False)
        self._btn_detect.setText("检测中...")
        for key in self._rows:
            self._update_badge(key, self.SCANNING)
        self.log_message.emit("开始检测所有设备...")

        def _detect_heeg() -> bool:
            try:
                import socket
                s = socket.socket()
                s.settimeout(2.0)
                s.connect(("127.0.0.1", 8172))
                s.close()
                return True
            except Exception:
                return False

        def _detect_shimmer() -> bool:
            try:
                import serial.tools.list_ports
                return len(list(serial.tools.list_ports.comports())) > 0
            except Exception:
                return False

        def _detect_video() -> bool:
            try:
                import cv2
                import sys as _sys
                backend = cv2.CAP_DSHOW if _sys.platform == "win32" else cv2.CAP_ANY
                for idx in range(4):
                    cap = cv2.VideoCapture(idx, backend)
                    if cap.isOpened():
                        cap.release()
                        return True
                    cap.release()
                return False
            except Exception:
                return False

        def _detect_audio() -> bool:
            try:
                import sounddevice as sd
                dev = sd.query_devices(kind='input')
                if int(dev.get('max_input_channels', 0)) > 0:
                    return True
                return any(
                    int(d.get('max_input_channels', 0)) > 0
                    for d in sd.query_devices()
                )
            except Exception:
                return False

        def _run_all():
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
            tasks = {
                "heeg": _detect_heeg,
                "shimmer": _detect_shimmer,
                "shimmer_emg": _detect_shimmer,
                "video": _detect_video,
                "audio": _detect_audio,
            }
            timeouts = {
                "heeg": 3.0, "shimmer": 3.0, "shimmer_emg": 3.0,
                "video": 8.0, "audio": 3.0,
            }
            results = {}
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {k: pool.submit(fn) for k, fn in tasks.items()}
                for k, fut in futures.items():
                    try:
                        results[k] = fut.result(timeout=timeouts[k])
                    except (FutTimeout, Exception):
                        results[k] = False
            self._sig_detect_done.emit(results)

        threading.Thread(target=_run_all, daemon=True).start()

    def _apply_detect_results(self, results: dict):
        found_count = 0
        for key, found in results.items():
            if found:
                self._update_badge(key, self.FOUND)
                found_count += 1
            else:
                self._update_badge(key, self.NOT_FOUND)

            name = next(
                (n for k, n, _, _ in DEVICE_DEFS if k == key), key
            )
            self.log_message.emit(
                f"{'✓' if found else '✗'} {name}：{'已找到' if found else '未找到'}"
            )
        self._btn_detect.setEnabled(True)
        self._btn_detect.setText("重新检测")
        self._btn_connect_all.setEnabled(found_count > 0)
        self.log_message.emit(f"检测完成，{found_count}/{len(self._rows)} 设备可用")

    def _on_connect_all(self):
        self._ensure_device_controller()
        self._btn_connect_all.setEnabled(False)
        self._btn_connect_all.setText("连接中...")

        connect_map = {
            "heeg": self.device_controller.initialize_heeg,
            "shimmer": self.device_controller.initialize_shimmer,
            "shimmer_emg": self.device_controller.initialize_shimmer_emg,
            "video": self.device_controller.initialize_video,
            "audio": self.device_controller.initialize_audio,
        }

        def _do_connect(key):
            fn = connect_map[key]
            self._sig_set_row.emit(key, self.CONNECTING)
            ok = fn()
            self._sig_set_row.emit(key, self.CONNECTED if ok else self.ERROR)
            return ok

        def _connect_parallel():
            independent = ["heeg", "video", "audio"]
            need_found = [
                k for k in independent
                if self._row_states.get(k) == self.FOUND
            ]
            gsr_needed = self._row_states.get("shimmer") == self.FOUND
            emg_needed = self._row_states.get("shimmer_emg") == self.FOUND

            def _gsr_then_emg():
                """GSR 先连，完成后再连 EMG（EMG 需排除 GSR 占用端口）"""
                with self._shimmer_lock:
                    if gsr_needed:
                        _do_connect("shimmer")
                    if emg_needed:
                        _do_connect("shimmer_emg")

            with ThreadPoolExecutor(max_workers=4) as pool:
                futs = []
                for key in need_found:
                    futs.append(pool.submit(_do_connect, key))
                if gsr_needed or emg_needed:
                    futs.append(pool.submit(_gsr_then_emg))
                for f in futs:
                    f.result()

            self._sig_connect_done.emit()

        threading.Thread(target=_connect_parallel, daemon=True).start()

    def _set_row_state(self, key: str, state: str):
        self._update_badge(key, state)
        self._refresh_conn_count()

    def _after_connect_all(self):
        self._btn_connect_all.setEnabled(True)
        self._btn_connect_all.setText("一键连接全部")
        self._btn_disconnect_all.setEnabled(True)
        self._refresh_conn_count()

    def _on_disconnect_all(self):
        if self.device_controller:
            self.device_controller.cleanup()
        for key in self._rows:
            self._update_badge(key, self.IDLE)
        self._refresh_conn_count()
        self._btn_disconnect_all.setEnabled(False)
        self.log_message.emit("已断开所有设备")

    def _on_connect_one(self, key: str):
        self._ensure_device_controller()
        connect_map = {
            "heeg": self.device_controller.initialize_heeg,
            "shimmer": self.device_controller.initialize_shimmer,
            "shimmer_emg": self.device_controller.initialize_shimmer_emg,
            "video": self.device_controller.initialize_video,
            "audio": self.device_controller.initialize_audio,
        }
        fn = connect_map.get(key)
        if not fn:
            return

        def _do():
            if key in ("shimmer", "shimmer_emg"):
                with self._shimmer_lock:
                    self._sig_set_row.emit(key, self.CONNECTING)
                    ok = fn()
            else:
                self._sig_set_row.emit(key, self.CONNECTING)
                ok = fn()
            self._sig_set_row.emit(
                key, self.CONNECTED if ok else self.ERROR
            )
            self._sig_connect_done.emit()

        name = next((n for k, n, _, _ in DEVICE_DEFS if k == key), key)
        threading.Thread(target=_do, daemon=True, name=f"connect_{key}").start()
        self.log_message.emit(f"正在连接 {name}...")

    def _on_disconnect_one(self, key: str):
        if not self.device_controller:
            return
        disconnect_map = {
            "heeg": self.device_controller.disconnect_heeg,
            "shimmer": self.device_controller.disconnect_shimmer,
            "shimmer_emg": self.device_controller.disconnect_shimmer_emg,
            "video": self.device_controller.disconnect_video,
            "audio": self.device_controller.disconnect_audio,
        }
        fn = disconnect_map.get(key)
        if fn:
            fn()
        self._update_badge(key, self.FOUND)
        self._refresh_conn_count()
        name = next((n for k, n, _, _ in DEVICE_DEFS if k == key), key)
        self.log_message.emit(f"已断开 {name}")

    def _refresh_conn_count(self):
        n = sum(
            1 for s in self._row_states.values() if s == self.CONNECTED
        )
        total = len(self._rows)
        self._conn_count_lbl.setText(f"{n} / {total} 已连接")
