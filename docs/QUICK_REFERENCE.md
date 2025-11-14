# Shimmer GSR+ LSL Integration - 快速参考指南

## 快速开始(5分钟)

### 1. 安装依赖
```bash
python setup.py
```

### 2. 查找设备
```bash
python scan_devices.py
```

### 3. 修改配置
编辑 `config.py`:
```python
'com_port': 'COM14',  # 你的端口
```

### 4. 运行
```bash
python main.py
```

### 5. 测试LSL(另一个终端)
```bash
python test_lsl_receiver.py
```

---

## 常用命令

### 运行主程序
```bash
# 基本运行
python main.py

# 指定端口
python main.py --port COM14

# 限制时长(300秒)
python main.py --duration 300
```

### 测试和调试
```bash
# 扫描设备
python scan_devices.py

# 测试LSL接收
python test_lsl_receiver.py

# 测试单个模块
python shimmer_device.py
python lsl_manager.py
python data_saver.py
```

---

## 文件说明

| 文件 | 功能 |
|------|------|
| `main.py` | 主程序入口 |
| `config.py` | 配置文件 |
| `shimmer_device.py` | Shimmer设备管理 |
| `lsl_manager.py` | LSL流管理 |
| `data_saver.py` | 数据保存 |
| `scan_devices.py` | 设备扫描工具 |
| `test_lsl_receiver.py` | LSL接收测试 |
| `setup.py` | 安装脚本 |
| `README.md` | 详细文档 |

---

## 配置速查

### Shimmer配置
```python
SHIMMER_CONFIG = {
    'com_port': 'COM14',           # 端口
    'sampling_rate': 128.0,        # 采样率: 51.2/128/256/512
    'enabled_sensors': [
        'gsr',                     # GSR信号
        'ppg',                     # PPG信号  
        'battery',                 # 电池电压
    ],
    'use_calibrated_data': True,   # 使用校准数据
}
```

### LSL配置
```python
LSL_CONFIG = {
    'stream_name': 'ShimmerGSR',   # 流名称
    'stream_type': 'GSR',          # 流类型
    'source_id': 'shimmer_gsr_001', # 设备ID
}
```

### 数据保存配置
```python
DATA_SAVING_CONFIG = {
    'save_raw_data': True,         # 是否保存
    'output_directory': './data',  # 输出目录
    'file_format': 'csv',          # 格式: csv/hdf5/both
    'buffer_size': 1000,           # 缓冲区大小
}
```

---

## 常见问题快速解决

### 无法连接设备
1. 检查设备是否配对
2. 确认COM端口正确
3. Windows: 查看设备管理器
4. Linux: 运行 `sudo rfcomm bind 0 MAC_ADDRESS 1`

### 找不到LSL流
1. 确认主程序在运行
2. 检查防火墙设置
3. 确保在同一网络

### 数据率低
1. 减少缓冲区大小
2. 降低采样率
3. 检查蓝牙信号强度

### 导入错误
```bash
pip install pylsl numpy pyserial
pip install git+https://github.com/matmont/shimmer3.git
```

---

## 端口配置

### Windows
- 格式: `COM14`
- 查找: 设备管理器 > 端口

### Linux  
- 格式: `/dev/rfcomm0`
- 创建: `sudo rfcomm bind 0 MAC_ADDRESS 1`

### macOS
- 格式: `/dev/tty.Shimmer3-XXXX-RN-SPP`
- 查找: `ls /dev/tty.*`

---

## 数据输出

### CSV文件列
- `Timestamp`: LSL时间戳
- `LocalTime`: 本地时间
- `GSR_Skin_Conductance`: 皮肤电导(μS)
- `GSR_Skin_Resistance`: 皮肤电阻(kΩ)
- `PPG_A13`: 光电脉搏(mV)

### 文件位置
- 数据: `./data/shimmer_gsr_YYYYMMDD_HHMMSS.csv`
- 元数据: `./data/shimmer_gsr_YYYYMMDD_HHMMSS_metadata.json`
- 日志: `./logs/shimmer_lsl_YYYYMMDD_HHMMSS.log`

---

## 多模态同步工作流

### 1. 启动所有数据源
```bash
# 终端1: Shimmer GSR
python main.py

# 终端2: 视频采集
# (运行你的视频LSL程序)

# 终端3: 音频采集
# (运行你的音频LSL程序)

# 终端4: 文本/标注
# (运行你的标注LSL程序)
```

### 2. 使用LabRecorder记录
1. 启动LabRecorder
2. 点击 "Update" 查看所有流
3. 选择要记录的流
4. 点击 "Record" 开始
5. 实验结束后点击 "Stop"

### 3. 数据分析
- LabRecorder输出: `.xdf` 文件
- 使用 `pyxdf` 库读取: `pip install pyxdf`

---

## 调试模式

在 `config.py` 中启用:
```python
LOGGING_CONFIG = {
    'level': 'DEBUG',  # INFO -> DEBUG
}
```

查看详细日志:
```bash
tail -f logs/shimmer_lsl_*.log
```

---

## 性能优化

### 提高数据率
- 增加 `buffer_size`
- 使用有线连接(如果可能)
- 关闭不需要的传感器

### 减少延迟
- 减少 `buffer_size`
- 使用更高的蓝牙版本
- 减少系统负载

### 节省磁盘空间
- 降低采样率
- 只启用需要的传感器
- 使用HDF5格式(更压缩)

---

## 支持的传感器

| 传感器 | 配置名称 | 说明 |
|--------|---------|------|
| 皮肤电反应 | `'gsr'` | 主要信号 |
| 光电脉搏 | `'ppg'` | 心率相关 |
| 加速度计 | `'accelerometer'` | 运动检测 |
| 电池 | `'battery'` | 电量监控 |

---

## 重要链接

- **项目文档**: `README.md`
- **Shimmer官网**: https://www.shimmersensing.com
- **LSL文档**: https://labstreaminglayer.readthedocs.io
- **LabRecorder**: https://github.com/labstreaminglayer/App-LabRecorder
- **pyxdf库**: https://github.com/xdf-modules/pyxdf

---

**提示**: 第一次使用前请完整阅读 `README.md`
