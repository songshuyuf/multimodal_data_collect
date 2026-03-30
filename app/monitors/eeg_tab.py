"""
实时EEG信号显示Tab — pyqtgraph 版
支持 Neuracle HEEG 64通道脑电信号实时显示，可选通道范围
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFrame, QSpinBox,
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


class RealtimeEEGTab(QWidget):
    """实时EEG信号显示Tab — 支持 64 通道可选"""

    def __init__(self, device_controller=None):
        super().__init__()
        self.device_controller = device_controller

        self._ch_start = 0
        self._ch_count = 8
        self._total_channels = 64

        self._plots: list = []
        self._curves: list = []

        self._init_ui()

        self._timer = QTimer()
        self._timer.timeout.connect(self._update_display)
        self._timer.start(50)

    def _init_ui(self):
        layout = QVBoxLayout()

        header = self._build_header()
        layout.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        if PYQTGRAPH_AVAILABLE:
            self._pg = pg.GraphicsLayoutWidget()
            from app.monitors import theme_pg_layout
            theme_pg_layout(self._pg)
            layout.addWidget(self._pg, stretch=1)
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

        ch_group = QGroupBox("通道选择")
        ch_lay = QHBoxLayout()
        ch_lay.addWidget(QLabel("起始:"))
        self._sp_start = QSpinBox()
        self._sp_start.setRange(1, 64)
        self._sp_start.setValue(1)
        self._sp_start.valueChanged.connect(self._on_channel_changed)
        ch_lay.addWidget(self._sp_start)
        ch_lay.addWidget(QLabel("显示:"))
        self._sp_count = QSpinBox()
        self._sp_count.setRange(1, 16)
        self._sp_count.setValue(8)
        self._sp_count.valueChanged.connect(self._on_channel_changed)
        ch_lay.addWidget(self._sp_count)
        ch_group.setLayout(ch_lay)
        layout.addWidget(ch_group)

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

    def _on_channel_changed(self):
        self._ch_start = self._sp_start.value() - 1
        self._ch_count = self._sp_count.value()
        if PYQTGRAPH_AVAILABLE:
            self._rebuild_plots()

    def _rebuild_plots(self):
        self._pg.clear()
        self._plots.clear()
        self._curves.clear()

        from app.monitors import _is_dark
        dark = _is_dark()
        fg = '#d4d4d4' if dark else '#333333'

        n = self._ch_count
        for i in range(n):
            ch_idx = self._ch_start + i
            p = self._pg.addPlot(row=i, col=0)
            p.setLabel('left', f'Ch{ch_idx + 1}', units='μV', color=fg)
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
            if total_ch != self._total_channels:
                self._total_channels = total_ch
                self._sp_start.setRange(1, max(1, total_ch))
                self._sp_count.setRange(1, min(16, total_ch))

            ch0 = self._ch_start
            for i, curve in enumerate(self._curves):
                ch = ch0 + i
                if ch < total_ch:
                    curve.setData(data[ch, :])
                    self._plots[i].setLabel('left', f'Ch{ch + 1}', units='μV')

        except Exception:
            pass

    def clear_display(self):
        for c in self._curves:
            c.setData([])

    def set_device_controller(self, controller):
        self.device_controller = controller
