"""
实时 EMG 显示 Tab  ── Shimmer3 ExG EMG
========================================
支持两种使用场景：
  1. 主应用 Tab：实例化后由 device_controller 通过 push_sample() 推送数据
  2. 独立调试窗口：由 test_emg_unit.py --realtime 启动，直接接收回调数据

显示内容：
  · EMG CH1 / CH2 波形（mV）+ 实时 RMS 电平柱
  · 加速度计 X/Y/Z（m/s²）
  · 陀螺仪 X/Y/Z（deg/s）
  · 统计面板：RMS、峰峰值、信号质量、实际采样率
"""

import math
import threading
import time
from collections import deque

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QMainWindow, QProgressBar, QVBoxLayout, QWidget,
)

try:
    import pyqtgraph as pg
    _PG = True
except ImportError:
    _PG = False

# ── 颜色主题 ──────────────────────────────────────────────
_BLUE   = "#2196F3"
_GREEN  = "#4CAF50"
_RED    = "#f44336"
_ORANGE = "#FF9800"
_PURPLE = "#9C27B0"
_TEAL   = "#009688"
def _get_bg():
    from app.monitors import _is_dark
    return '#1e1e1e' if _is_dark() else '#FAFAFA'


# ─────────────────────────────────────────────────────────
class EMGAnalyzer:
    """
    滑动窗口 RMS 和信号质量评估。
    线程安全：数据由采集线程写入，UI 线程读取统计结果。
    """
    def __init__(self, fs: float = 1000.0, window_ms: float = 200.0):
        self.fs     = fs
        self._win   = max(1, int(fs * window_ms / 1000.0))
        self._lock  = threading.Lock()
        self._buf1  = deque(maxlen=self._win)
        self._buf2  = deque(maxlen=self._win)
        self._t0    = None
        self._n     = 0

    def push(self, ch1_mv: float, ch2_mv: float):
        with self._lock:
            self._buf1.append(ch1_mv)
            self._buf2.append(ch2_mv)
            if self._t0 is None:
                self._t0 = time.perf_counter()
            self._n += 1

    def rms(self):
        with self._lock:
            b1 = list(self._buf1)
            b2 = list(self._buf2)
        r1 = math.sqrt(sum(v*v for v in b1) / len(b1)) if b1 else 0.0
        r2 = math.sqrt(sum(v*v for v in b2) / len(b2)) if b2 else 0.0
        return r1, r2

    def quality(self, rms_mv: float) -> tuple:
        """返回 (文字, 颜色)"""
        uv = rms_mv * 1000
        if uv < 5:
            return "⚠ 无信号", "#999"
        elif uv < 10:
            return "⚠ 微弱", _ORANGE
        elif uv < 50:
            return "✓ 基线", _GREEN
        elif uv < 500:
            return "✓ 正常激活", _GREEN
        elif uv < 5000:
            return "✓ 强激活", _TEAL
        else:
            return "⚠ 可能伪迹", _RED

    def actual_rate(self) -> float:
        with self._lock:
            if self._t0 is None or self._n < 2:
                return 0.0
            elapsed = time.perf_counter() - self._t0
            return self._n / elapsed if elapsed > 0 else 0.0

    def reset(self):
        with self._lock:
            self._buf1.clear()
            self._buf2.clear()
            self._t0 = None
            self._n  = 0


# ─────────────────────────────────────────────────────────
class RealtimeEMGTab(QWidget):
    """
    实时 EMG 显示控件。
    可作为主窗口 Tab 嵌入，也可独立作为 QMainWindow 的中心控件。

    外部通过 push_sample() 传入每一帧数据：
        tab.push_sample(
            ch1_mv, ch2_mv,
            ax_ms2, ay_ms2, az_ms2,
            gx_dps, gy_dps, gz_dps,
        )
    """

    # 显示窗口长度（秒）
    DISPLAY_SECS = 5.0
    # 定时刷新间隔（ms）
    REFRESH_MS   = 40    # ~25 fps

    def __init__(self, collection_tab_or_fs=None, parent=None):
        """
        两种调用方式：
          RealtimeEMGTab(collection_tab)   —— 嵌入主应用
          RealtimeEMGTab(fs=1000.0)        —— 独立/单元测试模式
        """
        super().__init__(parent)

        # 兼容两种调用方式
        if isinstance(collection_tab_or_fs, (int, float)):
            fs = float(collection_tab_or_fs)
            self._collection_tab = None
        elif collection_tab_or_fs is None:
            fs = 1000.0
            self._collection_tab = None
        else:
            self._collection_tab = collection_tab_or_fs
            fs = 1000.0

        self.fs = fs
        buf = int(fs * self.DISPLAY_SECS)

        # ── 环形缓冲区 ────────────────────────────────
        self._ch1   = deque(maxlen=buf)
        self._ch2   = deque(maxlen=buf)
        self._ax    = deque(maxlen=buf)
        self._ay    = deque(maxlen=buf)
        self._az    = deque(maxlen=buf)
        self._gx    = deque(maxlen=buf)
        self._gy    = deque(maxlen=buf)
        self._gz    = deque(maxlen=buf)
        self._lock  = threading.Lock()

        # ── 分析器 ───────────────────────────────────
        self._analyzer = EMGAnalyzer(fs=fs)

        self._init_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(self.REFRESH_MS)

    def set_device_controller(self, device_controller):
        """注入 DeviceController，自动注册 EMG 实时回调"""
        self._dc = device_controller
        if device_controller is not None:
            device_controller.emg_realtime_callback = self._on_emg_data

    def _on_emg_data(self, data: dict):
        """DeviceController 回调 → push_sample（线程安全）"""
        self.push_sample(
            data.get('emg_ch1_mv',  0.0),
            data.get('emg_ch2_mv',  0.0),
            data.get('accel_x_ms2', 0.0),
            data.get('accel_y_ms2', 0.0),
            data.get('accel_z_ms2', 0.0),
            data.get('gyro_x_dps',  0.0),
            data.get('gyro_y_dps',  0.0),
            data.get('gyro_z_dps',  0.0),
        )

    # ── 公共接口 ──────────────────────────────────────
    def push_sample(self,
                    ch1_mv: float, ch2_mv: float,
                    ax_ms2: float = 0, ay_ms2: float = 0, az_ms2: float = 0,
                    gx_dps: float = 0, gy_dps: float = 0, gz_dps: float = 0):
        """线程安全，从采集线程调用"""
        with self._lock:
            self._ch1.append(ch1_mv)
            self._ch2.append(ch2_mv)
            self._ax.append(ax_ms2)
            self._ay.append(ay_ms2)
            self._az.append(az_ms2)
            self._gx.append(gx_dps)
            self._gy.append(gy_dps)
            self._gz.append(gz_dps)
        self._analyzer.push(ch1_mv, ch2_mv)

    # ── UI 构建 ───────────────────────────────────────
    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # 标题栏
        root.addWidget(self._make_title())

        if _PG:
            root.addWidget(self._make_plots(), stretch=5)
        else:
            lbl = QLabel("⚠ 未安装 pyqtgraph，请执行：pip install pyqtgraph")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color:#999;font-size:15px;padding:40px;")
            root.addWidget(lbl, stretch=5)

        # RMS 电平计
        root.addWidget(self._make_level_bars(), stretch=1)

        # 统计面板
        root.addWidget(self._make_stats_panel())

    def _make_title(self):
        from app.monitors import _is_dark, tint
        lbl = QLabel("⚡ EMG 实时监测  ─  Shimmer3 ExG")
        _bg = tint(_BLUE, 25)
        lbl.setStyleSheet(f"""
            QLabel {{
                font-size: 17px; font-weight: bold; color: {_BLUE};
                padding: 8px 12px; background: {_bg};
                border-left: 4px solid {_BLUE}; border-radius: 4px;
            }}
        """)
        return lbl

    def _make_plots(self):
        self._pw = pg.GraphicsLayoutWidget()
        self._pw.setBackground(_get_bg())

        pen_ch1  = pg.mkPen(color=_BLUE,   width=2)
        pen_ch2  = pg.mkPen(color=_ORANGE, width=2)
        pen_ax   = pg.mkPen(color=_RED,    width=1.5)
        pen_ay   = pg.mkPen(color=_GREEN,  width=1.5)
        pen_az   = pg.mkPen(color=_BLUE,   width=1.5)
        pen_gx   = pg.mkPen(color=_RED,    width=1.5, style=Qt.DashLine)
        pen_gy   = pg.mkPen(color=_GREEN,  width=1.5, style=Qt.DashLine)
        pen_gz   = pg.mkPen(color=_BLUE,   width=1.5, style=Qt.DashLine)

        # ── EMG CH1 ───────────────────────────────────
        self._p_ch1 = self._pw.addPlot(row=0, col=0,
            title="<b style='font-size:12pt;color:#2196F3'>EMG CH1（mV）</b>")
        self._p_ch1.setLabel("left",   "mV",   **{"font-size": "10pt"})
        self._p_ch1.setLabel("bottom", "时间", units="s", **{"font-size": "10pt"})
        self._p_ch1.showGrid(x=True, y=True, alpha=0.25)
        self._p_ch1.setYRange(-1, 1)
        self._c_ch1 = self._p_ch1.plot(pen=pen_ch1)

        # 零基准线
        self._p_ch1.addLine(y=0, pen=pg.mkPen('#aaa', width=1, style=Qt.DashLine))

        # ── EMG CH2 ───────────────────────────────────
        self._p_ch2 = self._pw.addPlot(row=1, col=0,
            title="<b style='font-size:12pt;color:#FF9800'>EMG CH2（mV）</b>")
        self._p_ch2.setLabel("left",   "mV",   **{"font-size": "10pt"})
        self._p_ch2.setLabel("bottom", "时间", units="s", **{"font-size": "10pt"})
        self._p_ch2.showGrid(x=True, y=True, alpha=0.25)
        self._p_ch2.setYRange(-1, 1)
        self._c_ch2 = self._p_ch2.plot(pen=pen_ch2)
        self._p_ch2.addLine(y=0, pen=pg.mkPen('#aaa', width=1, style=Qt.DashLine))

        # ── 加速度计 ──────────────────────────────────
        self._p_acc = self._pw.addPlot(row=2, col=0,
            title="<b style='font-size:12pt;color:#4CAF50'>加速度计（m/s²）</b>")
        self._p_acc.setLabel("left",   "m/s²", **{"font-size": "10pt"})
        self._p_acc.setLabel("bottom", "时间", units="s", **{"font-size": "10pt"})
        self._p_acc.showGrid(x=True, y=True, alpha=0.25)
        self._c_ax = self._p_acc.plot(pen=pen_ax, name="X")
        self._c_ay = self._p_acc.plot(pen=pen_ay, name="Y")
        self._c_az = self._p_acc.plot(pen=pen_az, name="Z")
        leg = self._p_acc.addLegend(offset=(-10, 10))
        leg.setParentItem(self._p_acc.graphicsItem())

        # ── 陀螺仪 ────────────────────────────────────
        self._p_gyr = self._pw.addPlot(row=3, col=0,
            title="<b style='font-size:12pt;color:#9C27B0'>陀螺仪（deg/s）</b>")
        self._p_gyr.setLabel("left",   "°/s",  **{"font-size": "10pt"})
        self._p_gyr.setLabel("bottom", "时间", units="s", **{"font-size": "10pt"})
        self._p_gyr.showGrid(x=True, y=True, alpha=0.25)
        self._c_gx = self._p_gyr.plot(pen=pen_gx, name="X")
        self._c_gy = self._p_gyr.plot(pen=pen_gy, name="Y")
        self._c_gz = self._p_gyr.plot(pen=pen_gz, name="Z")
        leg2 = self._p_gyr.addLegend(offset=(-10, 10))
        leg2.setParentItem(self._p_gyr.graphicsItem())

        return self._pw

    def _make_level_bars(self):
        """RMS 电平柱——类似音量表"""
        group = QGroupBox("⚡ 实时 RMS 电平  (0.01 ~ 5 mV)")
        group.setStyleSheet(
            "QGroupBox{font-weight:bold;font-size:13px;padding-top:6px;}"
        )
        lay = QHBoxLayout(group)

        def _bar(label, color):
            vlay = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size:12px;font-weight:bold;")
            bar = QProgressBar()
            bar.setOrientation(Qt.Vertical)
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedWidth(40)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #ccc; border-radius: 3px;
                    background: #eee;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(
                        x1:0, y1:1, x2:0, y2:0,
                        stop:0 {color}, stop:0.7 {color}cc,
                        stop:1 {_RED});
                    border-radius: 3px;
                }}
            """)
            val_lbl = QLabel("0.000 mV")
            val_lbl.setAlignment(Qt.AlignCenter)
            val_lbl.setStyleSheet("font-size:11px;")
            vlay.addWidget(lbl)
            vlay.addWidget(bar, stretch=1)
            vlay.addWidget(val_lbl)
            return vlay, bar, val_lbl

        lay1, self._bar_ch1, self._val_ch1 = _bar("CH1", _BLUE)
        lay2, self._bar_ch2, self._val_ch2 = _bar("CH2", _ORANGE)
        lay.addLayout(lay1)
        lay.addLayout(lay2)
        lay.addStretch(1)

        # 刻度说明
        scale_lbl = QLabel(
            "参考：\n"
            " 0~50 μV   基线静息\n"
            " 50~500 μV 轻度激活\n"
            " 500~5000 μV 强激活\n"
            " >5000 μV  可能伪迹"
        )
        scale_lbl.setStyleSheet("color:#666;font-size:11px;padding-left:20px;")
        lay.addWidget(scale_lbl)
        lay.addStretch(2)

        return group

    def _make_stats_panel(self):
        group = QGroupBox("📊 实时统计")
        group.setStyleSheet(
            "QGroupBox{font-weight:bold;font-size:13px;padding-top:6px;}"
        )
        lay = QHBoxLayout(group)

        # CH1 stats
        f1 = self._stat_frame("EMG CH1", _BLUE)
        fl1 = QVBoxLayout(f1)
        self._lbl_ch1_rms  = QLabel("RMS：-- mV")
        self._lbl_ch1_pp   = QLabel("峰峰值：-- mV")
        self._lbl_ch1_q    = QLabel("信号质量：--")
        for w in (self._lbl_ch1_rms, self._lbl_ch1_pp, self._lbl_ch1_q):
            fl1.addWidget(w)
        lay.addWidget(f1)

        # CH2 stats
        f2 = self._stat_frame("EMG CH2", _ORANGE)
        fl2 = QVBoxLayout(f2)
        self._lbl_ch2_rms  = QLabel("RMS：-- mV")
        self._lbl_ch2_pp   = QLabel("峰峰值：-- mV")
        self._lbl_ch2_q    = QLabel("信号质量：--")
        for w in (self._lbl_ch2_rms, self._lbl_ch2_pp, self._lbl_ch2_q):
            fl2.addWidget(w)
        lay.addWidget(f2)

        # 运动状态
        f3 = self._stat_frame("运动状态", _GREEN)
        fl3 = QVBoxLayout(f3)
        self._lbl_motion   = QLabel("运动伪迹：--")
        self._lbl_accel    = QLabel("合加速度：-- m/s²")
        self._lbl_gyro     = QLabel("角速度：-- °/s")
        for w in (self._lbl_motion, self._lbl_accel, self._lbl_gyro):
            fl3.addWidget(w)
        lay.addWidget(f3)

        # 采集状态
        f4 = self._stat_frame("采集状态", _PURPLE)
        fl4 = QVBoxLayout(f4)
        self._lbl_fs       = QLabel("实际采样率：-- Hz")
        self._lbl_samples  = QLabel("累计样本：0")
        self._lbl_status   = QLabel("状态：等待数据")
        for w in (self._lbl_fs, self._lbl_samples, self._lbl_status):
            fl4.addWidget(w)
        lay.addWidget(f4)

        return group

    @staticmethod
    def _stat_frame(title: str, color: str) -> QFrame:
        from app.monitors import _is_dark, tint
        tc = '#d4d4d4' if _is_dark() else '#333'
        bg = tint(color, 30)
        f = QFrame()
        f.setStyleSheet(f"""
            QFrame {{
                background:{bg}; border:2px solid {color};
                border-radius:8px; padding:8px;
            }}
            QLabel {{ color:{tc}; font-size:12px; padding:2px 0; }}
        """)
        return f

    # ── 定时刷新 ──────────────────────────────────────
    def _refresh(self):
        if getattr(self, '_dc', None) is None and self._collection_tab:
            dc = getattr(self._collection_tab, 'device_controller', None)
            if dc is not None:
                self.set_device_controller(dc)

        with self._lock:
            ch1 = list(self._ch1)
            ch2 = list(self._ch2)
            ax  = list(self._ax)
            ay  = list(self._ay)
            az  = list(self._az)
            gx  = list(self._gx)
            gy  = list(self._gy)
            gz  = list(self._gz)

        n = len(ch1)
        if n == 0:
            return

        t = np.arange(n) / self.fs

        # ── 波形 ─────────────────────────────────────
        if _PG:
            self._c_ch1.setData(t, ch1)
            self._c_ch2.setData(t, ch2)

            # 自动调整 Y 轴（保留 10% 余量）
            for arr, plot in ((ch1, self._p_ch1), (ch2, self._p_ch2)):
                if len(arr) > 10:
                    mn, mx = min(arr), max(arr)
                    margin = max((mx - mn) * 0.15, 0.05)
                    plot.setYRange(mn - margin, mx + margin)

            if ax:
                self._c_ax.setData(t, ax)
                self._c_ay.setData(t, ay)
                self._c_az.setData(t, az)

            if gx:
                self._c_gx.setData(t, gx)
                self._c_gy.setData(t, gy)
                self._c_gz.setData(t, gz)

        # ── RMS 电平柱 ────────────────────────────────
        rms1, rms2 = self._analyzer.rms()
        # log scale: 0.001 mV → 0%,  5 mV → 100%
        def _log_pct(v):
            if v < 1e-6:
                return 0
            import math
            lo, hi = math.log10(0.001), math.log10(5.0)
            pct = (math.log10(max(v, 0.001)) - lo) / (hi - lo) * 100
            return max(0, min(100, int(pct)))

        self._bar_ch1.setValue(_log_pct(rms1))
        self._bar_ch2.setValue(_log_pct(rms2))
        self._val_ch1.setText(f"{rms1*1000:.1f} μV")
        self._val_ch2.setText(f"{rms2*1000:.1f} μV")

        # ── 统计面板 ──────────────────────────────────
        if len(ch1) > 10:
            mn1, mx1 = min(ch1), max(ch1)
            mn2, mx2 = min(ch2), max(ch2)

            self._lbl_ch1_rms.setText(f"RMS：{rms1*1000:.2f} μV")
            self._lbl_ch1_pp.setText(f"峰峰值：{(mx1-mn1)*1000:.2f} μV")
            q1, c1 = self._analyzer.quality(rms1)
            self._lbl_ch1_q.setText(f"信号质量：{q1}")
            self._lbl_ch1_q.setStyleSheet(f"color:{c1};font-weight:bold;font-size:12px;")

            self._lbl_ch2_rms.setText(f"RMS：{rms2*1000:.2f} μV")
            self._lbl_ch2_pp.setText(f"峰峰值：{(mx2-mn2)*1000:.2f} μV")
            q2, c2 = self._analyzer.quality(rms2)
            self._lbl_ch2_q.setText(f"信号质量：{q2}")
            self._lbl_ch2_q.setStyleSheet(f"color:{c2};font-weight:bold;font-size:12px;")

        # 运动状态
        if ax:
            mag = math.sqrt(ax[-1]**2 + ay[-1]**2 + az[-1]**2)
            gyro_mag = math.sqrt(gx[-1]**2 + gy[-1]**2 + gz[-1]**2) if gx else 0
            motion = "⚠ 运动伪迹" if (gyro_mag > 30 or mag > 15) else "✓ 静止"
            self._lbl_motion.setText(f"运动伪迹：{motion}")
            self._lbl_accel.setText(f"合加速度：{mag:.2f} m/s²")
            self._lbl_gyro.setText(f"角速度：{gyro_mag:.1f} °/s")

        # 采集状态
        fs_actual = self._analyzer.actual_rate()
        n_total   = self._analyzer._n
        self._lbl_fs.setText(f"实际采样率：{fs_actual:.1f} Hz")
        self._lbl_samples.setText(f"累计样本：{n_total:,}")
        status = "🟢 采集中" if fs_actual > 100 else ("🟡 等待数据" if fs_actual > 0 else "⚪ 未开始")
        self._lbl_status.setText(f"状态：{status}")


# ── 独立运行入口（供 test_emg_unit.py --realtime 调用） ────────────────
class EMGViewerWindow(QMainWindow):
    """独立调试窗口，包裹 RealtimeEMGTab"""

    def __init__(self, fs: float = 1000.0):
        super().__init__()
        self.setWindowTitle("Shimmer EMG 实时监测")
        self.resize(1100, 850)
        self._tab = RealtimeEMGTab(fs=fs)
        self.setCentralWidget(self._tab)

    def push_sample(self, *args, **kwargs):
        self._tab.push_sample(*args, **kwargs)


def launch_viewer(fs: float = 1000.0) -> EMGViewerWindow:
    """
    从采集线程调用：创建 QApplication（如不存在）并返回窗口。
    必须在主线程调用；采集线程通过 window.push_sample() 传数据。
    """
    app = QApplication.instance()
    if app is None:
        import sys
        app = QApplication(sys.argv)

    win = EMGViewerWindow(fs=fs)
    win.show()
    return win, app


# ── 直接运行时显示演示数据 ─────────────────────────────
if __name__ == "__main__":
    import sys, math, random, threading

    app = QApplication(sys.argv)
    win = EMGViewerWindow(fs=1000.0)
    win.show()

    # 模拟数据推送
    _running = True

    def _sim():
        t = 0.0
        dt = 1 / 1000.0
        while _running:
            # 模拟 EMG（50 μV 基线 + 150 μV 随机噪声）
            ch1 = (0.05 + random.gauss(0, 0.15)) * 1e-3       # mV
            ch2 = (random.gauss(0, 0.03)) * 1e-3               # mV
            # 模拟加速度（重力 Z ≈ 9.8，小幅抖动）
            ax = random.gauss(0, 0.1)
            ay = random.gauss(0, 0.1)
            az = 9.81 + random.gauss(0, 0.05)
            # 模拟陀螺仪（静息接近 0）
            gx = random.gauss(0, 1.0)
            gy = random.gauss(0, 1.0)
            gz = random.gauss(0, 0.5)
            win.push_sample(ch1, ch2, ax, ay, az, gx, gy, gz)
            t += dt
            time.sleep(dt)

    th = threading.Thread(target=_sim, daemon=True)
    th.start()

    ret = app.exec_()
    _running = False
    sys.exit(ret)
