"""
GSR + EMG 双设备真机联调测试
============================
一键连接两台 Shimmer 设备，实时显示波形，采集后输出 CSV + 数据汇总。

使用方法：
    py -3.13 tests/test_dual_hw.py

操作步骤：
    1. 点击 [连接 GSR]  →  自动扫描 COM 口连接 Shimmer GSR+
    2. 点击 [连接 EMG]  →  自动扫描 COM 口连接 Shimmer EMG（跳过 GSR 占用口）
    3. 点击 [▶ 开始采集]  →  两路同时采集，实时波形滚动
    4. 点击 [⏹ 停止 & 输出]  →  保存 CSV 到 data/dual_test/，打印数据汇总
"""

import csv
import math
import os
import sys
import time
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTextEdit,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

try:
    import pyqtgraph as pg
    _PG = True
except ImportError:
    _PG = False

from devices.controller import DeviceController


# ── 输出目录 ──────────────────────────────────────────────
OUT_DIR = ROOT / "data" / "dual_test"
OUT_DIR.mkdir(parents=True, exist_ok=True)


class DualDeviceTestWindow(QMainWindow):
    """双设备联调主窗口"""

    _log_sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GSR + EMG 双设备联调测试")
        self.resize(1400, 950)

        self.dc = DeviceController(use_mock_devices=False)
        self.dc.set_status_callback(lambda msg: self._log_sig.emit(msg))

        self.gsr_rows: list[dict] = []
        self.emg_rows: list[dict] = []
        self.collecting = False
        self.t0 = 0.0

        # 实时缓冲（固定长度滚动窗口）
        GSR_BUF = 128 * 6      # GSR 128 Hz × 6 s
        EMG_BUF = 1000 * 5     # EMG 1000 Hz × 5 s
        self._gsr_cond  = deque(maxlen=GSR_BUF)
        self._gsr_ppg   = deque(maxlen=GSR_BUF)
        self._emg_ch1   = deque(maxlen=EMG_BUF)
        self._emg_ch2   = deque(maxlen=EMG_BUF)
        self._emg_ax    = deque(maxlen=EMG_BUF)
        self._emg_ay    = deque(maxlen=EMG_BUF)
        self._emg_az    = deque(maxlen=EMG_BUF)

        self._build_ui()

        self._log_sig.connect(self._log)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    # ══════════════════════════════════════════════════════
    #  UI 构建
    # ══════════════════════════════════════════════════════

    def _build_ui(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)

        # ── 按钮栏 ──
        bar = QHBoxLayout()
        self.btn_gsr = self._btn("🔗  连接 GSR", self._on_connect_gsr)
        self.btn_emg = self._btn("🔗  连接 EMG", self._on_connect_emg)
        self.btn_start = self._btn("▶  开始采集", self._on_start, enabled=False)
        self.btn_stop = self._btn("⏹  停止 && 输出数据", self._on_stop, enabled=False)
        for b in (self.btn_gsr, self.btn_emg, self.btn_start, self.btn_stop):
            bar.addWidget(b)
        root.addLayout(bar)

        # ── 状态栏 ──
        self.lbl_status = QLabel("就绪 — 请先连接设备")
        self.lbl_status.setStyleSheet(
            "font-size:14px; padding:6px 10px; "
            "background:#2d2d2d; color:#ccc; border-radius:4px;"
        )
        root.addWidget(self.lbl_status)

        # ── 波形 ──
        if _PG:
            splitter = QSplitter(Qt.Vertical)
            splitter.addWidget(self._build_gsr_plots())
            splitter.addWidget(self._build_emg_plots())
            root.addWidget(splitter, stretch=1)
        else:
            root.addWidget(QLabel("⚠ pyqtgraph 未安装，无法显示波形"), stretch=1)

        # ── 日志 ──
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(220)
        self.log_box.setStyleSheet(
            "font-family:Consolas,'Courier New',monospace; font-size:12px; "
            "background:#1a1a1a; color:#b5cea8; border:1px solid #333;"
        )
        root.addWidget(self.log_box)

    @staticmethod
    def _btn(text, slot, enabled=True):
        b = QPushButton(text)
        b.setFixedHeight(42)
        b.setStyleSheet(
            "QPushButton{font-size:14px; font-weight:bold; padding:0 18px; "
            "border-radius:6px; background:#0078d4; color:white;}"
            "QPushButton:hover{background:#1a8ae8;}"
            "QPushButton:disabled{background:#555; color:#999;}"
        )
        b.setEnabled(enabled)
        b.clicked.connect(slot)
        return b

    def _build_gsr_plots(self):
        w = pg.GraphicsLayoutWidget()
        w.setBackground("#1e1e1e")

        self.p_gsr = w.addPlot(row=0, col=0,
            title="<span style='font-size:13pt;color:#4CAF50'>GSR 皮肤电导 (µS)</span>")
        self.p_gsr.showGrid(x=True, y=True, alpha=0.25)
        self.p_gsr.setLabel("bottom", "时间", units="s")
        self.c_gsr = self.p_gsr.plot(pen=pg.mkPen("#4CAF50", width=2))

        self.p_ppg = w.addPlot(row=1, col=0,
            title="<span style='font-size:13pt;color:#f44336'>PPG 光电容积</span>")
        self.p_ppg.showGrid(x=True, y=True, alpha=0.25)
        self.p_ppg.setLabel("bottom", "时间", units="s")
        self.c_ppg = self.p_ppg.plot(pen=pg.mkPen("#f44336", width=2))

        return w

    def _build_emg_plots(self):
        w = pg.GraphicsLayoutWidget()
        w.setBackground("#1e1e1e")

        self.p_ch1 = w.addPlot(row=0, col=0,
            title="<span style='font-size:13pt;color:#2196F3'>EMG CH1 (mV)</span>")
        self.p_ch1.showGrid(x=True, y=True, alpha=0.25)
        self.p_ch1.addLine(y=0, pen=pg.mkPen("#555", width=1, style=Qt.DashLine))
        self.c_ch1 = self.p_ch1.plot(pen=pg.mkPen("#2196F3", width=2))

        self.p_ch2 = w.addPlot(row=1, col=0,
            title="<span style='font-size:13pt;color:#FF9800'>EMG CH2 (mV)</span>")
        self.p_ch2.showGrid(x=True, y=True, alpha=0.25)
        self.p_ch2.addLine(y=0, pen=pg.mkPen("#555", width=1, style=Qt.DashLine))
        self.c_ch2 = self.p_ch2.plot(pen=pg.mkPen("#FF9800", width=2))

        self.p_acc = w.addPlot(row=2, col=0,
            title="<span style='font-size:13pt;color:#4CAF50'>EMG 加速度 (m/s²)</span>")
        self.p_acc.showGrid(x=True, y=True, alpha=0.25)
        self.c_ax = self.p_acc.plot(pen=pg.mkPen("#f44336", width=1.5), name="X")
        self.c_ay = self.p_acc.plot(pen=pg.mkPen("#4CAF50", width=1.5), name="Y")
        self.c_az = self.p_acc.plot(pen=pg.mkPen("#2196F3", width=1.5), name="Z")
        self.p_acc.addLegend(offset=(-10, 10))

        return w

    # ══════════════════════════════════════════════════════
    #  按钮动作
    # ══════════════════════════════════════════════════════

    def _on_connect_gsr(self):
        self.btn_gsr.setEnabled(False)
        self.btn_gsr.setText("⏳ GSR 连接中…")
        threading.Thread(target=self._do_connect_gsr, daemon=True).start()

    def _do_connect_gsr(self):
        self.dc.initialize_shimmer()
        self._log_sig.emit(
            "✅ GSR 连接成功" if self.dc.shimmer_connected else "❌ GSR 连接失败"
        )

    def _on_connect_emg(self):
        self.btn_emg.setEnabled(False)
        self.btn_emg.setText("⏳ EMG 连接中…")
        threading.Thread(target=self._do_connect_emg, daemon=True).start()

    def _do_connect_emg(self):
        self.dc.initialize_shimmer_emg()
        self._log_sig.emit(
            "✅ EMG 连接成功" if self.dc.shimmer_emg_connected else "❌ EMG 连接失败"
        )

    def _on_start(self):
        self.collecting = True
        self.t0 = time.time()
        self.gsr_rows.clear()
        self.emg_rows.clear()
        self._gsr_cond.clear()
        self._gsr_ppg.clear()
        self._emg_ch1.clear()
        self._emg_ch2.clear()
        self._emg_ax.clear()
        self._emg_ay.clear()
        self._emg_az.clear()

        if self.dc.shimmer_connected and self.dc.shimmer_device:
            self.dc.shimmer_device.start_streaming()
            self._log("GSR 数据流已启动")

        if self.dc.shimmer_emg_connected and self.dc.shimmer_emg_device:
            self.dc.shimmer_emg_device.start_streaming(self._emg_packet)
            self._log("EMG 数据流已启动")

        self._log("▶ 采集开始！按 [停止 & 输出数据] 结束")

    def _on_stop(self):
        if not self.collecting:
            return
        self.collecting = False
        elapsed = time.time() - self.t0

        if self.dc.shimmer_connected and self.dc.shimmer_device:
            try:
                self.dc.shimmer_device.stop_streaming()
            except Exception:
                pass

        if self.dc.shimmer_emg_connected and self.dc.shimmer_emg_device:
            try:
                self.dc.shimmer_emg_device.stop_streaming()
            except Exception:
                pass

        self._log(f"⏹ 采集停止（{elapsed:.1f} 秒）")
        self._save_and_report(elapsed)

    # ══════════════════════════════════════════════════════
    #  数据回调
    # ══════════════════════════════════════════════════════

    def _emg_packet(self, data: dict):
        """EMG 数据回调（pyshimmer 线程）"""
        if not self.collecting:
            return
        self.emg_rows.append(data)
        self._emg_ch1.append(data.get("emg_ch1_mv", 0))
        self._emg_ch2.append(data.get("emg_ch2_mv", 0))
        self._emg_ax.append(data.get("accel_x_ms2", 0))
        self._emg_ay.append(data.get("accel_y_ms2", 0))
        self._emg_az.append(data.get("accel_z_ms2", 0))

    # ══════════════════════════════════════════════════════
    #  定时刷新 (50 ms)
    # ══════════════════════════════════════════════════════

    def _tick(self):
        self._sync_buttons()

        if not self.collecting:
            return

        self._poll_gsr()
        self._refresh_plots()
        self._refresh_status()

    def _poll_gsr(self):
        """从 GSR 设备缓冲区取出数据"""
        dev = self.dc.shimmer_device
        if not (self.dc.shimmer_connected and dev):
            return
        buf = getattr(dev, "data_buffer", None)
        if not buf:
            return

        while buf:
            pkt = buf.pop(0)
            try:
                result = dev.extract_sample_from_packet(pkt)
                if isinstance(result, tuple) and len(result) == 2:
                    sample, ts = result
                else:
                    sample, ts = result, time.time()

                if not sample:
                    continue

                names = dev.get_channel_names()
                row = {"timestamp": ts}
                for i, name in enumerate(names):
                    if i < len(sample):
                        row[name] = sample[i]
                self.gsr_rows.append(row)

                for i, name in enumerate(names):
                    if i >= len(sample):
                        break
                    if "GSR_Skin_Conductance" in name:
                        self._gsr_cond.append(sample[i])
                    elif "PPG" in name and "PPGtoHR" not in name:
                        self._gsr_ppg.append(sample[i])
            except Exception:
                pass

    def _refresh_plots(self):
        if not _PG:
            return

        def _set(curve, buf, fs):
            if buf:
                arr = np.array(buf)
                t = np.arange(len(arr)) / fs
                curve.setData(t, arr)

        _set(self.c_gsr, self._gsr_cond, 128.0)
        _set(self.c_ppg, self._gsr_ppg, 128.0)
        _set(self.c_ch1, self._emg_ch1, 1000.0)
        _set(self.c_ch2, self._emg_ch2, 1000.0)

        if self._emg_ax:
            n = len(self._emg_ax)
            t = np.arange(n) / 1000.0
            self.c_ax.setData(t, np.array(self._emg_ax))
            self.c_ay.setData(t, np.array(self._emg_ay))
            self.c_az.setData(t, np.array(self._emg_az))

    def _refresh_status(self):
        elapsed = time.time() - self.t0
        gsr_n = len(self.gsr_rows)
        emg_n = len(self.emg_rows)
        gsr_hz = gsr_n / elapsed if elapsed > 0 else 0
        emg_hz = emg_n / elapsed if elapsed > 0 else 0
        self.lbl_status.setText(
            f"🟢 采集中  {elapsed:.1f}s  │  "
            f"GSR: {gsr_n} 包 ({gsr_hz:.0f} Hz)  │  "
            f"EMG: {emg_n} 包 ({emg_hz:.0f} Hz)"
        )

    def _sync_buttons(self):
        gsr_ok = self.dc.shimmer_connected
        emg_ok = self.dc.shimmer_emg_connected
        self.btn_gsr.setText("✅ GSR 已连接" if gsr_ok else "🔗  连接 GSR")
        self.btn_gsr.setEnabled(not gsr_ok and not self.collecting)
        self.btn_emg.setText("✅ EMG 已连接" if emg_ok else "🔗  连接 EMG")
        self.btn_emg.setEnabled(not emg_ok and not self.collecting)
        self.btn_start.setEnabled((gsr_ok or emg_ok) and not self.collecting)
        self.btn_stop.setEnabled(self.collecting)

    # ══════════════════════════════════════════════════════
    #  保存 & 输出汇总
    # ══════════════════════════════════════════════════════

    def _save_and_report(self, elapsed: float):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # ── GSR CSV ──
        if self.gsr_rows:
            path = OUT_DIR / f"gsr_{stamp}.csv"
            keys = list(self.gsr_rows[0].keys())
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(self.gsr_rows)
            self._log(f"📁 GSR 已保存: {path}")
        else:
            self._log("⚠ 无 GSR 数据")

        # ── EMG CSV ──
        if self.emg_rows:
            path = OUT_DIR / f"emg_{stamp}.csv"
            keys = list(self.emg_rows[0].keys())
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(self.emg_rows)
            self._log(f"📁 EMG 已保存: {path}")
        else:
            self._log("⚠ 无 EMG 数据")

        # ── 汇总报告 ──
        sep = "═" * 60
        self._log(f"\n{sep}")
        self._log("  GSR + EMG 双设备采集报告")
        self._log(sep)
        self._log(f"  采集时长 : {elapsed:.1f} 秒")
        self._log(f"  GSR 数据 : {len(self.gsr_rows)} 包  "
                   f"({len(self.gsr_rows)/elapsed:.1f} Hz)" if elapsed > 0 else "")
        self._log(f"  EMG 数据 : {len(self.emg_rows)} 包  "
                   f"({len(self.emg_rows)/elapsed:.1f} Hz)" if elapsed > 0 else "")

        if self.gsr_rows:
            self._log("\n  ── GSR 数据样例 ──")
            for i, row in enumerate(self.gsr_rows[:3]):
                vals = "  ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                                 for k, v in list(row.items())[:5])
                self._log(f"    [{i}] {vals}")
            conds = [r.get("GSR_Skin_Conductance", 0)
                     for r in self.gsr_rows if "GSR_Skin_Conductance" in r]
            if conds:
                self._log(f"\n  GSR 电导  min={min(conds):.6f}  "
                           f"max={max(conds):.6f}  mean={np.mean(conds):.6f} µS")

        if self.emg_rows:
            self._log("\n  ── EMG 数据样例 ──")
            for i, row in enumerate(self.emg_rows[:3]):
                vals = "  ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                                 for k, v in list(row.items())[:5])
                self._log(f"    [{i}] {vals}")
            ch1 = [r.get("emg_ch1_mv", 0) for r in self.emg_rows]
            ch2 = [r.get("emg_ch2_mv", 0) for r in self.emg_rows]
            rms1 = math.sqrt(sum(v * v for v in ch1) / len(ch1)) if ch1 else 0
            rms2 = math.sqrt(sum(v * v for v in ch2) / len(ch2)) if ch2 else 0
            self._log(f"\n  EMG CH1   min={min(ch1):.6f}  max={max(ch1):.6f}  "
                       f"RMS={rms1:.6f} mV  ({rms1*1000:.1f} µV)")
            self._log(f"  EMG CH2   min={min(ch2):.6f}  max={max(ch2):.6f}  "
                       f"RMS={rms2:.6f} mV  ({rms2*1000:.1f} µV)")

        self._log(sep + "\n")

    # ── 日志 ──
    def _log(self, msg: str):
        self.log_box.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── 退出清理 ──
    def closeEvent(self, event):
        if self.collecting:
            self._on_stop()
        self.dc.cleanup()
        super().closeEvent(event)


# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = DualDeviceTestWindow()
    win.show()
    sys.exit(app.exec_())
