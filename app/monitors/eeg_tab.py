"""
实时EEG信号显示Tab — pyqtgraph 版
固定显示全部 64 通道脑电信号（垂直排列，每通道独立子图，可滚动）
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFrame, QScrollArea,
)
from PyQt5.QtCore import Qt, QTimer
import numpy as np

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False

_PLOT_COLORS = [
    "#b39ddb", "#ce93d8", "#f48fb1", "#ef9a9a",
    "#ffcc80", "#fff59d", "#c5e1a5", "#80cbc4",
    "#81d4fa", "#90caf9", "#a5d6a7", "#e6ee9c",
    "#ffab91", "#bcaaa4", "#b0bec5", "#80deea",
]

_MAX_CHANNELS = 64
_PLOT_HEIGHT_PX = 60   # height per channel row in pixels


class RealtimeEEGTab(QWidget):
    """实时EEG信号显示Tab — 固定显示全部 64 通道"""

    def __init__(self, device_controller=None):
        super().__init__()
        self.device_controller = device_controller

        self._total_channels = _MAX_CHANNELS
        self._plots: list = []
        self._curves: list = []

        self._init_ui()

        self._timer = QTimer()
        self._timer.timeout.connect(self._update_display)
        self._timer.start(50)

    # ── UI ──────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = self._build_header()
        layout.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        if PYQTGRAPH_AVAILABLE:
            # Wrap the tall GraphicsLayoutWidget in a scroll area
            self._pg = pg.GraphicsLayoutWidget()
            self._pg.setMinimumHeight(_PLOT_HEIGHT_PX * _MAX_CHANNELS)

            from app.monitors import theme_pg_layout
            theme_pg_layout(self._pg)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(self._pg)
            scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")
            layout.addWidget(scroll, stretch=1)

            self._rebuild_plots()
        else:
            layout.addWidget(QLabel("pyqtgraph 未安装，无法显示波形"))

        self.setLayout(layout)

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        from app.monitors import _is_dark, tint
        title = QLabel("🧠 HEEG 脑电信号")
        _tbg = tint('#9C27B0', 25) if _is_dark() else 'transparent'
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 18px; font-weight: bold;
                color: #9C27B0; padding: 10px;
                background-color: {_tbg}; border-radius: 5px;
            }}
        """)
        layout.addWidget(title)
        layout.addStretch()

        status_group = QGroupBox("设备状态")
        sl = QHBoxLayout()
        self._status_label = QLabel("未连接")
        self._status_label.setStyleSheet("color: red; font-weight: bold;")
        sl.addWidget(QLabel("HEEG:"))
        sl.addWidget(self._status_label)
        status_group.setLayout(sl)
        layout.addWidget(status_group)

        stats_group = QGroupBox("统计信息")
        st = QHBoxLayout()
        st.addWidget(QLabel("包:"))
        self._pkt_label = QLabel("0")
        st.addWidget(self._pkt_label)
        st.addWidget(QLabel("样本:"))
        self._samp_label = QLabel("0")
        st.addWidget(self._samp_label)
        st.addWidget(QLabel("Trigger:"))
        self._trigger_label = QLabel("-")
        st.addWidget(self._trigger_label)
        stats_group.setLayout(st)
        layout.addWidget(stats_group)

        return layout

    def _rebuild_plots(self):
        self._pg.clear()
        self._plots.clear()
        self._curves.clear()

        from app.monitors import _is_dark
        dark = _is_dark()
        fg = '#d4d4d4' if dark else '#333333'

        n = self._total_channels
        for i in range(n):
            p = self._pg.addPlot(row=i, col=0)
            p.setFixedHeight(_PLOT_HEIGHT_PX)
            p.setLabel('left', f'Ch{i + 1}', units='μV', color=fg)
            p.showGrid(y=True, alpha=0.2)
            p.setMouseEnabled(x=False, y=False)
            if i < n - 1:
                p.hideAxis('bottom')
            else:
                p.setLabel('bottom', '样本点', color=fg)

            for axis_name in ('left', 'bottom'):
                ax = p.getAxis(axis_name)
                ax.setPen(fg)
                ax.setTextPen(fg)

            color = _PLOT_COLORS[i % len(_PLOT_COLORS)]
            curve = p.plot(pen=pg.mkPen(color, width=1))
            self._plots.append(p)
            self._curves.append(curve)

    # ── 更新 ────────────────────────────────────────────────────────

    def _update_display(self):
        try:
            dc = self.device_controller
            if not dc:
                return

            ready = getattr(dc, 'heeg_ready', False)
            if ready:
                self._status_label.setText("已连接")
                self._status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self._status_label.setText("未连接")
                self._status_label.setStyleSheet("color: red; font-weight: bold;")
                return

            pkt = getattr(dc, 'heeg_packet_count', 0)
            samp = getattr(dc, 'heeg_sample_count', 0)
            self._pkt_label.setText(f"{pkt:,}")
            self._samp_label.setText(f"{samp:,}")

            data = dc.get_realtime_heeg_data(2000)
            if data is None:
                return

            total_ch = data.shape[0]
            # If device reports more channels than expected, rebuild plots once
            if total_ch != self._total_channels and PYQTGRAPH_AVAILABLE:
                self._total_channels = total_ch
                self._pg.setMinimumHeight(_PLOT_HEIGHT_PX * total_ch)
                self._rebuild_plots()

            for i, curve in enumerate(self._curves):
                if i < total_ch:
                    curve.setData(data[i, :])

        except Exception:
            pass

    # ── 公开接口 ────────────────────────────────────────────────────

    def clear_display(self):
        for c in self._curves:
            c.setData([])

    def set_device_controller(self, controller):
        self.device_controller = controller
