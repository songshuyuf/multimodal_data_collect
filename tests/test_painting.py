"""
绘画数据集测试
测试 dataset_manager 是否能正确扫描和显示绘画
"""

import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QListWidget, QTextEdit)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt


class PaintingTestWindow(QWidget):
    """绘画数据集测试窗口"""

    def __init__(self):
        super().__init__()
        self.dataset_manager = None
        self.current_paintings = []
        self.current_index = 0

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("绘画数据集测试")
        self.setGeometry(100, 100, 1000, 700)

        # 主布局
        main_layout = QHBoxLayout()

        # 左侧：控制面板
        left_layout = QVBoxLayout()

        # 扫描按钮
        btn_scan = QPushButton("扫描数据集")
        btn_scan.clicked.connect(self.scan_dataset)
        left_layout.addWidget(btn_scan)

        # 数据集统计
        self.label_stats = QLabel("数据集: 未扫描")
        left_layout.addWidget(self.label_stats)

        # 采样按钮
        btn_sample = QPushButton("随机采样30张")
        btn_sample.clicked.connect(self.sample_paintings)
        left_layout.addWidget(btn_sample)

        # 绘画列表
        self.list_paintings = QListWidget()
        self.list_paintings.itemClicked.connect(self.on_painting_selected)
        left_layout.addWidget(self.list_paintings)

        # 日志
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        left_layout.addWidget(self.log_text)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        main_layout.addWidget(left_widget, stretch=1)

        # 右侧：图片显示
        right_layout = QVBoxLayout()

        # 图片信息
        self.label_info = QLabel("请先扫描数据集")
        right_layout.addWidget(self.label_info)

        # 图片显示
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(600, 400)
        self.image_label.setStyleSheet("border: 1px solid black;")
        right_layout.addWidget(self.image_label)

        # 导航按钮
        nav_layout = QHBoxLayout()
        btn_prev = QPushButton("上一张")
        btn_prev.clicked.connect(self.prev_painting)
        nav_layout.addWidget(btn_prev)

        btn_next = QPushButton("下一张")
        btn_next.clicked.connect(self.next_painting)
        nav_layout.addWidget(btn_next)

        right_layout.addLayout(nav_layout)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        main_layout.addWidget(right_widget, stretch=2)

        self.setLayout(main_layout)

    def log(self, message):
        """输出日志"""
        self.log_text.append(message)
        print(message)

    def scan_dataset(self):
        """扫描数据集"""
        self.log("\n" + "=" * 60)
        self.log("开始扫描数据集...")
        self.log("=" * 60)

        try:
            # 导入 DatasetManager
            from engine.dataset import DatasetManager

            # 扫描
            self.dataset_manager = DatasetManager('./dataset')

            # 获取统计信息
            stats = self.dataset_manager.get_statistics()
            painting_stats = stats['paintings']

            self.log(f"\n✓ 扫描完成:")
            self.log(f"  绘画总数: {painting_stats['total']} 张")
            self.log(f"  流派数: {len(painting_stats['styles'])}")

            # 显示各流派统计
            self.log(f"\n各流派详情:")
            for style, count in painting_stats['styles'].items():
                self.log(f"  - {style}: {count} 张")

            # 更新统计标签
            self.label_stats.setText(
                f"数据集: {painting_stats['total']} 张绘画, "
                f"{len(painting_stats['styles'])} 个流派"
            )

            if painting_stats['total'] == 0:
                self.log("\n⚠ 警告: 没有找到任何绘画!")
                self.log("\n请检查以下目录:")
                self.log("  ./dataset/painting/wikiart/")
                self.log("\n目录结构应该是:")
                self.log("  dataset/painting/wikiart/")
                self.log("    ├── Cubism/")
                self.log("    │   ├── painting1.jpg")
                self.log("    │   └── painting2.jpg")
                self.log("    ├── Impressionism/")
                self.log("    │   └── ...")
                self.log("    └── ...")

        except Exception as e:
            self.log(f"\n✗ 扫描失败: {e}")
            import traceback
            self.log(traceback.format_exc())

    def sample_paintings(self):
        """随机采样绘画"""
        if self.dataset_manager is None:
            self.log("⚠ 请先扫描数据集")
            return

        try:
            self.log("\n随机采样30张绘画...")

            # 采样
            self.current_paintings = self.dataset_manager.sample_paintings(30)

            self.log(f"✓ 采样完成: {len(self.current_paintings)} 张")

            # 清空列表
            self.list_paintings.clear()

            # 添加到列表
            for i, painting in enumerate(self.current_paintings):
                item_text = f"{i + 1}. {painting['style']} - {painting['filename']}"
                self.list_paintings.addItem(item_text)

            # 显示第一张
            if self.current_paintings:
                self.current_index = 0
                self.show_painting(0)

        except Exception as e:
            self.log(f"✗ 采样失败: {e}")
            import traceback
            self.log(traceback.format_exc())

    def show_painting(self, index):
        """显示指定索引的绘画"""
        if not self.current_paintings:
            return

        if index < 0 or index >= len(self.current_paintings):
            return

        painting = self.current_paintings[index]

        # 更新信息
        self.label_info.setText(
            f"[{index + 1}/{len(self.current_paintings)}] "
            f"{painting['style']} - {painting['filename']}"
        )

        # 加载图片
        if os.path.exists(painting['path']):
            pixmap = QPixmap(painting['path'])

            if pixmap.isNull():
                self.log(f"✗ 无法加载图片: {painting['path']}")
                self.image_label.setText("图片加载失败")
            else:
                # 缩放显示
                scaled_pixmap = pixmap.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)

                self.log(f"✓ 显示: {painting['filename']} ({pixmap.width()}x{pixmap.height()})")
        else:
            self.log(f"✗ 文件不存在: {painting['path']}")
            self.image_label.setText(f"文件不存在:\n{painting['path']}")

        self.current_index = index

        # 高亮列表项
        self.list_paintings.setCurrentRow(index)

    def on_painting_selected(self, item):
        """点击列表项"""
        index = self.list_paintings.row(item)
        self.show_painting(index)

    def prev_painting(self):
        """上一张"""
        if self.current_paintings:
            new_index = (self.current_index - 1) % len(self.current_paintings)
            self.show_painting(new_index)

    def next_painting(self):
        """下一张"""
        if self.current_paintings:
            new_index = (self.current_index + 1) % len(self.current_paintings)
            self.show_painting(new_index)


def main():
    """主函数"""
    print("=" * 60)
    print("绘画数据集测试")
    print("=" * 60)
    print("\n使用说明:")
    print("1. 点击'扫描数据集'检查数据集")
    print("2. 查看统计信息和各流派数量")
    print("3. 点击'随机采样30张'测试采样")
    print("4. 点击列表项或使用上一张/下一张查看图片")
    print("\n如果扫描失败，查看日志中的错误信息")
    print("=" * 60 + "\n")

    app = QApplication(sys.argv)
    window = PaintingTestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()