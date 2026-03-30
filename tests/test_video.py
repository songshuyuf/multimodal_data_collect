"""
视频播放测试 - 修复Windows路径
"""

import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl


class VideoTestWindow(QWidget):
    """视频播放测试窗口"""

    def __init__(self):
        super().__init__()
        self.init_ui()

        # 创建媒体播放器
        self.player = QMediaPlayer()
        self.player.setVideoOutput(self.video_widget)

        # 连接信号
        self.player.stateChanged.connect(self.on_state_changed)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.error.connect(self.on_error)

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("视频播放测试")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        # 视频显示区域
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(640, 480)
        layout.addWidget(self.video_widget)

        # 状态标签
        self.label_status = QLabel("状态: 未加载")
        layout.addWidget(self.label_status)

        # 进度标签
        self.label_progress = QLabel("进度: 0 / 0")
        layout.addWidget(self.label_progress)

        # 按钮区域
        button_layout = QHBoxLayout()

        # 选择文件按钮
        btn_select = QPushButton("选择视频文件")
        btn_select.clicked.connect(self.select_file)
        button_layout.addWidget(btn_select)

        # 播放按钮
        btn_play = QPushButton("播放")
        btn_play.clicked.connect(self.play)
        button_layout.addWidget(btn_play)

        # 暂停按钮
        btn_pause = QPushButton("暂停")
        btn_pause.clicked.connect(self.pause)
        button_layout.addWidget(btn_pause)

        # 停止按钮
        btn_stop = QPushButton("停止")
        btn_stop.clicked.connect(self.stop)
        button_layout.addWidget(btn_stop)

        # 测试按钮
        btn_test = QPushButton("测试数据集视频")
        btn_test.clicked.connect(self.test_dataset_video)
        button_layout.addWidget(btn_test)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # 当前文件
        self.current_file = None

    def select_file(self):
        """选择视频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv);;所有文件 (*.*)"
        )

        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path):
        """加载视频文件"""
        # 转换为绝对路径
        file_path = os.path.abspath(file_path)

        if not os.path.exists(file_path):
            self.label_status.setText(f"状态: 文件不存在 - {file_path}")
            print(f"✗ 文件不存在: {file_path}")
            return

        self.current_file = file_path

        # 统一使用正斜杠（QUrl.fromLocalFile会处理）
        file_path_normalized = file_path.replace('\\', '/')

        print(f"\n尝试加载视频:")
        print(f"  原始路径: {file_path}")
        print(f"  标准化路径: {file_path_normalized}")

        # 加载文件
        url = QUrl.fromLocalFile(file_path_normalized)
        print(f"  QUrl: {url.toString()}")

        self.player.setMedia(QMediaContent(url))

        self.label_status.setText(f"状态: 已加载 - {os.path.basename(file_path)}")
        print(f"✓ 已加载: {file_path}")
        print(f"  文件大小: {os.path.getsize(file_path) / 1024 / 1024:.2f} MB")

    def play(self):
        """播放"""
        if self.current_file is None:
            self.label_status.setText("状态: 请先选择文件")
            return

        self.player.play()
        self.label_status.setText("状态: 播放中")
        print("▶ 播放")

    def pause(self):
        """暂停"""
        self.player.pause()
        self.label_status.setText("状态: 已暂停")
        print("⏸ 暂停")

    def stop(self):
        """停止"""
        self.player.stop()
        self.label_status.setText("状态: 已停止")
        print("⏹ 停止")

    def test_dataset_video(self):
        """测试数据集中的视频"""
        # 尝试找到数据集中的视频文件
        test_path = './dataset/video/sims/Raw'

        if not os.path.exists(test_path):
            self.label_status.setText("状态: 未找到数据集视频目录")
            print(f"✗ 目录不存在: {test_path}")
            return

        # 遍历查找视频文件
        for folder in os.listdir(test_path):
            folder_path = os.path.join(test_path, folder)
            if os.path.isdir(folder_path):
                files = [f for f in os.listdir(folder_path)
                        if f.endswith(('.mp4', '.avi', '.mov', '.mkv'))]

                if files:
                    test_file = os.path.join(folder_path, files[0])
                    print(f"\n测试文件: {test_file}")
                    self.load_file(test_file)
                    return

        self.label_status.setText("状态: 未找到视频文件")
        print(f"✗ 在 {test_path} 下未找到视频文件")

    # ========== 信号回调 ==========

    def on_state_changed(self, state):
        """状态改变"""
        states = {
            QMediaPlayer.StoppedState: "已停止",
            QMediaPlayer.PlayingState: "播放中",
            QMediaPlayer.PausedState: "已暂停"
        }
        state_str = states.get(state, "未知")
        print(f"[状态] {state_str}")

    def on_position_changed(self, position):
        """播放进度改变"""
        duration = self.player.duration()
        if duration > 0:
            self.label_progress.setText(
                f"进度: {position/1000:.1f}s / {duration/1000:.1f}s"
            )

    def on_duration_changed(self, duration):
        """时长改变"""
        print(f"[时长] {duration/1000:.1f}秒")

    def on_error(self, error):
        """错误"""
        error_msgs = {
            QMediaPlayer.NoError: "无错误",
            QMediaPlayer.ResourceError: "资源错误（文件不存在或无法访问）",
            QMediaPlayer.FormatError: "格式错误（不支持的视频格式）",
            QMediaPlayer.NetworkError: "网络错误",
            QMediaPlayer.AccessDeniedError: "访问被拒绝",
            QMediaPlayer.ServiceMissingError: "服务缺失（可能缺少解码器）"
        }

        error_str = error_msgs.get(error, f"未知错误 ({error})")
        error_desc = self.player.errorString()

        self.label_status.setText(f"状态: ✗ {error_str}")
        print(f"\n✗ 播放错误:")
        print(f"  错误类型: {error_str}")
        print(f"  错误描述: {error_desc}")

        # 打印详细诊断信息
        print(f"\n诊断信息:")
        print(f"  当前文件: {self.current_file}")
        print(f"  文件存在: {os.path.exists(self.current_file) if self.current_file else 'N/A'}")
        print(f"  媒体状态: {self.player.mediaStatus()}")

        if error == QMediaPlayer.ServiceMissingError:
            print("\n可能的解决方法:")
            print("  1. 安装 K-Lite Codec Pack")
            print("     下载: https://codecguide.com/download_kl.htm")
            print("  2. 或安装 LAV Filters")
            print("     下载: https://github.com/Nevcairiel/LAVFilters/releases")

        if error == QMediaPlayer.FormatError:
            print("\n可能的原因:")
            print("  1. 视频格式不支持（尝试转换为 .mp4）")
            print("  2. 视频编码不支持（推荐 H.264 编码）")
            print("\n使用 FFmpeg 转换:")
            print(f"  ffmpeg -i {self.current_file} -codec:v libx264 -codec:a aac output.mp4")

        if error == QMediaPlayer.ResourceError:
            print("\n可能的原因:")
            print("  1. 文件路径包含特殊字符")
            print("  2. 文件被占用")
            print("  3. 文件损坏")
            print("  4. 编码器缺失")
            print("\n建议:")
            print("  - 尝试用Windows Media Player打开此文件")
            print("  - 如果WMP也打不开，说明文件本身有问题")
            print("  - 如果WMP能打开，说明是Qt编码器问题")


def main():
    """主函数"""
    print("=" * 60)
    print("视频播放测试 - Windows路径修复版")
    print("=" * 60)
    print("\n使用说明:")
    print("1. 点击'选择视频文件'选择任意视频")
    print("2. 或点击'测试数据集视频'自动测试")
    print("3. 点击'播放'开始播放")
    print("4. 观察视频是否正常显示")
    print("\n注意:")
    print("- 如果黑屏但有声音 → 解码器问题")
    print("- 如果'资源错误' → 可能是编码器问题")
    print("- 推荐使用 .mp4 格式（H.264编码）")
    print("\n=" * 60 + "\n")

    app = QApplication(sys.argv)
    window = VideoTestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()