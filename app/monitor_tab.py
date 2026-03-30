"""
实时监控页面 — Fluent Design Pivot + QStackedWidget
内部 5 个监控子 Tab（GSR/EMG/EEG/视频/音频）保持原有实现不变
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QLabel
from PyQt5.QtCore import Qt

from qfluentwidgets import (
    SmoothScrollArea, Pivot, SubtitleLabel, BodyLabel,
    SimpleCardWidget, IndeterminateProgressBar,
)


class MonitorPage(SmoothScrollArea):
    """实时监控页面：Fluent Pivot 包裹 5 个已有监控 Tab"""

    def __init__(self, console_page, parent=None):
        super().__init__(parent)
        self.setObjectName("monitorPage")
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea{background:transparent; border:none;}")

        self._console = console_page

        container = QWidget()
        container.setStyleSheet("QWidget{background:transparent;}")
        self.setWidget(container)

        lay = QVBoxLayout(container)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(16)

        self._pivot = Pivot(self)
        lay.addWidget(self._pivot)

        self._stack = QStackedWidget()
        lay.addWidget(self._stack, stretch=1)

        self._tabs_loaded = False
        self._load_tabs()

    def _load_tabs(self):
        tab_loaders = [
            ("GSR / 外周生理", self._load_shimmer_tab),
            ("EMG 肌电",       self._load_emg_tab),
            ("EEG 脑电",       self._load_eeg_tab),
            ("视频",           self._load_video_tab),
            ("音频",           self._load_audio_tab),
        ]

        for name, loader in tab_loaders:
            widget = loader()
            self._stack.addWidget(widget)
            self._pivot.addItem(
                routeKey=name,
                text=name,
                onClick=lambda _, w=widget: self._stack.setCurrentWidget(w),
            )

        if tab_loaders:
            self._pivot.setCurrentItem(tab_loaders[0][0])
        self._tabs_loaded = True

    def _load_shimmer_tab(self) -> QWidget:
        try:
            from app.monitors.gsr_tab import RealtimeShimmerTab
            return RealtimeShimmerTab(self._console)
        except Exception as e:
            return self._error_placeholder(f"GSR/Shimmer 加载失败：{e}")

    def _load_emg_tab(self) -> QWidget:
        try:
            from app.monitors.emg_tab import RealtimeEMGTab
            tab = RealtimeEMGTab(self._console)
            if self._console.device_controller:
                tab.set_device_controller(self._console.device_controller)
            return tab
        except Exception as e:
            return self._error_placeholder(f"EMG 加载失败：{e}")

    def _load_eeg_tab(self) -> QWidget:
        try:
            from app.monitors.eeg_tab import RealtimeEEGTab
            tab = RealtimeEEGTab(self._console)
            if self._console.device_controller:
                tab.set_device_controller(self._console.device_controller)
            return tab
        except Exception as e:
            return self._error_placeholder(f"EEG 加载失败：{e}")

    def _load_video_tab(self) -> QWidget:
        try:
            from app.monitors.video_tab import RealtimeVideoTab
            return RealtimeVideoTab(self._console)
        except Exception as e:
            return self._error_placeholder(f"视频加载失败：{e}")

    def _load_audio_tab(self) -> QWidget:
        try:
            from app.monitors.audio_tab import RealtimeAudioTab
            return RealtimeAudioTab(self._console)
        except Exception as e:
            return self._error_placeholder(f"音频加载失败：{e}")

    @staticmethod
    def _error_placeholder(message: str) -> QWidget:
        card = SimpleCardWidget()
        card.setMinimumHeight(300)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setAlignment(Qt.AlignCenter)

        title = SubtitleLabel("模块加载失败")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        lay.addSpacing(12)

        bar = IndeterminateProgressBar()
        bar.setFixedWidth(200)
        bar.stop()
        lay.addWidget(bar, alignment=Qt.AlignCenter)

        lay.addSpacing(12)

        desc = BodyLabel(message)
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        return card
