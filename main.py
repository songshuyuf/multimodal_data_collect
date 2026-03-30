"""
多模态数据采集系统 - GUI 主入口
v3.0 重构版：app/ + engine/ + devices/ + data/ 四层架构
"""

import sys
import os

if getattr(sys, 'frozen', False):
    # PyInstaller 6.x 把数据文件放在 _internal/ 子目录（即 sys._MEIPASS）
    # 切换工作目录到该位置，这样 ./experiment_config.json, ./dataset 等相对路径才能正确找到
    os.chdir(sys._MEIPASS)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main_window import main

if __name__ == '__main__':
    main()
