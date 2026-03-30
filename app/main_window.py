"""
主窗口 — AI 艺术诊疗多模态采集系统
Fluent Design 重构版：MSFluentWindow + 3 子页面 + 18 主题组合
"""

import sys
import os
import logging

from PyQt5.QtWidgets import QApplication, QMessageBox, QAction
from PyQt5.QtGui import QIcon, QColor, QPixmap
from PyQt5.QtCore import QSettings, Qt

from qfluentwidgets import (
    MSFluentWindow, NavigationItemPosition,
    FluentIcon as FIF, setTheme, setThemeColor, Theme, isDarkTheme,
    RoundMenu,
)

from data.database import DatabaseManager
from data.files import FileManager
from data.session import SessionManager

from .experiment_tab import ConsolePage
from .monitor_tab import MonitorPage
from .upload_manager import UploadManager
from .upload_tab import UploadPage
from .updater import start_update_check

try:
    from version import APP_VERSION
except ImportError:
    APP_VERSION = "0.7.0"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ACCENT_COLORS = {
    'Amber':      '#FFB300',
    'Blue':       '#2979FF',
    'Cyan':       '#00BCD4',
    'LightGreen': '#8BC34A',
    'Pink':       '#E91E63',
    'Purple':     '#9C27B0',
    'Red':        '#F44336',
    'Teal':       '#009688',
    'Yellow':     '#FFEB3B',
}

_SETTINGS = QSettings('TGAI', 'AiArtTreat')


class FluentMainWindow(MSFluentWindow):

    def __init__(self):
        super().__init__()
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        self.db_manager = DatabaseManager("./data/database/patients.db")
        self.file_manager = FileManager("./data/sessions")
        self.session_manager = SessionManager(self.db_manager, self.file_manager)

        self._restore_theme()
        self._init_ui()

    def _restore_theme(self):
        """Restore theme from QSettings (or apply defaults)."""
        base = _SETTINGS.value('theme/base', 'dark')
        accent = _SETTINGS.value('theme/accent', '#2979FF')
        setTheme(Theme.DARK if base == 'dark' else Theme.LIGHT)
        setThemeColor(QColor(accent))

    def _save_theme(self, base: str = None, accent: str = None):
        if base is not None:
            _SETTINGS.setValue('theme/base', base)
        if accent is not None:
            _SETTINGS.setValue('theme/accent', accent)

    def _apply_base_theme(self, dark: bool):
        setTheme(Theme.DARK if dark else Theme.LIGHT, lazy=True)
        self._save_theme(base='dark' if dark else 'light')

    def _apply_accent(self, hex_color: str):
        setThemeColor(QColor(hex_color))
        self._save_theme(accent=hex_color)

    def _show_theme_menu(self):
        menu = RoundMenu(parent=self)

        dark_act = QAction("深色模式", menu)
        dark_act.setCheckable(True)
        dark_act.setChecked(isDarkTheme())
        dark_act.triggered.connect(lambda: self._apply_base_theme(True))
        menu.addAction(dark_act)

        light_act = QAction("浅色模式", menu)
        light_act.setCheckable(True)
        light_act.setChecked(not isDarkTheme())
        light_act.triggered.connect(lambda: self._apply_base_theme(False))
        menu.addAction(light_act)

        menu.addSeparator()

        current_accent = _SETTINGS.value('theme/accent', '#2979FF')
        for name, hex_c in ACCENT_COLORS.items():
            pix = QPixmap(16, 16)
            pix.fill(QColor(hex_c))
            act = QAction(QIcon(pix), name, menu)
            act.setCheckable(True)
            act.setChecked(hex_c.upper() == current_accent.upper())
            act.triggered.connect(lambda checked, c=hex_c: self._apply_accent(c))
            menu.addAction(act)

        btn = self.navigationInterface.widget("theme")
        if btn is not None:
            pos = btn.mapToGlobal(btn.rect().topRight())
            menu.exec_(pos)
        else:
            from PyQt5.QtGui import QCursor
            menu.exec_(QCursor.pos())

    def _init_ui(self):
        self.setWindowTitle(f"AI 艺术诊疗多模态采集系统 v{APP_VERSION}")
        self.resize(1440, 900)

        logo_path = os.path.join(PROJECT_ROOT, "assets", "logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        self._console = ConsolePage(self.db_manager, self.session_manager, self)
        self._monitor = MonitorPage(self._console, self)

        self._upload_mgr = UploadManager(self)
        self._upload_page = UploadPage(self._upload_mgr, self)

        self._about = _build_about_page(self)

        self.addSubInterface(self._console, FIF.COMMAND_PROMPT, "主控台")
        self.addSubInterface(self._monitor, FIF.IOT, "实时监控")
        self.addSubInterface(self._upload_page, FIF.CLOUD_DOWNLOAD, "数据上传")
        self.addSubInterface(
            self._about, FIF.INFO, "关于",
            position=NavigationItemPosition.BOTTOM,
        )

        self._console.experiment_session_done.connect(
            self._upload_page.enqueue_session
        )

        self.navigationInterface.addItem(
            routeKey="theme",
            icon=FIF.CONSTRACT,
            text="主题",
            onClick=lambda: self._show_theme_menu(),
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        self.navigationInterface.setCurrentItem("consolePage")

    def closeEvent(self, event):
        if hasattr(self, '_console') and self._console.is_collecting:
            reply = QMessageBox.warning(
                self, "警告",
                "数据采集正在进行中！\n确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply == QMessageBox.No:
                event.ignore()
                return

        reply = QMessageBox.question(
            self, "确认退出", "确定要退出程序吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._upload_mgr.stop()
            self.db_manager.close()
            event.accept()
        else:
            event.ignore()


def _build_about_page(parent):
    """构建关于页面，带 logo 和项目信息"""
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QPixmap
    from qfluentwidgets import (
        TitleLabel, SubtitleLabel, BodyLabel, CaptionLabel,
        SimpleCardWidget, InfoBadge, InfoLevel, SmoothScrollArea,
    )

    scroll = SmoothScrollArea(parent)
    scroll.setObjectName("aboutPage")
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")

    container = QWidget()
    container.setStyleSheet("QWidget{background:transparent;}")
    scroll.setWidget(container)

    lay = QVBoxLayout(container)
    lay.setContentsMargins(60, 40, 60, 40)
    lay.setSpacing(16)
    lay.setAlignment(Qt.AlignCenter)

    logo_path = os.path.join(PROJECT_ROOT, "assets", "logo.png")
    if os.path.exists(logo_path):
        logo_lbl = QLabel()
        pix = QPixmap(logo_path)
        scaled = pix.scaledToHeight(80, Qt.SmoothTransformation)
        logo_lbl.setPixmap(scaled)
        logo_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo_lbl)
        lay.addSpacing(12)

    title = TitleLabel("AI 艺术诊疗多模态采集系统")
    title.setAlignment(Qt.AlignCenter)
    lay.addWidget(title)

    ver = SubtitleLabel(f"v{APP_VERSION}  ·  Fluent Design 版")
    ver.setAlignment(Qt.AlignCenter)
    lay.addWidget(ver)

    lay.addSpacing(24)

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

    lay.addWidget(desc_card)
    lay.addSpacing(16)

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

    lay.addWidget(tech_card)
    lay.addSpacing(12)

    footer = CaptionLabel("Westlake University · TGAI Lab")
    footer.setAlignment(Qt.AlignCenter)
    lay.addWidget(footer)

    return scroll


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI艺术诊疗多模态采集系统")
    app.setOrganizationName("Westlake University TGAI Lab")

    logo_path = os.path.join(PROJECT_ROOT, "assets", "logo.png")
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))

    window = FluentMainWindow()
    window.show()

    start_update_check(window)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
