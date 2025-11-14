# 🔧 使用pyshimmer库的安装说明

## 重要更新!

根据你提供的代码,我已经将项目更新为使用 **pyshimmer** 库(而不是之前的shimmer3)。

---

## 📦 安装步骤

### 1. 安装pyshimmer库

```powershell
# 方法1: 从PyPI安装(如果可用)
pip install pyshimmer

# 方法2: 从GitHub安装
pip install git+https://github.com/patrickmayy/pyshimmer.git
```

### 2. 安装其他依赖

```powershell
pip install pylsl numpy pyserial
```

### 3. 验证安装

```powershell
python -c "from pyshimmer import ShimmerBluetooth, EChannelType; print('pyshimmer installed successfully!')"
```

---

## ⚙️ 配置设备

### 1. 编辑config.py

```python
SHIMMER_CONFIG = {
    'com_port': 'COM6',  # 你的实际端口(根据scan_devices.py的结果)
    'sampling_rate': 128.0,
    'enabled_sensors': [
        'gsr',      # GSR信号
        'ppg',      # PPG信号(可选)
        'battery',  # 电池电压
    ],
}
```

### 2. 确认COM端口

根据你的扫描结果,你有以下端口:
- COM3
- COM4
- COM5
- COM6 ✅ (这个看起来最可能是Shimmer)

**建议**: 先用COM6尝试,如果不行再试其他端口。

---

## 🚀 运行程序

### 基本运行

```powershell
# 确保ConsensysPRO已关闭!
python main.py
```

### 指定端口运行

```powershell
python main.py --port COM6
```

### 限制时长

```powershell
python main.py --port COM6 --duration 60  # 运行60秒
```

---

## 🧪 测试步骤

### 步骤1: 测试设备连接

```powershell
python shimmer_device.py
```

这会:
- 列出所有COM端口
- 尝试连接设备
- 采集10秒数据
- 显示样本数据

**预期输出**:
```
=== Available COM Ports ===
  - COM6: 蓝牙链接上的标准串行 (COM6)
  ...

=== Testing Connection ===
Attempting to connect to Shimmer on COM6...
Initializing Shimmer device...
Successfully connected and initialized Shimmer on COM6

=== Device Info ===
sampling_rate: 128.0
enabled_sensors: ['gsr', 'battery']
channel_names: ['GSR_Skin_Conductance', 'GSR_Skin_Resistance', 'Battery_Voltage']

=== Streaming Data (10 seconds) ===
Data streaming started successfully
Packet #10: [5.23, 191.2, 3.8]...
Packet #20: [5.18, 193.1, 3.8]...
...
Total packets received: 1280
```

### 步骤2: 测试LSL流

```powershell
# 终端1: 运行主程序
python main.py

# 终端2: 运行接收测试
python test_lsl_receiver.py
```

---

## ⚠️ 重要提示

### 1. 关闭ConsensysPRO
在运行Python脚本前,**必须关闭ConsensysPRO软件**,否则会有端口占用冲突。

### 2. 确认设备配对
- 打开 Windows设置 → 蓝牙和其他设备
- 确认Shimmer设备已配对
- 记下设备名称(通常是Shimmer3-XXXX)

### 3. COM端口确认
如果不确定哪个是Shimmer的端口:
1. 打开设备管理器
2. 展开"端口(COM和LPT)"
3. 找到与Shimmer设备对应的端口

---

## 🐛 常见问题

### Q1: ModuleNotFoundError: No module named 'pyshimmer'

**解决**:
```powershell
pip install pyshimmer
# 或
pip install git+https://github.com/patrickmayy/pyshimmer.git
```

### Q2: 连接失败 "Failed to connect to Shimmer"

**检查**:
1. 设备是否开机
2. 设备是否配对
3. ConsensysPRO是否已关闭
4. COM端口是否正确

**尝试**:
```powershell
# 逐个测试端口
python main.py --port COM3
python main.py --port COM4
python main.py --port COM5
python main.py --port COM6
```

### Q3: "数据流启动失败: 'ShimmerBluetooth' object has no attribute 'get_sample'"

这个错误已经在新版本中修复了。新版本使用 `shimmer.read()` 方法而不是 `get_sample()`。

### Q4: 没有收到数据

**检查**:
1. 设备是否正常工作(LED是否闪烁)
2. 传感器是否正确连接
3. 查看日志文件 `logs/*.log`

---

## 📊 数据输出

成功运行后,数据会保存在:

```
data/
├── shimmer_gsr_20241112_150000.csv        # 数据文件
└── shimmer_gsr_20241112_150000_metadata.json  # 元数据
```

CSV格式:
```csv
Timestamp,LocalTime,GSR_Skin_Conductance,GSR_Skin_Resistance,Battery_Voltage
1731423600.123,2024-11-12 15:00:00.123000,5.23,191.2,3.8
1731423600.131,2024-11-12 15:00:00.131000,5.18,193.1,3.8
...
```

---

## 🎯 下一步

1. ✅ 安装pyshimmer库
2. ✅ 运行 `python shimmer_device.py` 测试连接
3. ✅ 运行 `python main.py` 开始采集
4. ✅ 运行 `python test_lsl_receiver.py` 验证LSL流

---

## 📞 需要帮助?

如果遇到问题:
1. 查看 `logs/` 目录中的日志文件
2. 运行 `python scan_devices.py` 检查设备
3. 查看 README.md 获取更多信息

---

**祝使用顺利!** 🎉
