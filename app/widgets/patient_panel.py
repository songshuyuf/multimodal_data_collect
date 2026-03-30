"""患者选择/管理面板 — Fluent Design 版，保留全部 DB 业务逻辑"""

from typing import Optional

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import pyqtSignal

from qfluentwidgets import (
    HeaderCardWidget,
    PrimaryPushButton, PushButton, TransparentToolButton,
    ComboBox, BodyLabel,
    FluentIcon as FIF,
)
from PyQt5.QtWidgets import QHBoxLayout

from data.database import DatabaseManager
from data.models import Patient
from .patient_dialog import PatientDialog


class PatientPanel(HeaderCardWidget):
    """Step 1: 患者选择面板（Fluent 卡片）"""

    patient_changed = pyqtSignal(object)
    log_message = pyqtSignal(str)

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.setTitle("Step 1 · 选择患者")

        self.db = db
        self.current_patient: Optional[Patient] = None

        self._build()
        self._load_patients()

    def _build(self):
        self._patient_combo = ComboBox()
        self._patient_combo.setMinimumWidth(280)
        self._patient_combo.currentIndexChanged.connect(self._on_patient_selected)
        self.viewLayout.addWidget(self._patient_combo)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_new = PrimaryPushButton(FIF.ADD, "新建患者")
        self._btn_new.setFixedHeight(34)
        self._btn_new.clicked.connect(self._on_new_patient)
        btn_row.addWidget(self._btn_new)

        self._btn_edit = PushButton(FIF.EDIT, "编辑")
        self._btn_edit.setFixedHeight(34)
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._on_edit_patient)
        btn_row.addWidget(self._btn_edit)

        btn_row.addStretch()

        self._btn_refresh = TransparentToolButton(FIF.SYNC)
        self._btn_refresh.setFixedSize(34, 34)
        self._btn_refresh.setToolTip("刷新患者列表")
        self._btn_refresh.clicked.connect(self._load_patients)
        btn_row.addWidget(self._btn_refresh)

        self.viewLayout.addLayout(btn_row)

        self._patient_info = BodyLabel("请选择患者")
        self._patient_info.setStyleSheet(
            "padding: 8px 14px; background: rgba(128,128,128,0.08); border-radius: 6px;"
        )
        self.viewLayout.addWidget(self._patient_info)

    # ═══════════════════════════════════════════════════════════
    #  业务逻辑（完整保留）
    # ═══════════════════════════════════════════════════════════

    def _load_patients(self):
        self._patient_combo.blockSignals(True)
        self._patient_combo.clear()
        self._patient_combo.addItem("— 请选择患者 —")

        patients = self.db.get_all_patients()
        self._patient_ids = [None]

        for p in patients:
            label = f"{p.name}（ID: {p.patient_id}）"
            if p.diagnosis:
                label += f"  [{p.diagnosis}]"
            self._patient_combo.addItem(label)
            self._patient_ids.append(p.patient_id)

        self._patient_combo.blockSignals(False)
        self.log_message.emit(f"已加载 {len(patients)} 位患者")

    def _on_patient_selected(self, index: int):
        if index < 0 or index >= len(self._patient_ids):
            return
        pid = self._patient_ids[index]
        if pid is None:
            self.current_patient = None
            self._patient_info.setText("请选择患者")
            self._btn_edit.setEnabled(False)
            self.patient_changed.emit(None)
            return

        p = self.db.get_patient(pid)
        if p:
            self.current_patient = p
            gmap = {"M": "男", "F": "女", "Other": "其他", None: "未指定"}
            info = f"姓名：{p.name}    年龄：{p.age or '—'}    性别：{gmap.get(p.gender, '—')}"
            if p.diagnosis:
                info += f"    诊断：{p.diagnosis}"
            self._patient_info.setText(info)
            self._btn_edit.setEnabled(True)
            self.patient_changed.emit(p)
            self.log_message.emit(f"已选择：{p.name}")

    def _on_new_patient(self):
        dlg = PatientDialog(self.window())
        if dlg.exec():
            np_ = dlg.get_patient()
            if np_:
                try:
                    pid = self.db.add_patient(np_)
                    self.log_message.emit(f"新建患者：{np_.name} (ID: {pid})")
                    self._load_patients()
                    for i, stored_pid in enumerate(self._patient_ids):
                        if stored_pid == pid:
                            self._patient_combo.setCurrentIndex(i)
                            break
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"新建失败：{e}")

    def _on_edit_patient(self):
        if not self.current_patient:
            return
        dlg = PatientDialog(self.window(), patient=self.current_patient)
        if dlg.exec():
            updated = dlg.get_patient()
            if updated:
                try:
                    self.db.update_patient(updated)
                    self.log_message.emit(f"已更新患者：{updated.name}")
                    self._load_patients()
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"更新失败：{e}")
