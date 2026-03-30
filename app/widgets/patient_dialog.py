"""患者新建/编辑弹窗 — Fluent Design 适配深色/浅色主题"""

from typing import Optional

from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt

from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, BodyLabel,
    LineEdit, ComboBox, InfoBar, InfoBarPosition,
)

from data.models import Patient


class PatientDialog(MessageBoxBase):

    def __init__(self, parent=None, patient: Optional[Patient] = None):
        super().__init__(parent)
        self.patient = patient
        self._result: Optional[Patient] = None
        is_edit = patient is not None

        self._setup_ui(is_edit)

    def _setup_ui(self, is_edit: bool):
        title = SubtitleLabel("编辑患者信息" if is_edit else "新建患者")
        self.viewLayout.addWidget(title)

        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("请输入姓名")
        self.name_edit.setClearButtonEnabled(True)
        if is_edit:
            self.name_edit.setText(self.patient.name)

        self.age_edit = LineEdit()
        self.age_edit.setPlaceholderText("年龄（数字）")
        self.age_edit.setClearButtonEnabled(True)
        if is_edit and self.patient.age:
            self.age_edit.setText(str(self.patient.age))

        self.gender_combo = ComboBox()
        self.gender_combo.addItems(["未指定", "男", "女", "其他"])
        if is_edit and self.patient.gender:
            gmap = {"M": "男", "F": "女", "Other": "其他"}
            idx = self.gender_combo.findText(gmap.get(self.patient.gender, "未指定"))
            if idx >= 0:
                self.gender_combo.setCurrentIndex(idx)

        self.diag_edit = LineEdit()
        self.diag_edit.setPlaceholderText("诊断（可选）")
        self.diag_edit.setClearButtonEnabled(True)
        if is_edit and self.patient.diagnosis:
            self.diag_edit.setText(self.patient.diagnosis)

        self.notes_edit = LineEdit()
        self.notes_edit.setPlaceholderText("备注（可选）")
        self.notes_edit.setClearButtonEnabled(True)
        if is_edit and self.patient.notes:
            self.notes_edit.setText(self.patient.notes)

        fields = [
            ("姓名 *", self.name_edit),
            ("年龄",   self.age_edit),
            ("性别",   self.gender_combo),
            ("诊断",   self.diag_edit),
            ("备注",   self.notes_edit),
        ]
        for label_text, widget in fields:
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl = BodyLabel(label_text)
            lbl.setFixedWidth(60)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(lbl)
            row.addWidget(widget)
            self.viewLayout.addLayout(row)

        self.yesButton.setText("确认")
        self.cancelButton.setText("取消")

        self.widget.setMinimumWidth(400)

    def accept(self):
        """点确认时验证并保存数据。"""
        name = self.name_edit.text().strip()
        if not name:
            InfoBar.warning(
                title="提示", content="姓名不能为空",
                parent=self, duration=3000,
                position=InfoBarPosition.TOP,
            )
            return

        age = None
        age_text = self.age_edit.text().strip()
        if age_text:
            try:
                age = int(age_text)
            except ValueError:
                InfoBar.warning(
                    title="提示", content="年龄必须是数字",
                    parent=self, duration=3000,
                    position=InfoBarPosition.TOP,
                )
                return

        gmap = {"未指定": None, "男": "M", "女": "F", "其他": "Other"}
        self._result = Patient(
            patient_id=self.patient.patient_id if self.patient else None,
            name=name,
            age=age,
            gender=gmap.get(self.gender_combo.currentText()),
            diagnosis=self.diag_edit.text().strip() or None,
            notes=self.notes_edit.text().strip() or None,
        )
        super().accept()

    def get_patient(self) -> Optional[Patient]:
        return self._result
