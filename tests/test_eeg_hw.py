#!/usr/bin/env python3
"""
EEG 真机连接测试
─────────────────────────────────────────────
连接 Neuracle HEEG (TCP 127.0.0.1:8172)，
实时显示可选通道波形，全部通道保存 CSV。

运行方式：
    py -3.13 tests/test_eeg_hw.py

前置条件：
    1. NSH-R 软件正在运行并采集数据
    2. config.ini 中 [DataSend] Value=1
"""

import sys
import os
import time
import csv
import threading
from collections import deque
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QSplitter, QSpinBox,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import pyqtgraph as pg

from devices.heeg import NeuracleHEEGDevice, HEEGState

_PLOT_COLORS = [
    "#00ff88", "#ff6b6b", "#4ecdc4", "#ffe66d",
    "#a8e6cf", "#ff8a80", "#80cbc4", "#fff59d",
    "#b39ddb", "#f48fb1", "#81d4fa", "#c5e1a5",
    "#ffcc80", "#ce93d8", "#80deea", "#e6ee9c",
]


class EEGTestWindow(QMainWindow):
    _sig_log = pyqtSignal(str)
    _sig_connected = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EEG 真机测试 — Neuracle HEEG")
        self.resize(1300, 850)

        self.device: NeuracleHEEGDevice | None = None
        self.is_streaming = False
        self.packet_count = 0
        self.sample_count = 0
        self.start_time: float | None = None

        self.all_data: list = []
        self.display_bufs: dict[int, deque] = {}
        self._actual_ch_count = 0

        self._build_ui()

        self._sig_log.connect(self._append_log)
        self._sig_connected.connect(self._after_connect)

        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(50)

    # ── UI ────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        splitter = QSplitter(Qt.Horizontal)

        # left panel
        left = QWidget()
        ll = QVBoxLayout(left)

        row1 = QHBoxLayout()
        self._btn_conn = QPushButton("连接 EEG")
        self._btn_conn.clicked.connect(self._on_connect)
        row1.addWidget(self._btn_conn)

        self._btn_start = QPushButton("▶ 开始采集")
        self._btn_start.setEnabled(False)
        self._btn_start.clicked.connect(self._on_start)
        row1.addWidget(self._btn_start)

        self._btn_stop = QPushButton("⏹ 停止 & 输出数据")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        row1.addWidget(self._btn_stop)
        ll.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("起始通道:"))
        self._sp_start = QSpinBox()
        self._sp_start.setRange(1, 64)
        self._sp_start.setValue(1)
        row2.addWidget(self._sp_start)
        row2.addWidget(QLabel("显示通道数:"))
        self._sp_count = QSpinBox()
        self._sp_count.setRange(1, 16)
        self._sp_count.setValue(8)
        row2.addWidget(self._sp_count)
        row2.addStretch()
        ll.addLayout(row2)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet("background:#1e1e1e; color:#d4d4d4; font-family:Consolas;")
        ll.addWidget(self._log)
        splitter.addWidget(left)

        # right panel — plots
        self._pg = pg.GraphicsLayoutWidget()
        self._pg.setBackground("#111")
        self._plots: list[pg.PlotItem] = []
        self._curves: list = []
        splitter.addWidget(self._pg)
        splitter.setSizes([420, 880])

        QVBoxLayout(central).addWidget(splitter)

        sb = self.statusBar()
        self._st_time = QLabel("00:00")
        self._st_pkt = QLabel("包: 0")
        self._st_samp = QLabel("样本: 0")
        self._st_rate = QLabel("速率: -- Hz")
        for w in (self._st_time, self._st_pkt, self._st_samp, self._st_rate):
            sb.addPermanentWidget(w)

        self._rebuild_plots(8)

    def _rebuild_plots(self, n: int):
        self._pg.clear()
        self._plots.clear()
        self._curves.clear()
        ch0 = self._sp_start.value() - 1
        for i in range(n):
            p = self._pg.addPlot(row=i, col=0)
            p.setLabel("left", f"Ch{ch0 + i + 1}", units="μV")
            p.showGrid(y=True, alpha=0.2)
            p.setMouseEnabled(x=False, y=False)
            if i < n - 1:
                p.hideAxis("bottom")
            c = p.plot(pen=pg.mkPen(_PLOT_COLORS[i % len(_PLOT_COLORS)], width=1))
            self._plots.append(p)
            self._curves.append(c)

    # ── Logging ───────────────────────────────────────────

    def _log_msg(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._sig_log.emit(f"[{ts}] {msg}")

    def _append_log(self, msg: str):
        self._log.append(msg)

    # ── Connect ───────────────────────────────────────────

    def _on_connect(self):
        self._btn_conn.setEnabled(False)
        self._btn_conn.setText("连接中...")
        threading.Thread(target=self._do_connect, daemon=True).start()

    def _do_connect(self):
        self._log_msg("正在连接 Neuracle HEEG (127.0.0.1:8172) ...")
        self.device = NeuracleHEEGDevice(hostname="127.0.0.1", port=8172)

        if not self.device.connect(max_retries=3):
            self._log_msg("✗ TCP 连接失败！请检查 NSH-R 是否运行")
            self._sig_connected.emit(False)
            return

        self._log_msg("✓ TCP 已连接，等待首个数据包 (最多 10s) ...")

        waited = 0.0
        while self.device.state not in (HEEGState.READY, HEEGState.STOPPED) and waited < 10:
            time.sleep(0.2)
            waited += 0.2

        if self.device.state != HEEGState.READY:
            self._log_msg("✗ 超时未收到数据包，请确认设备正在采集")
            self._sig_connected.emit(False)
            return

        info = self.device.get_device_info()
        self._actual_ch_count = info["channel_count"]
        self._log_msg(f"✓ 设备就绪!")
        self._log_msg(f"  通道数:  {info['channel_count']}")
        self._log_msg(f"  采样率:  {info['sample_rate']} Hz")
        ch_preview = ", ".join(info["channel_names"][:8])
        if info["channel_count"] > 8:
            ch_preview += " ..."
        self._log_msg(f"  通道名:  {ch_preview}")
        self._sig_connected.emit(True)

    def _after_connect(self, ok: bool):
        if ok:
            self._btn_conn.setText("✓ 已连接")
            self._btn_start.setEnabled(True)
            self._sp_start.setRange(1, max(1, self._actual_ch_count))
            self._sp_count.setRange(1, min(16, self._actual_ch_count))
        else:
            self._btn_conn.setText("连接 EEG")
            self._btn_conn.setEnabled(True)

    # ── Start / Stop ──────────────────────────────────────

    def _on_start(self):
        if not self.device:
            return

        self.device.set_data_callback(self._data_cb)

        if not self.device.start_streaming():
            self._log_msg("✗ 启动采集失败（设备状态非 READY）")
            return

        self.is_streaming = True
        self.start_time = time.time()
        self.packet_count = 0
        self.sample_count = 0
        self.all_data = []

        n_ch = self._actual_ch_count
        self.display_bufs = {i: deque(maxlen=4000) for i in range(n_ch)}

        n_show = min(self._sp_count.value(), n_ch)
        self._rebuild_plots(n_show)

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._log_msg(f"▶ 采集开始 — {n_ch} 通道 @ {self.device.sample_rate} Hz")

    def _on_stop(self):
        if self.device and self.device.is_streaming():
            self.device.stop_streaming()
        self.is_streaming = False
        self._btn_stop.setEnabled(False)

        elapsed = time.time() - self.start_time if self.start_time else 0
        self._log_msg(
            f"⏹ 采集停止 — {elapsed:.1f}s, {self.packet_count} 包, "
            f"{self.sample_count} 样本"
        )
        self._save_csv()
        self._print_summary()
        self._btn_start.setEnabled(True)

    # ── Data callback (device recv thread) ────────────────

    def _data_cb(self, data_struct: dict):
        self.packet_count += 1
        n_samp = data_struct["dataCountPerChannel"]
        self.sample_count += n_samp

        datas = data_struct["datas"]       # (ch, samples)
        heeg_ts = data_struct.get("timeStamp", 0)
        trigger = data_struct.get("trigger")
        sys_ts = time.time()

        for s in range(n_samp):
            self.all_data.append((sys_ts, heeg_ts, trigger, datas[:, s]))

        for ch in range(datas.shape[0]):
            buf = self.display_bufs.get(ch)
            if buf is not None:
                buf.extend(datas[ch, :].tolist())

    # ── Refresh plots ─────────────────────────────────────

    def _refresh(self):
        if not self.is_streaming:
            return

        ch0 = self._sp_start.value() - 1
        for i, curve in enumerate(self._curves):
            buf = self.display_bufs.get(ch0 + i)
            if buf and len(buf) > 0:
                curve.setData(np.array(buf))
            self._plots[i].setLabel("left", f"Ch{ch0 + i + 1}", units="μV")

        if self.start_time:
            el = time.time() - self.start_time
            m, s = divmod(int(el), 60)
            self._st_time.setText(f"{m:02d}:{s:02d}")
            self._st_pkt.setText(f"包: {self.packet_count}")
            self._st_samp.setText(f"样本: {self.sample_count}")
            self._st_rate.setText(f"速率: {self.sample_count / el:.0f} Hz" if el > 0 else "")

    # ── Save CSV ──────────────────────────────────────────

    def _save_csv(self):
        if not self.all_data:
            self._log_msg("⚠ 无数据可保存")
            return

        out_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "eeg_test",
        )
        os.makedirs(out_dir, exist_ok=True)

        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"eeg_{ts_str}.csv")

        n_ch = self._actual_ch_count or 64
        headers = ["system_time", "heeg_timestamp", "trigger"] + [
            f"Ch{i + 1}" for i in range(n_ch)
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for sys_ts, heeg_ts, trigger, row in self.all_data:
                writer.writerow(
                    [f"{sys_ts:.6f}", heeg_ts, trigger if trigger is not None else ""]
                    + [f"{v:.4f}" for v in row]
                )

        self._log_msg(f"📁 EEG 已保存: {path}")
        self._log_msg(f"   行数: {len(self.all_data):,}  列数: {len(headers)}")

    # ── Summary ───────────────────────────────────────────

    def _print_summary(self):
        if not self.all_data:
            return

        n_ch = len(self.all_data[0][3])
        n_samples = len(self.all_data)
        elapsed = time.time() - self.start_time if self.start_time else 1

        self._log_msg("=" * 55)
        self._log_msg("📊 EEG 数据汇总")
        self._log_msg(f"  通道数:     {n_ch}")
        self._log_msg(f"  总样本:     {n_samples:,}")
        self._log_msg(f"  采集时长:   {elapsed:.1f}s")
        self._log_msg(f"  实际采样率: {n_samples / elapsed:.1f} Hz")

        data_arr = np.array([row[3] for row in self.all_data])
        show_n = min(8, n_ch)
        for i in range(show_n):
            ch = data_arr[:, i]
            self._log_msg(
                f"  Ch{i + 1:>2d}: min={ch.min():>10.2f}  "
                f"max={ch.max():>10.2f}  "
                f"mean={ch.mean():>10.2f}  "
                f"std={ch.std():>8.2f} μV"
            )
        if n_ch > show_n:
            self._log_msg(f"  ... 其余 {n_ch - show_n} 个通道已保存到 CSV")

        triggers = [r[2] for r in self.all_data if r[2] is not None]
        if triggers:
            unique = sorted(set(triggers))
            self._log_msg(f"  Trigger: {len(triggers)} 事件, 值: {unique}")
        else:
            self._log_msg("  Trigger: 无")
        self._log_msg("=" * 55)

    # ── Close ─────────────────────────────────────────────

    def closeEvent(self, event):
        if self.is_streaming and self.device:
            self.device.stop_streaming()
        if self.device:
            self.device.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = app.palette()
    from PyQt5.QtGui import QColor
    palette.setColor(palette.Window, QColor("#1e1e1e"))
    palette.setColor(palette.WindowText, QColor("#d4d4d4"))
    palette.setColor(palette.Base, QColor("#252526"))
    palette.setColor(palette.Text, QColor("#d4d4d4"))
    palette.setColor(palette.Button, QColor("#333"))
    palette.setColor(palette.ButtonText, QColor("#d4d4d4"))
    app.setPalette(palette)

    win = EEGTestWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
