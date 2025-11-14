# 🚀 Shimmer GSR+ LSL Integration - 入门指南

欢迎使用Shimmer GSR+与LSL的集成系统!这个指南会帮助你在5-10分钟内快速上手。

---

## 📋 前提条件

在开始之前,请确保你有:
- ✅ Shimmer GSR+ 设备
- ✅ 计算机(Windows/Linux/macOS)
- ✅ Python 3.7 或更高版本
- ✅ 蓝牙功能
- ✅ 互联网连接(用于安装依赖)

---

## 🎯 5分钟快速开始

### 第1步: 下载项目
项目已经准备好,所有文件都在 `shimmer_lsl_integration` 文件夹中。

### 第2步: 安装依赖
打开终端/命令提示符,进入项目目录:

```bash
cd shimmer_lsl_integration
python setup.py
```

按照提示完成安装。

### 第3步: 查找你的设备
```bash
python scan_devices.py
```

这会告诉你如何找到Shimmer设备的端口号。

### 第4步: 配置设备
编辑 `config.py` 文件,修改这一行:
```python
'com_port': 'COM14',  # 改成你的端口号
```

### 第5步: 运行!
```bash
python main.py
```

如果看到类似这样的输出,就说明成功了:
```
============================================================
Shimmer GSR+ LSL Integration
============================================================

[1/4] Initializing Shimmer GSR+ device...
✓ Successfully connected to Shimmer on COM14
...
Initialization complete! Ready to stream data.
```

---

## 📊 验证LSL流

在另一个终端窗口中:
```bash
python test_lsl_receiver.py
```

你应该看到实时数据流入!

---

## 🎮 基本操作

### 开始采集
```bash
python main.py
```

### 停止采集
按 `Ctrl+C`

### 查看数据
数据保存在 `data/` 文件夹中,文件名类似:
- `shimmer_gsr_20241112_143025.csv`
- `shimmer_gsr_20241112_143025_metadata.json`

---

## 🔧 常见问题

### Q: 无法连接到设备
**A:** 
1. 确保设备已打开并已配对
2. 运行 `python scan_devices.py` 查找正确端口
3. 检查蓝牙是否启用

### Q: 找不到LSL流
**A:**
1. 确保主程序正在运行
2. 检查防火墙设置
3. 尝试在本机运行接收器测试

### Q: 安装出错
**A:**
1. 确保Python版本 ≥ 3.7
2. 尝试手动安装: `pip install pylsl numpy pyserial`
3. 安装Shimmer库: `pip install git+https://github.com/matmont/shimmer3.git`

---

## 📚 下一步

### 多模态同步采集
1. 启动Shimmer采集: `python main.py`
2. 启动其他数据源(视频、音频等)
3. 使用LabRecorder统一录制所有LSL流

### 自定义配置
编辑 `config.py` 来:
- 调整采样率
- 启用/禁用传感器
- 修改数据保存位置

### 深入学习
- 阅读 `README.md` 了解详细功能
- 查看 `QUICK_REFERENCE.md` 快速查找命令
- 查看 `PROJECT_SUMMARY.md` 了解技术细节

---

## 🆘 获取帮助

### 文档
- `README.md` - 完整文档
- `QUICK_REFERENCE.md` - 快速参考
- `PROJECT_SUMMARY.md` - 项目总结

### 在线资源
- Shimmer官网: https://www.shimmersensing.com
- LSL文档: https://labstreaminglayer.readthedocs.io

### 测试脚本
```bash
python shimmer_device.py    # 测试设备连接
python lsl_manager.py        # 测试LSL流
python data_saver.py         # 测试数据保存
```

---

## ✅ 检查清单

开始使用前,确保:
- [ ] Python已安装(版本 ≥ 3.7)
- [ ] 依赖已安装(`python setup.py`)
- [ ] Shimmer设备已配对
- [ ] 端口号已在`config.py`中配置
- [ ] 可以成功运行 `python main.py`
- [ ] LSL流可以被接收(`python test_lsl_receiver.py`)

---

## 🎉 准备好了!

现在你已经准备好开始收集多模态数据了!

记住:
1. **总是先启动所有数据源**
2. **然后使用LabRecorder统一录制**
3. **实验结束后正常停止(Ctrl+C)**

祝研究顺利! 🚀

---

**需要帮助?** 查看其他文档或联系项目维护者。
