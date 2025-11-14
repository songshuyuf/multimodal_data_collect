"""
主窗口
应用程序的主界面框架
"""

import sys
import logging
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QAction,
    QMessageBox, QStatusBar, QMenuBar
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from database.database_manager import DatabaseManager
from managers.file_manager import FileManager
from managers.session_manager import SessionManager
from .patient_tab import PatientTab
from .collection_tab import CollectionTab
from .realtime_shimmer_tab import RealtimeShimmerTab
from .realtime_video_audio_tab import RealtimeVideoAudioTab
from .realtime_eeg_tab import RealtimeEEGTab


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()

        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # 初始化管理器
        self.db_manager = DatabaseManager("./data/database/patients.db")
        self.file_manager = FileManager("./data/sessions")
        self.session_manager = SessionManager(self.db_manager, self.file_manager)

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("多模态数据采集系统 - Phase 1 完整版")
        self.setGeometry(100, 100, 1400, 900)

        # 创建菜单栏
        self.create_menu_bar()

        # 创建Tab控件
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 1. 患者管理Tab
        self.patient_tab = PatientTab(self.db_manager)
        self.tabs.addTab(self.patient_tab, "👤 患者管理")

        # 2. 数据采集Tab
        self.collection_tab = CollectionTab(self.db_manager, self.session_manager)
        self.tabs.addTab(self.collection_tab, "📹 数据采集")

        # 3. 外周生理信号Tab (实时显示Shimmer数据)
        self.shimmer_realtime_tab = RealtimeShimmerTab(self.collection_tab)
        self.tabs.addTab(self.shimmer_realtime_tab, "📊 外周生理信号")

        # 4. 视音频Tab (实时显示视频和音频)
        self.video_audio_tab = RealtimeVideoAudioTab(self.collection_tab)
        self.tabs.addTab(self.video_audio_tab, "🎥 视音频")

        # 5. EEG信号Tab (预留)
        self.eeg_tab = RealtimeEEGTab()
        self.tabs.addTab(self.eeg_tab, "🧠 EEG信号")

        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 - 完整版多模态采集系统")

        # 设置样式
        self.setup_style()

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        # 退出
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")

        # 设置
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.show_settings)
        edit_menu.addAction(settings_action)

        # 查看菜单
        view_menu = menubar.addMenu("查看")

        # 切换到患者管理
        view_patients_action = QAction("患者管理", self)
        view_patients_action.setShortcut("Ctrl+1")
        view_patients_action.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        view_menu.addAction(view_patients_action)

        # 切换到数据采集
        view_collection_action = QAction("数据采集", self)
        view_collection_action.setShortcut("Ctrl+2")
        view_collection_action.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        view_menu.addAction(view_collection_action)

        # 切换到外周生理信号
        view_shimmer_action = QAction("外周生理信号", self)
        view_shimmer_action.setShortcut("Ctrl+3")
        view_shimmer_action.triggered.connect(lambda: self.tabs.setCurrentIndex(2))
        view_menu.addAction(view_shimmer_action)

        # 切换到视音频
        view_video_action = QAction("视音频", self)
        view_video_action.setShortcut("Ctrl+4")
        view_video_action.triggered.connect(lambda: self.tabs.setCurrentIndex(3))
        view_menu.addAction(view_video_action)

        # 切换到EEG
        view_eeg_action = QAction("EEG信号", self)
        view_eeg_action.setShortcut("Ctrl+5")
        view_eeg_action.triggered.connect(lambda: self.tabs.setCurrentIndex(4))
        view_menu.addAction(view_eeg_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        # 关于
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # 使用指南
        guide_action = QAction("使用指南", self)
        guide_action.triggered.connect(self.show_guide)
        help_menu.addAction(guide_action)

    def setup_style(self):
        """设置样式"""
        # 设置全局字体
        font = QFont("Microsoft YaHei", 10)
        self.setFont(font)
        QApplication.setFont(font)

        # 设置应用样式
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
            QTabBar::tab {
                padding: 8px 15px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #e3f2fd;
                border-bottom: 3px solid #2196F3;
            }
        """)

    def show_settings(self):
        """显示设置对话框"""
        QMessageBox.information(
            self,
            "设置",
            "设置功能将在后续版本中实现\n\n" +
            "计划功能：\n" +
            "- 设备参数配置\n" +
            "- 数据保存路径\n" +
            "- 采集参数设置"
        )

    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h2>多模态数据采集系统</h2>
        <p><b>版本:</b> Phase 1 完整版</p>
        <p><b>功能:</b> 患者管理、多模态数据采集、实时监控</p>
        <hr>
        <p><b>开发者:</b> Songshuyu @ Westlake University TGAI Lab</p>
        <p><b>技术栈:</b> PyQt5, SQLite3, OpenCV, pylsl, pyqtgraph</p>
        <hr>
        <p><b>已完成功能:</b></p>
        <ul>
            <li>✅ 数据库管理 (Day 1)</li>
            <li>✅ 文件管理 (Day 1)</li>
            <li>✅ 会话管理 (Day 1)</li>
            <li>✅ 患者管理GUI (Day 1)</li>
            <li>✅ 数据采集Tab (Day 2)</li>
            <li>✅ 设备控制 (Day 3)</li>
            <li>✅ 实时Shimmer信号显示 (Day 3)</li>
            <li>✅ 实时视音频显示 (Day 3)</li>
            <li>✅ EEG接口预留 (Day 3)</li>
        </ul>
        <p><b>下一步:</b> Phase 2 - 数据分析与可视化</p>
        """

        QMessageBox.about(self, "关于", about_text)

    def show_guide(self):
        """显示使用指南"""
        guide_text = """
        <h2>📖 使用指南</h2>
        
        <h3>1️⃣ 患者管理</h3>
        <ul>
            <li>添加患者：点击 "➕ 添加患者" 按钮</li>
            <li>编辑患者：双击患者行或点击 "✏️ 编辑"</li>
            <li>删除患者：选中后点击 "🗑️ 删除"</li>
            <li>搜索患者：输入关键词搜索</li>
        </ul>
        
        <h3>2️⃣ 数据采集流程</h3>
        <ol>
            <li><b>选择患者</b>：从下拉框选择要采集数据的患者</li>
            <li><b>创建会话</b>：输入会话名称（如"基线测试"）</li>
            <li><b>连接设备</b>：连接需要的设备（Shimmer/视频/音频）</li>
            <li><b>开始采集</b>：点击 "▶️ 开始采集" 或按空格键</li>
            <li><b>实时监控</b>：切换到实时显示Tab查看数据</li>
            <li><b>停止采集</b>：点击 "⏹️ 停止采集" 或再按空格键</li>
        </ol>
        
        <h3>3️⃣ 实时监控Tab</h3>
        <ul>
            <li><b>外周生理信号</b>：实时显示GSR、PPG、心率、加速度计</li>
            <li><b>视音频</b>：实时显示视频预览和音频波形</li>
            <li><b>EEG信号</b>：预留接口，Phase 3实现</li>
        </ul>
        
        <h3>⌨️ 快捷键</h3>
        <ul>
            <li><b>空格键</b>：开始/停止采集</li>
            <li><b>Ctrl+1</b>：切换到患者管理</li>
            <li><b>Ctrl+2</b>：切换到数据采集</li>
            <li><b>Ctrl+3</b>：切换到外周生理信号</li>
            <li><b>Ctrl+4</b>：切换到视音频</li>
            <li><b>Ctrl+5</b>：切换到EEG信号</li>
            <li><b>Ctrl+Q</b>：退出程序</li>
        </ul>
        
        <h3>💡 提示</h3>
        <ul>
            <li>采集前必须先选择患者并创建会话</li>
            <li>至少连接一个设备才能开始采集</li>
            <li>采集过程中无法断开设备连接</li>
            <li>数据自动保存到 data/sessions/ 目录</li>
            <li>实时监控Tab需要在采集开始后才有数据显示</li>
        </ul>
        
        <hr>
        <p><b>注意：</b>需要安装 pyqtgraph 才能看到实时波形<br>
        安装命令: pip install pyqtgraph</p>
        """

        msg = QMessageBox(self)
        msg.setWindowTitle("使用指南")
        msg.setTextFormat(Qt.RichText)
        msg.setText(guide_text)
        msg.exec_()

    def closeEvent(self, event):
        """关闭事件"""
        # 检查是否正在采集
        if hasattr(self, 'collection_tab') and self.collection_tab.is_collecting:
            reply = QMessageBox.warning(
                self,
                "警告",
                "数据采集正在进行中！\n\n确定要退出吗？这将停止当前采集。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.No:
                event.ignore()
                return

        # 正常退出确认
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出程序吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 关闭数据库连接
            self.db_manager.close()
            event.accept()
        else:
            event.ignore()


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用程序信息
    app.setApplicationName("多模态数据采集系统")
    app.setOrganizationName("Westlake University")
    app.setOrganizationDomain("westlake.edu.cn")

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    # 运行事件循环
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()