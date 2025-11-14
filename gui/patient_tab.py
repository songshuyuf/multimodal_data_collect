"""
患者管理Tab
提供患者信息的增删改查界面
"""

import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLineEdit, QDialog, QFormLayout, QLabel,
    QTextEdit, QComboBox, QSpinBox, QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from database.database_manager import DatabaseManager
from database.models import Patient


class PatientTab(QWidget):
    """患者管理Tab"""

    def __init__(self, db_manager: DatabaseManager):
        """
        初始化患者管理Tab

        Args:
            db_manager: 数据库管理器实例
        """
        super().__init__()
        self.db = db_manager
        self.init_ui()
        self.refresh_table()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()

        # 工具栏
        toolbar = self.create_toolbar()
        layout.addLayout(toolbar)

        # 搜索栏
        search_bar = self.create_search_bar()
        layout.addLayout(search_bar)

        # 患者表格
        self.table = self.create_table()
        layout.addWidget(self.table)

        self.setLayout(layout)

    def create_toolbar(self) -> QHBoxLayout:
        """创建工具栏"""
        toolbar = QHBoxLayout()

        # 添加患者按钮
        self.btn_add = QPushButton("➕ 添加患者")
        self.btn_add.clicked.connect(self.add_patient)
        toolbar.addWidget(self.btn_add)

        # 编辑按钮
        self.btn_edit = QPushButton("✏️ 编辑")
        self.btn_edit.clicked.connect(self.edit_patient)
        self.btn_edit.setEnabled(False)
        toolbar.addWidget(self.btn_edit)

        # 删除按钮
        self.btn_delete = QPushButton("🗑️ 删除")
        self.btn_delete.clicked.connect(self.delete_patient)
        self.btn_delete.setEnabled(False)
        toolbar.addWidget(self.btn_delete)

        toolbar.addStretch()

        # 刷新按钮
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.clicked.connect(self.refresh_table)
        toolbar.addWidget(self.btn_refresh)

        return toolbar

    def create_search_bar(self) -> QHBoxLayout:
        """创建搜索栏"""
        search_bar = QHBoxLayout()

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索患者姓名或诊断...")
        self.search_input.returnPressed.connect(self.search_patients)
        search_bar.addWidget(self.search_input)

        # 搜索按钮
        self.btn_search = QPushButton("🔍 搜索")
        self.btn_search.clicked.connect(self.search_patients)
        search_bar.addWidget(self.btn_search)

        return search_bar

    def create_table(self) -> QTableWidget:
        """创建患者表格"""
        table = QTableWidget()

        # 设置列
        headers = ["ID", "姓名", "年龄", "性别", "诊断", "创建时间"]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        # 设置表格属性
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)

        # 设置列宽
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 姓名
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 年龄
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 性别
        header.setSectionResizeMode(4, QHeaderView.Stretch)  # 诊断
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 创建时间

        # 连接选择信号
        table.itemSelectionChanged.connect(self.on_selection_changed)

        # 双击编辑
        table.doubleClicked.connect(self.edit_patient)

        return table

    def refresh_table(self):
        """刷新表格数据"""
        # 获取所有患者
        patients = self.db.get_all_patients()

        # 清空表格
        self.table.setRowCount(0)

        # 填充数据
        for patient in patients:
            self.add_table_row(patient)

    def add_table_row(self, patient: Patient):
        """添加一行患者数据"""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # ID
        self.table.setItem(row, 0, QTableWidgetItem(str(patient.patient_id)))

        # 姓名
        self.table.setItem(row, 1, QTableWidgetItem(patient.name))

        # 年龄
        age_text = str(patient.age) if patient.age else ""
        self.table.setItem(row, 2, QTableWidgetItem(age_text))

        # 性别
        gender_map = {'M': '男', 'F': '女', 'Other': '其他'}
        gender_text = gender_map.get(patient.gender, patient.gender)
        self.table.setItem(row, 3, QTableWidgetItem(gender_text))

        # 诊断
        self.table.setItem(row, 4, QTableWidgetItem(patient.diagnosis))

        # 创建时间
        created_text = patient.created_at.strftime("%Y-%m-%d %H:%M") if patient.created_at else ""
        self.table.setItem(row, 5, QTableWidgetItem(created_text))

    def on_selection_changed(self):
        """表格选择改变时"""
        has_selection = len(self.table.selectedItems()) > 0
        self.btn_edit.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)

    def get_selected_patient_id(self) -> int:
        """获取选中的患者ID"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        row = selected_rows[0].row()
        patient_id = int(self.table.item(row, 0).text())
        return patient_id

    def add_patient(self):
        """添加患者"""
        dialog = PatientDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            patient = dialog.get_patient()
            try:
                patient_id = self.db.add_patient(patient)
                QMessageBox.information(self, "成功", f"患者添加成功！ID: {patient_id}")
                self.refresh_table()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"添加患者失败: {str(e)}")

    def edit_patient(self):
        """编辑患者"""
        patient_id = self.get_selected_patient_id()
        if not patient_id:
            return

        # 获取患者信息
        patient = self.db.get_patient(patient_id)
        if not patient:
            QMessageBox.warning(self, "警告", "患者不存在")
            return

        # 显示编辑对话框
        dialog = PatientDialog(self, patient)
        if dialog.exec_() == QDialog.Accepted:
            updated_patient = dialog.get_patient()
            updated_patient.patient_id = patient_id

            if self.db.update_patient(updated_patient):
                QMessageBox.information(self, "成功", "患者信息更新成功！")
                self.refresh_table()
            else:
                QMessageBox.critical(self, "错误", "更新患者失败")

    def delete_patient(self):
        """删除患者"""
        patient_id = self.get_selected_patient_id()
        if not patient_id:
            return

        # 获取患者信息
        patient = self.db.get_patient(patient_id)
        if not patient:
            QMessageBox.warning(self, "警告", "患者不存在")
            return

        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除患者 '{patient.name}' 吗？\n\n" +
            "⚠️ 警告：这将同时删除该患者的所有会话数据！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.db.delete_patient(patient_id):
                QMessageBox.information(self, "成功", "患者删除成功！")
                self.refresh_table()
            else:
                QMessageBox.critical(self, "错误", "删除患者失败")

    def search_patients(self):
        """搜索患者"""
        keyword = self.search_input.text().strip()

        if not keyword:
            # 如果搜索框为空，显示所有患者
            self.refresh_table()
            return

        # 搜索患者
        patients = self.db.search_patients(keyword)

        # 清空表格
        self.table.setRowCount(0)

        # 填充搜索结果
        for patient in patients:
            self.add_table_row(patient)


class PatientDialog(QDialog):
    """患者信息编辑对话框"""

    def __init__(self, parent=None, patient: Patient = None):
        """
        初始化对话框

        Args:
            parent: 父窗口
            patient: 要编辑的患者对象（None表示新建）
        """
        super().__init__(parent)
        self.patient = patient
        self.is_edit_mode = patient is not None

        self.setWindowTitle("编辑患者" if self.is_edit_mode else "添加患者")
        self.setMinimumWidth(400)

        self.init_ui()

        if self.is_edit_mode:
            self.fill_form()

    def init_ui(self):
        """初始化UI"""
        layout = QFormLayout()

        # 姓名
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("必填")
        layout.addRow("姓名:", self.name_input)

        # 年龄
        self.age_input = QSpinBox()
        self.age_input.setRange(0, 150)
        self.age_input.setValue(0)
        self.age_input.setSpecialValueText("未填写")
        layout.addRow("年龄:", self.age_input)

        # 性别
        self.gender_input = QComboBox()
        self.gender_input.addItems(["未选择", "男", "女", "其他"])
        layout.addRow("性别:", self.gender_input)

        # 诊断
        self.diagnosis_input = QLineEdit()
        self.diagnosis_input.setPlaceholderText("诊断信息")
        layout.addRow("诊断:", self.diagnosis_input)

        # 备注
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("备注信息")
        self.notes_input.setMaximumHeight(100)
        layout.addRow("备注:", self.notes_input)

        # 按钮
        button_layout = QHBoxLayout()

        self.btn_save = QPushButton("保存")
        self.btn_save.clicked.connect(self.accept)
        button_layout.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        layout.addRow(button_layout)

        self.setLayout(layout)

    def fill_form(self):
        """填充表单（编辑模式）"""
        if not self.patient:
            return

        self.name_input.setText(self.patient.name)

        if self.patient.age:
            self.age_input.setValue(self.patient.age)

        gender_map = {'M': '男', 'F': '女', 'Other': '其他'}
        gender_text = gender_map.get(self.patient.gender, "未选择")
        index = self.gender_input.findText(gender_text)
        if index >= 0:
            self.gender_input.setCurrentIndex(index)

        self.diagnosis_input.setText(self.patient.diagnosis)
        self.notes_input.setPlainText(self.patient.notes)

    def get_patient(self) -> Patient:
        """获取表单数据"""
        # 性别映射
        gender_map = {'男': 'M', '女': 'F', '其他': 'Other', '未选择': ''}
        gender = gender_map.get(self.gender_input.currentText(), '')

        # 年龄（0表示未填写）
        age = self.age_input.value() if self.age_input.value() > 0 else None

        return Patient(
            name=self.name_input.text().strip(),
            age=age,
            gender=gender,
            diagnosis=self.diagnosis_input.text().strip(),
            notes=self.notes_input.toPlainText().strip()
        )

    def accept(self):
        """验证并接受"""
        # 验证姓名
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "验证失败", "请输入患者姓名")
            self.name_input.setFocus()
            return

        super().accept()