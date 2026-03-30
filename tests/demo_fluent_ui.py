"""
Fluent Design UI 演示 — AI 艺术诊疗多模态采集系统
独立运行，不依赖项目任何模块，纯 mock 数据。
"""

import sys, json, os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidgetItem, QHeaderView, QStackedWidget, QSizePolicy,
    QSpacerItem, QGridLayout, QFrame,
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont, QColor

from qfluentwidgets import (
    MSFluentWindow, NavigationItemPosition,
    FluentIcon as FIF, setTheme, Theme, isDarkTheme, toggleTheme,
    HeaderCardWidget, SimpleCardWidget, CardWidget,
    PrimaryPushButton, PushButton, TransparentPushButton,
    ToolButton, TransparentToolButton,
    ComboBox, ProgressBar, IndeterminateProgressBar,
    TableWidget, Pivot,
    TitleLabel, SubtitleLabel, StrongBodyLabel, BodyLabel, CaptionLabel,
    InfoBadge, InfoLevel,
    SmoothScrollArea,
    setFont,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TASKS = [
    {"id": 1, "name": "静息态EEG",        "dur": 300},
    {"id": 2, "name": "Dot-probe任务",    "dur": 300},
    {"id": 3, "name": "绘画作品欣赏",     "dur": 297},
    {"id": 4, "name": "音乐欣赏",         "dur": 485},
    {"id": 5, "name": "VR沉浸体验",       "dur": 180},
    {"id": 6, "name": "语音任务A：朗读",   "dur": 180},
    {"id": 7, "name": "语音任务B：访谈",   "dur": 180},
    {"id": 8, "name": "语音任务C：图像描述","dur": 180},
]

try:
    cfg_path = os.path.join(PROJECT_ROOT, "experiment_config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        _cfg = json.load(f)
    TASKS = [
        {"id": t["id"], "name": t["display_name"], "dur": t["duration"]}
        for t in _cfg.get("tasks", TASKS)
    ]
except Exception:
    pass

DEVICES = [
    ("EEG 脑电",   FIF.HEART,    "Neuracle HEEG-16"),
    ("GSR / PPG",  FIF.IOT,      "Shimmer GSR+"),
    ("EMG 肌电",   FIF.CALORIES, "Shimmer EMG"),
    ("摄像头",     FIF.CAMERA,   "USB Camera 0"),
    ("麦克风",     FIF.MICROPHONE,"Default Input"),
]


# ─── 滚动包装器 ────────────────────────────────────────────────

class ScrollPage(SmoothScrollArea):
    """可滚动子页面基类"""

    def __init__(self, object_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea{background:transparent; border:none;}")

        self._container = QWidget()
        self._container.setStyleSheet("QWidget{background:transparent;}")
        self.setWidget(self._container)

        self.vBoxLayout = QVBoxLayout(self._container)
        self.vBoxLayout.setContentsMargins(36, 28, 36, 28)
        self.vBoxLayout.setSpacing(20)
        self.vBoxLayout.setAlignment(Qt.AlignTop)


# ═══════════════════════════════════════════════════════════════
#  页面 1 ：主控台
# ═══════════════════════════════════════════════════════════════

class ConsolePage(ScrollPage):

    def __init__(self, parent=None):
        super().__init__("consolePage", parent)
        self._elapsed = 0
        self._running = False

        self._build_patient_card()
        self._build_experiment_card()
        self._build_device_card()
        self._build_overview_table()
        self._build_progress_card()

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._tick)

    # ── 患者 ──

    def _build_patient_card(self):
        card = HeaderCardWidget(self)
        card.setTitle("Step 1 · 选择患者")

        row = QHBoxLayout()
        row.setSpacing(12)

        self._combo = ComboBox()
        self._combo.setMinimumWidth(280)
        self._combo.addItems([
            "— 请选择患者 —",
            "张三（ID: 63028）[焦虑]",
            "李四（ID: 11082）[抑郁]",
        ])
        row.addWidget(self._combo)

        btn_new = PrimaryPushButton(FIF.ADD, "新建患者")
        btn_new.setFixedHeight(34)
        row.addWidget(btn_new)

        btn_edit = PushButton(FIF.EDIT, "编辑")
        btn_edit.setFixedHeight(34)
        row.addWidget(btn_edit)

        row.addStretch()

        self._patient_info = BodyLabel("姓名：张三    年龄：28    性别：男    诊断：焦虑")
        self._patient_info.setStyleSheet(
            "padding: 8px 14px; background: rgba(128,128,128,0.08); border-radius: 6px;"
        )

        card.viewLayout.addLayout(row)
        card.viewLayout.addWidget(self._patient_info)
        self.vBoxLayout.addWidget(card)

    # ── 实验控制 ──

    def _build_experiment_card(self):
        card = HeaderCardWidget(self)
        card.setTitle("Step 2 · 实验控制")

        btn_row = QHBoxLayout()
        btn_row.setSpacing(14)

        self._btn_start = PrimaryPushButton(FIF.PLAY, "开始采集实验")
        self._btn_start.setFixedHeight(52)
        self._btn_start.setMinimumWidth(260)
        setFont(self._btn_start, 16, QFont.Bold)
        self._btn_start.clicked.connect(self._on_start)
        btn_row.addWidget(self._btn_start, stretch=3)

        self._btn_stop = PushButton(FIF.CLOSE, "停止")
        self._btn_stop.setFixedHeight(52)
        self._btn_stop.setEnabled(False)
        setFont(self._btn_stop, 16, QFont.Bold)
        self._btn_stop.clicked.connect(self._on_stop)
        btn_row.addWidget(self._btn_stop, stretch=1)

        card.viewLayout.addLayout(btn_row)

        self._timer_label = TitleLabel("00:00:00")
        self._timer_label.setAlignment(Qt.AlignCenter)
        card.viewLayout.addWidget(self._timer_label)

        self._stats_label = CaptionLabel(
            "EEG: —  |  GSR: —  |  EMG: —  |  视频: —  |  音频: —"
        )
        self._stats_label.setAlignment(Qt.AlignCenter)
        card.viewLayout.addWidget(self._stats_label)

        self.vBoxLayout.addWidget(card)

    # ── 设备 ──

    def _build_device_card(self):
        card = HeaderCardWidget(self)
        card.setTitle("设备检测")

        self._device_badges = []

        for name, icon, model in DEVICES:
            row = QHBoxLayout()
            row.setSpacing(12)

            icon_label = ToolButton(icon)
            icon_label.setFixedSize(32, 32)
            icon_label.setEnabled(False)
            row.addWidget(icon_label)

            name_lbl = StrongBodyLabel(name)
            name_lbl.setFixedWidth(90)
            row.addWidget(name_lbl)

            model_lbl = CaptionLabel(model)
            row.addWidget(model_lbl, stretch=1)

            badge = InfoBadge.warning("未检测")
            badge.setFixedHeight(22)
            self._device_badges.append(badge)
            row.addWidget(badge)

            btn = PushButton("连接")
            btn.setFixedSize(72, 30)
            btn.clicked.connect(
                lambda _, b=badge: self._mock_connect(b)
            )
            row.addWidget(btn)

            card.viewLayout.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_detect = PushButton(FIF.SEARCH, "检测所有设备")
        btn_detect.setFixedHeight(38)
        btn_detect.clicked.connect(self._mock_detect_all)
        btn_row.addWidget(btn_detect)

        btn_connect = PrimaryPushButton(FIF.LINK, "一键连接全部")
        btn_connect.setFixedHeight(38)
        btn_connect.clicked.connect(self._mock_connect_all)
        btn_row.addWidget(btn_connect)

        card.viewLayout.addLayout(btn_row)
        self.vBoxLayout.addWidget(card)

    # ── 实验概览表 ──

    def _build_overview_table(self):
        card = HeaderCardWidget(self)
        total_min = sum(t["dur"] for t in TASKS) // 60
        card.setTitle(f"实验概览   ·   {len(TASKS)} 个环节   ·   约 {total_min} 分钟")

        self._table = TableWidget(self)
        self._table.setBorderVisible(True)
        self._table.setBorderRadius(8)
        self._table.setColumnCount(3)
        self._table.setRowCount(len(TASKS))
        self._table.setHorizontalHeaderLabels(["序号", "任务名称", "时长"])
        self._table.verticalHeader().hide()

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        for i, t in enumerate(TASKS):
            self._table.setItem(i, 0, QTableWidgetItem(str(t["id"])))
            self._table.setItem(i, 1, QTableWidgetItem(t["name"]))
            self._table.setItem(i, 2, QTableWidgetItem(f'{t["dur"] // 60} min'))
            self._table.setRowHeight(i, 42)

        self._table.setEditTriggers(TableWidget.NoEditTriggers)
        self._table.setMinimumHeight(len(TASKS) * 42 + 46)

        card.viewLayout.addWidget(self._table)
        self.vBoxLayout.addWidget(card)

    # ── 进度 ──

    def _build_progress_card(self):
        card = HeaderCardWidget(self)
        card.setTitle("实验进度")

        row1 = QHBoxLayout()
        self._task_name_lbl = StrongBodyLabel("等待开始...")
        row1.addWidget(self._task_name_lbl)
        row1.addStretch()
        self._task_idx_lbl = CaptionLabel("0 / 8")
        row1.addWidget(self._task_idx_lbl)
        card.viewLayout.addLayout(row1)

        self._task_bar = ProgressBar()
        self._task_bar.setRange(0, 100)
        self._task_bar.setValue(0)
        card.viewLayout.addWidget(self._task_bar)

        row2 = QHBoxLayout()
        row2.addWidget(CaptionLabel("整体进度"))
        self._overall_bar = ProgressBar()
        self._overall_bar.setRange(0, len(TASKS))
        self._overall_bar.setValue(0)
        row2.addWidget(self._overall_bar, stretch=1)
        self._overall_lbl = CaptionLabel(f"0 / {len(TASKS)}")
        row2.addWidget(self._overall_lbl)
        card.viewLayout.addLayout(row2)

        time_row = QHBoxLayout()
        time_row.addWidget(CaptionLabel("已用时"))
        self._elapsed_lbl = StrongBodyLabel("00:00:00")
        time_row.addWidget(self._elapsed_lbl)
        time_row.addStretch()
        time_row.addWidget(CaptionLabel("当前任务剩余"))
        self._remain_lbl = StrongBodyLabel("—")
        time_row.addWidget(self._remain_lbl)
        card.viewLayout.addLayout(time_row)

        self.vBoxLayout.addWidget(card)

    # ── 模拟操作 ──

    def _on_start(self):
        self._running = True
        self._elapsed = 0
        self._current_task = 0
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._tick_timer.start()
        self._update_task()

    def _on_stop(self):
        self._running = False
        self._tick_timer.stop()
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._task_name_lbl.setText("已停止")

    def _tick(self):
        self._elapsed += 1
        h, r = divmod(self._elapsed, 3600)
        m, s = divmod(r, 60)
        self._timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
        self._elapsed_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")

        if self._current_task < len(TASKS):
            t = TASKS[self._current_task]
            pct = min(100, int(
                (self._elapsed - sum(tt["dur"] for tt in TASKS[:self._current_task]))
                / max(t["dur"], 1) * 100
            ))
            self._task_bar.setValue(pct)
            remain = t["dur"] - (self._elapsed - sum(tt["dur"] for tt in TASKS[:self._current_task]))
            if remain <= 0:
                self._current_task += 1
                self._update_task()
            else:
                rm, rs = divmod(max(remain, 0), 60)
                self._remain_lbl.setText(f"{rm:02d}:{rs:02d}")

        self._stats_label.setText(
            f"EEG: {self._elapsed * 64} 样本  |  GSR: {self._elapsed} 包  |  "
            f"EMG: {self._elapsed} 包  |  视频: {self._elapsed * 30} 帧  |  "
            f"音频: {self._elapsed * 44100} 样本"
        )

    def _update_task(self):
        if self._current_task < len(TASKS):
            t = TASKS[self._current_task]
            self._task_name_lbl.setText(t["name"])
            self._task_idx_lbl.setText(f"{self._current_task + 1} / {len(TASKS)}")
            self._overall_bar.setValue(self._current_task)
            self._overall_lbl.setText(f"{self._current_task} / {len(TASKS)}")
            self._task_bar.setValue(0)
            self._table.selectRow(self._current_task)
        else:
            self._on_stop()
            self._task_name_lbl.setText("实验已完成")
            self._overall_bar.setValue(len(TASKS))
            self._overall_lbl.setText(f"{len(TASKS)} / {len(TASKS)}")
            self._task_bar.setValue(100)

    def _mock_detect_all(self):
        for badge in self._device_badges:
            badge.setText("已找到")
            badge.setLevel(InfoLevel.SUCCESS)

    def _mock_connect(self, badge):
        badge.setText("已连接")
        badge.setLevel(InfoLevel.SUCCESS)

    def _mock_connect_all(self):
        for badge in self._device_badges:
            badge.setText("已连接")
            badge.setLevel(InfoLevel.SUCCESS)


# ═══════════════════════════════════════════════════════════════
#  页面 2 ：实时监控
# ═══════════════════════════════════════════════════════════════

class MonitorPage(ScrollPage):

    def __init__(self, parent=None):
        super().__init__("monitorPage", parent)

        self._pivot = Pivot(self)
        self.vBoxLayout.addWidget(self._pivot)

        self._stack = QStackedWidget(self)
        self.vBoxLayout.addWidget(self._stack, stretch=1)

        monitors = [
            ("GSR / 外周生理", FIF.IOT,
             "GSR 电导 · PPG 光电容积 · 心率 · 皮肤温度\n\n实时波形将在此显示"),
            ("EMG 肌电", FIF.CALORIES,
             "EMG CH1 / CH2 · 加速度 · 陀螺仪\n\n实时波形将在此显示"),
            ("EEG 脑电", FIF.HEART,
             "64 通道 EEG · Alpha / Beta / Theta 频段\n\n实时脑电拓扑图将在此显示"),
            ("视频", FIF.CAMERA,
             "实时摄像头画面 · FPS · 分辨率\n\n视频预览将在此显示"),
            ("音频", FIF.MICROPHONE,
             "实时音频波形 · 频谱图 · 音量\n\n音频波形将在此显示"),
        ]

        for name, icon, desc in monitors:
            page = self._make_monitor_card(name, desc)
            self._stack.addWidget(page)
            self._pivot.addItem(
                routeKey=name,
                text=name,
                onClick=lambda _, w=page: self._stack.setCurrentWidget(w),
            )

        self._pivot.setCurrentItem(monitors[0][0])

    def _make_monitor_card(self, title: str, desc: str) -> QWidget:
        card = SimpleCardWidget()
        card.setMinimumHeight(400)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(30, 30, 30, 30)
        lay.setAlignment(Qt.AlignCenter)

        icon_lbl = SubtitleLabel(title)
        icon_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon_lbl)

        lay.addSpacing(16)

        bar = IndeterminateProgressBar()
        bar.setFixedWidth(300)
        lay.addWidget(bar, alignment=Qt.AlignCenter)

        lay.addSpacing(16)

        desc_lbl = BodyLabel(desc)
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setWordWrap(True)
        lay.addWidget(desc_lbl)

        return card


# ═══════════════════════════════════════════════════════════════
#  页面 3 ：关于
# ═══════════════════════════════════════════════════════════════

class AboutPage(ScrollPage):

    def __init__(self, parent=None):
        super().__init__("aboutPage", parent)

        self.vBoxLayout.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.setSpacing(16)

        title = TitleLabel("AI 艺术诊疗多模态采集系统")
        title.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(title)

        ver = SubtitleLabel("v4.0  ·  Fluent Design 重构版")
        ver.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(ver)

        self.vBoxLayout.addSpacing(24)

        desc_card = SimpleCardWidget()
        desc_lay = QVBoxLayout(desc_card)
        desc_lay.setContentsMargins(32, 24, 32, 24)
        desc_lay.setSpacing(12)

        for line in [
            "多模态生理信号同步采集系统",
            "支持 EEG（Neuracle HEEG）、GSR/PPG（Shimmer GSR+）、EMG、视频、音频",
            "面向艺术诊疗实验研究，支持 BIDS 标准数据格式输出",
            "",
            "架构：app/ (GUI) + engine/ (实验引擎) + devices/ (设备层) + data/ (数据层)",
        ]:
            if line:
                lbl = BodyLabel(line)
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setWordWrap(True)
                desc_lay.addWidget(lbl)
            else:
                desc_lay.addSpacing(8)

        self.vBoxLayout.addWidget(desc_card)

        self.vBoxLayout.addSpacing(16)

        tech_card = SimpleCardWidget()
        tech_lay = QHBoxLayout(tech_card)
        tech_lay.setContentsMargins(24, 16, 24, 16)
        tech_lay.setSpacing(10)
        tech_lay.setAlignment(Qt.AlignCenter)

        for tag in ["PyQt5", "Fluent Widgets", "SQLite", "OpenCV",
                     "pylsl", "pyqtgraph", "edge-tts", "ADB"]:
            badge = InfoBadge(tag)
            badge.setFixedHeight(26)
            badge.setLevel(InfoLevel.INFOAMTION)
            tech_lay.addWidget(badge)

        self.vBoxLayout.addWidget(tech_card)

        self.vBoxLayout.addSpacing(12)

        footer = CaptionLabel("Westlake University · TGAI Lab")
        footer.setAlignment(Qt.AlignCenter)
        self.vBoxLayout.addWidget(footer)


# ═══════════════════════════════════════════════════════════════
#  主窗口
# ═══════════════════════════════════════════════════════════════

class DemoFluentWindow(MSFluentWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 艺术诊疗多模态采集系统 v4.0  [Fluent 预览]")
        self.resize(1360, 860)

        self._console = ConsolePage(self)
        self._monitor = MonitorPage(self)
        self._about   = AboutPage(self)

        self.addSubInterface(self._console, FIF.COMMAND_PROMPT, "主控台")
        self.addSubInterface(self._monitor, FIF.IOT,           "实时监控")
        self.addSubInterface(self._about,   FIF.INFO,          "关于",
                             position=NavigationItemPosition.BOTTOM)

        self.navigationInterface.addItem(
            routeKey="theme",
            icon=FIF.CONSTRACT,
            text="切换主题",
            onClick=lambda: toggleTheme(lazy=True),
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        self.navigationInterface.setCurrentItem("consolePage")


# ═══════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI艺术诊疗多模态采集系统")

    setTheme(Theme.DARK)

    window = DemoFluentWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
