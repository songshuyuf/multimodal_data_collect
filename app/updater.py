"""
自动更新模块 — 启动时后台检查 + 下载 + 提示安装重启
===================================================
流程：
  1. UpdateChecker (QThread) 向服务端查询最新版本
  2. 若有新版本，发射 update_available 信号
  3. 主窗口弹出 UpdateDialog，用户可选择"立即更新"或"稍后"
  4. 点击"立即更新"：后台下载安装包 → 完成后启动安装程序 → 退出当前应用
"""

import os
import sys
import json
import logging
import tempfile
import subprocess
from packaging.version import Version

from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt5.QtCore import QUrl

from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, BodyLabel, ProgressBar,
    PrimaryPushButton, PushButton, InfoBar, InfoBarPosition,
)

logger = logging.getLogger(__name__)


def _current_version() -> str:
    try:
        from version import APP_VERSION
        return APP_VERSION
    except ImportError:
        return "0.0.0"


def _update_url() -> str:
    try:
        from version import UPDATE_CHECK_URL
        return UPDATE_CHECK_URL
    except ImportError:
        return ""


class UpdateChecker(QThread):
    """后台线程：向服务端 GET /api/v1/update/check 查询最新版本。"""

    update_available = pyqtSignal(dict)
    check_finished = pyqtSignal()

    def run(self):
        import urllib.request
        import urllib.error

        url = _update_url()
        if not url:
            self.check_finished.emit()
            return

        params = f"?version={_current_version()}&platform=windows"
        try:
            req = urllib.request.Request(url + params, method="GET")
            req.add_header("User-Agent", f"AiArtTreat/{_current_version()}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            if not data.get("update_available", False):
                logger.info("当前已是最新版本 %s", _current_version())
                self.check_finished.emit()
                return

            latest = data.get("latest_version", "")
            if latest and Version(latest) > Version(_current_version()):
                logger.info("发现新版本 %s (当前 %s)", latest, _current_version())
                self.update_available.emit(data)
            else:
                logger.info("版本比较：无需更新")

        except urllib.error.URLError as e:
            logger.debug("更新检查失败（网络）: %s", e)
        except Exception as e:
            logger.debug("更新检查异常: %s", e)
        finally:
            self.check_finished.emit()


class DownloadThread(QThread):
    """后台线程：下载安装包，报告进度。"""

    progress = pyqtSignal(int, int)      # (已下载字节, 总字节)
    finished = pyqtSignal(str)           # 下载完成，传入本地文件路径
    error = pyqtSignal(str)              # 下载出错

    def __init__(self, download_url: str, file_size: int = 0, parent=None):
        super().__init__(parent)
        self._url = download_url
        self._file_size = file_size
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(self._url, method="GET")
            req.add_header("User-Agent", f"AiArtTreat/{_current_version()}")

            suffix = ".exe" if self._url.endswith(".exe") else ".tmp"
            fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="AiArtTreat_update_")
            os.close(fd)

            with urllib.request.urlopen(req, timeout=300) as resp:
                total = int(resp.headers.get("Content-Length", self._file_size) or 0)
                downloaded = 0
                chunk_size = 256 * 1024  # 256 KB

                with open(tmp_path, "wb") as f:
                    while True:
                        if self._cancelled:
                            os.unlink(tmp_path)
                            return

                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total)

            self.finished.emit(tmp_path)

        except Exception as e:
            logger.error("下载更新失败: %s", e)
            self.error.emit(str(e))


class UpdateDialog(MessageBoxBase):
    """Fluent 风格更新弹窗：显示版本信息 + 更新日志 + 下载进度。"""

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self._info = update_info
        self._download_thread = None
        self._installer_path = None

        self._setup_ui()

    def _setup_ui(self):
        latest = self._info.get("latest_version", "?")
        current = _current_version()

        self.titleLabel = SubtitleLabel(f"发现新版本 v{latest}")
        self.viewLayout.addWidget(self.titleLabel)

        self.versionLabel = BodyLabel(f"当前版本: v{current}  →  最新版本: v{latest}")
        self.viewLayout.addWidget(self.versionLabel)

        notes = self._info.get("release_notes", "")
        if notes:
            self.notesLabel = BodyLabel(notes)
            self.notesLabel.setWordWrap(True)
            self.viewLayout.addWidget(self.notesLabel)

        file_size = self._info.get("file_size", 0)
        if file_size > 0:
            size_mb = file_size / (1024 * 1024)
            self.sizeLabel = BodyLabel(f"安装包大小: {size_mb:.1f} MB")
            self.viewLayout.addWidget(self.sizeLabel)

        self.progressBar = ProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.hide()
        self.viewLayout.addWidget(self.progressBar)

        self.progressLabel = BodyLabel("")
        self.progressLabel.hide()
        self.viewLayout.addWidget(self.progressLabel)

        self.yesButton.setText("立即更新")
        self.cancelButton.setText("稍后提醒")

        self.widget.setMinimumWidth(420)

    def _on_yes_clicked(self):
        """覆写确认按钮行为：开始下载而非直接关闭。"""
        download_url = self._info.get("download_url", "")
        if not download_url:
            return

        self.yesButton.setEnabled(False)
        self.yesButton.setText("下载中…")
        self.cancelButton.setText("取消下载")
        self.progressBar.show()
        self.progressLabel.show()

        file_size = self._info.get("file_size", 0)
        self._download_thread = DownloadThread(download_url, file_size, self)
        self._download_thread.progress.connect(self._on_progress)
        self._download_thread.finished.connect(self._on_download_done)
        self._download_thread.error.connect(self._on_download_error)
        self._download_thread.start()

    def _on_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = int(downloaded * 100 / total)
            self.progressBar.setValue(pct)
            dl_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.progressLabel.setText(f"{dl_mb:.1f} / {total_mb:.1f} MB  ({pct}%)")
        else:
            dl_mb = downloaded / (1024 * 1024)
            self.progressLabel.setText(f"已下载 {dl_mb:.1f} MB")

    def _on_download_done(self, installer_path: str):
        self._installer_path = installer_path
        self.progressBar.setValue(100)
        self.progressLabel.setText("下载完成，正在启动安装程序…")

        QTimer.singleShot(500, self._launch_installer)

    def _on_download_error(self, error_msg: str):
        self.yesButton.setEnabled(True)
        self.yesButton.setText("重试")
        self.cancelButton.setText("稍后提醒")
        self.progressLabel.setText(f"下载失败: {error_msg}")

    def _launch_installer(self):
        if not self._installer_path or not os.path.isfile(self._installer_path):
            return

        try:
            subprocess.Popen(
                [self._installer_path, "/SILENT", "/RESTARTAPPLICATIONS"],
                shell=False,
                creationflags=subprocess.DETACHED_PROCESS,
            )
            QApplication.instance().quit()
        except Exception as e:
            logger.error("启动安装程序失败: %s", e)
            self.progressLabel.setText(f"启动安装程序失败: {e}")

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def accept(self):
        """覆写 accept：首次点确认是开始下载，不是关闭。"""
        if self._download_thread is None:
            self._on_yes_clicked()
        else:
            super().accept()

    def reject(self):
        """取消：如果正在下载则中止。"""
        if self._download_thread and self._download_thread.isRunning():
            self._download_thread.cancel()
            self._download_thread.wait(3000)
        super().reject()


def start_update_check(parent_window):
    """
    在主窗口启动后调用此函数，后台检查更新。
    parent_window: FluentMainWindow 实例，用作弹窗的父窗口。
    """
    checker = UpdateChecker(parent_window)
    checker.update_available.connect(
        lambda info: _show_update_dialog(info, parent_window)
    )
    checker.start()
    parent_window._update_checker = checker


def _show_update_dialog(update_info: dict, parent):
    """收到新版本信号后弹出更新对话框。"""
    dialog = UpdateDialog(update_info, parent)
    dialog.exec()
