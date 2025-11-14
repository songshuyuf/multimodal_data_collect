# Shimmer GSR+ LSL Integration

这个项目实现了Shimmer GSR+设备与Lab Streaming Layer (LSL)的集成,用于多模态数据同步采集。

## 项目概述

该系统可以:
- 通过蓝牙连接Shimmer GSR+设备
- 实时采集GSR(皮肤电反应)和其他生理信号
- 通过LSL框架与其他模态(视频、音频、文本、EEG等)同步
- 将原始数据保存到本地文件
- 提供实时数据流监控

## 系统要求

### 硬件
- Shimmer GSR+ 设备
- 蓝牙适配器(如果计算机没有内置蓝牙)
- 运行Windows, Linux或macOS的计算机

### 软件
- Python 3.7+
- 蓝牙驱动(系统自带或需要安装)

## 安装步骤

### 1. 克隆或下载项目

```bash
cd shimmer_lsl_integration
```

### 2. 创建虚拟环境(推荐)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 安装Shimmer Python库

有两个选项:

**选项1: matmont/shimmer3 (推荐用于基础功能)**
```bash
pip install git+https://github.com/matmont/shimmer3.git
```

**选项2: seemoo-lab/pyshimmer (功能更全面)**
```bash
pip install git+https://github.com/seemoo-lab/pyshimmer.git
```

### 5. 配置蓝牙连接

#### Windows
1. 打开蓝牙设置
2. 配对Shimmer设备(PIN通常是1234)
3. 查看设备管理器中的COM端口号(例如COM14)

#### Linux
```bash
# 扫描蓝牙设备
hcitool scan

# 绑定设备 (替换MAC地址)
sudo rfcomm bind 0 00:06:66:XX:XX:XX 1

# 这会创建 /dev/rfcomm0
```

#### macOS
macOS可能需要额外配置,参考Shimmer官方文档。

## 配置

编辑 `config.py` 文件来配置系统:

```python
# Shimmer设备配置
SHIMMER_CONFIG = {
    'com_port': 'COM14',  # 修改为你的端口
    'sampling_rate': 128.0,  # 采样率
    'enabled_sensors': ['gsr', 'ppg', 'battery'],
}

# LSL流配置
LSL_CONFIG = {
    'stream_name': 'ShimmerGSR',
    'stream_type': 'GSR',
    'source_id': 'shimmer_gsr_001',
}

# 数据保存配置
DATA_SAVING_CONFIG = {
    'save_raw_data': True,
    'output_directory': './data',
    'file_format': 'csv',
}
```

## 使用方法

### 基本使用

启动数据采集:

```bash
python main.py
```

指定COM端口:

```bash
python main.py --port COM14
```

设置采集时长(秒):

```bash
python main.py --duration 300
```

### 测试LSL流

在另一个终端运行接收器测试脚本:

```bash
python test_lsl_receiver.py
```

这个脚本会:
- 查找并连接到Shimmer GSR的LSL流
- 显示流的详细信息
- 实时接收和显示数据
- 统计数据接收率

### 与其他模态同步

使用LabRecorder或其他LSL工具来同步记录多个数据流:

1. **下载LabRecorder**: https://github.com/labstreaminglayer/App-LabRecorder/releases

2. **启动所有数据源**:
   - Shimmer GSR (本项目)
   - 视频采集(使用LSL-compatible工具)
   - 音频采集(使用LSL-compatible工具)
   - EEG设备(等EEG设备到货后)

3. **在LabRecorder中**:
   - 点击"Update"查看所有可用流
   - 选择要记录的流
   - 点击"Record"开始同步记录

## 项目结构

```
shimmer_lsl_integration/
├── config.py              # 配置文件
├── shimmer_device.py      # Shimmer设备管理
├── lsl_manager.py         # LSL流管理
├── data_saver.py          # 数据保存模块
├── main.py                # 主程序
├── test_lsl_receiver.py   # LSL接收器测试
├── requirements.txt       # Python依赖
├── README.md              # 本文件
├── data/                  # 数据输出目录(自动创建)
└── logs/                  # 日志目录(自动创建)
```

## 数据格式

### CSV输出格式

保存的CSV文件包含以下列:
- `Timestamp`: LSL时间戳(秒)
- `LocalTime`: 本地时间(可读格式)
- `GSR_Skin_Conductance`: 皮肤电导(μS)
- `GSR_Skin_Resistance`: 皮肤电阻(kΩ)
- `PPG_A13`: 光电容积脉搏波(mV)
- ... (其他启用的传感器)

### 元数据文件

每个会话还会生成一个JSON元数据文件,包含:
- 会话开始/结束时间
- 采样率和通道信息
- 设备信息
- 文件路径

## 故障排除

### 问题1: 无法连接到Shimmer设备

**解决方案**:
1. 确认设备已配对并且电源已打开
2. 检查COM端口号是否正确
3. 尝试手动指定端口: `python main.py --port COM14`
4. Linux用户确保有访问串口的权限: `sudo usermod -a -G dialout $USER`

### 问题2: 找不到LSL流

**解决方案**:
1. 确认主程序正在运行
2. 检查防火墙设置(LSL使用UDP端口)
3. 确认所有设备在同一网络

### 问题3: 数据采集率低于预期

**解决方案**:
1. 减少缓冲区大小
2. 确保蓝牙连接稳定
3. 关闭其他占用CPU的程序

### 问题4: Shimmer库安装失败

**解决方案**:
1. 确保安装了Git
2. 尝试不同的Shimmer库(matmont vs seemoo-lab)
3. 检查Python版本兼容性

## 进阶使用

### 自定义传感器配置

在 `config.py` 中修改启用的传感器:

```python
'enabled_sensors': [
    'gsr',           # 皮肤电反应
    'ppg',           # 光电容积脉搏波
    'accelerometer', # 加速度计
    'battery',       # 电池电压
],
```

### 修改采样率

支持的采样率: 51.2, 128.0, 256.0, 512.0 Hz

```python
'sampling_rate': 256.0,  # 更高的采样率
```

### 添加自定义数据处理

在 `main.py` 的 `_extract_sample_from_packet()` 方法中添加处理逻辑:

```python
def _extract_sample_from_packet(self, packet: dict) -> tuple:
    # 提取原始数据
    sample, timestamp = ...
    
    # 添加自定义处理
    # 例如: 滤波, 归一化等
    
    return processed_sample, timestamp
```

## 开发和调试

### 启用调试日志

在 `config.py` 中:

```python
LOGGING_CONFIG = {
    'level': 'DEBUG',  # 改为DEBUG级别
}
```

### 测试单个模块

每个模块都可以独立运行测试:

```bash
# 测试Shimmer设备连接
python shimmer_device.py

# 测试LSL流
python lsl_manager.py

# 测试数据保存
python data_saver.py
```

## 参考资料

- [Shimmer官方文档](https://www.shimmersensing.com/support/)
- [Lab Streaming Layer文档](https://labstreaminglayer.readthedocs.io/)
- [pylsl GitHub](https://github.com/labstreaminglayer/pylsl)
- [Shimmer Python库](https://github.com/matmont/shimmer3)

## 许可证

本项目用于研究目的。请遵守Shimmer和LSL的相关许可协议。

## 联系方式

如有问题,请联系项目维护者或查看相关文档。

---

**最后更新**: 2024年
