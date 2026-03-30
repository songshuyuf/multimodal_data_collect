"""实验概览卡 + 实验进度面板 — Fluent Design 版"""

import json
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem, QHeaderView,
    QSizePolicy,
)
from PyQt5.QtCore import Qt

from qfluentwidgets import (
    HeaderCardWidget, TableWidget,
    ProgressBar, StrongBodyLabel, CaptionLabel, BodyLabel,
)


class ExperimentOverviewCard(HeaderCardWidget):
    """从 experiment_config.json 读取并显示实验任务列表（Fluent TableWidget）"""

    def __init__(self, config_path: str = "./experiment_config.json", parent=None):
        super().__init__(parent)
        self._config_path = config_path
        self._tasks = []
        self._load_config()
        self._build()

    def _load_config(self):
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            self._tasks = cfg.get('tasks', [])
            self._total_sec = cfg.get('total_duration', 0)
        except Exception:
            self._tasks = []
            self._total_sec = 0

    def _build(self):
        total_min = self._total_sec // 60
        self.setTitle(
            f"实验概览   ·   {len(self._tasks)} 个环节   ·   约 {total_min} 分钟"
        )

        if not self._tasks:
            self.viewLayout.addWidget(
                CaptionLabel("暂无实验配置，请检查 experiment_config.json")
            )
            return

        self._table = TableWidget(self)
        self._table.setBorderVisible(True)
        self._table.setBorderRadius(8)
        self._table.setColumnCount(3)
        self._table.setRowCount(len(self._tasks))
        self._table.setHorizontalHeaderLabels(["序号", "任务名称", "时长"])
        self._table.verticalHeader().hide()

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        for i, t in enumerate(self._tasks):
            self._table.setItem(i, 0, QTableWidgetItem(str(t.get('id', i + 1))))
            self._table.setItem(
                i, 1, QTableWidgetItem(t.get('display_name', t.get('name', '')))
            )
            dur = t.get('duration', 0) // 60
            self._table.setItem(i, 2, QTableWidgetItem(f"{dur} min"))
            self._table.setRowHeight(i, 42)

        self._table.setEditTriggers(TableWidget.NoEditTriggers)
        self._table.setMinimumHeight(len(self._tasks) * 42 + 46)

        self.viewLayout.addWidget(self._table)


class ExperimentProgressPanel(HeaderCardWidget):
    """实验进行时的实时进度显示（Fluent ProgressBar）"""

    def __init__(self, total_tasks: int = 8, parent=None):
        super().__init__(parent)
        self.setTitle("实验进度")
        self._total = total_tasks
        self._build()

    def _build(self):
        row1 = QHBoxLayout()
        self._task_label = StrongBodyLabel("准备中...")
        row1.addWidget(self._task_label)
        row1.addStretch()
        self._task_index = CaptionLabel("0 / 0")
        row1.addWidget(self._task_index)
        self.viewLayout.addLayout(row1)

        self._task_bar = ProgressBar()
        self._task_bar.setRange(0, 100)
        self._task_bar.setValue(0)
        self.viewLayout.addWidget(self._task_bar)

        row2 = QHBoxLayout()
        row2.addWidget(CaptionLabel("整体进度"))
        self._overall_bar = ProgressBar()
        self._overall_bar.setRange(0, self._total)
        self._overall_bar.setValue(0)
        row2.addWidget(self._overall_bar, stretch=1)
        self._overall_pct = CaptionLabel(f"0/{self._total}")
        row2.addWidget(self._overall_pct)
        self.viewLayout.addLayout(row2)

        time_row = QHBoxLayout()
        time_row.addWidget(CaptionLabel("已用时"))
        self._elapsed_lbl = StrongBodyLabel("00:00:00")
        time_row.addWidget(self._elapsed_lbl)
        time_row.addStretch()
        time_row.addWidget(CaptionLabel("当前任务剩余"))
        self._remain_lbl = StrongBodyLabel("—")
        time_row.addWidget(self._remain_lbl)
        self.viewLayout.addLayout(time_row)

    # ═══════════════════════════════════════════════════════════
    #  公开 API（保持兼容）
    # ═══════════════════════════════════════════════════════════

    def update_task(self, name: str, index: int, total: int):
        self._task_label.setText(name)
        self._task_index.setText(f"{index} / {total}")
        self._overall_bar.setMaximum(total)
        self._overall_bar.setValue(index - 1)
        self._overall_pct.setText(f"{index - 1}/{total}")
        self._task_bar.setValue(0)

    def update_task_progress(self, current: int, total: int):
        if total > 0:
            pct = int(current / total * 100)
            self._task_bar.setValue(pct)

    def update_elapsed(self, elapsed_sec: int, task_remain_sec: Optional[int] = None):
        h, r = divmod(elapsed_sec, 3600)
        m, s = divmod(r, 60)
        self._elapsed_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")
        if task_remain_sec is not None:
            m2, s2 = divmod(task_remain_sec, 60)
            self._remain_lbl.setText(f"{m2:02d}:{s2:02d}")

    def mark_finished(self, total: int):
        self._task_label.setText("实验已完成")
        self._overall_bar.setValue(total)
        self._overall_pct.setText(f"{total}/{total}")
        self._task_bar.setValue(100)
        self._remain_lbl.setText("完成")
