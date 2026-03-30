"""
devices — 设备驱动与数据采集模块
================================
将原 core/ 和 gui/device_controller.py 中的设备层统一迁移至此包。

所有导入均为懒加载，避免缺少第三方库时阻塞启动。
使用方式：from devices.controller import DeviceController
"""

__all__ = [
    "DeviceController",
    "NeuracleHEEGDevice",
    "MockHEEGDevice",
    "MockShimmerDevice",
    "DataSaver",
    "VRADBController",
    "ShimmerGSRDevice",
    "ShimmerEMGDevice",
    "VideoLSLStream",
    "AudioLSLStream",
]
