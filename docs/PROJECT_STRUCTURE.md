# 📁 Shimmer GSR+ LSL Integration - 项目结构

```
shimmer_lsl_integration/
│
├── 📘 文档 (Documentation)
│   ├── INDEX.md                    ⭐ 从这里开始! 文档导航
│   ├── GETTING_STARTED.md          🚀 5分钟快速入门
│   ├── QUICK_REFERENCE.md          📋 快速参考手册
│   ├── README.md                   📖 完整使用文档
│   ├── PROJECT_SUMMARY.md          🔧 技术架构说明
│   └── PROJECT_CHECKLIST.md        ✅ 项目完整性检查
│
├── 🎯 核心程序 (Core Application)
│   ├── main.py                     ▶️  主程序入口
│   ├── config.py                   ⚙️  配置文件 (需要编辑!)
│   ├── shimmer_device.py           📡 Shimmer设备管理
│   ├── lsl_manager.py              🌊 LSL流管理
│   └── data_saver.py               💾 数据保存模块
│
├── 🔧 工具脚本 (Utilities)
│   ├── setup.py                    📦 自动安装脚本
│   ├── scan_devices.py             🔍 设备扫描工具
│   └── test_lsl_receiver.py        🧪 LSL接收测试
│
├── 📝 配置文件 (Configuration)
│   └── requirements.txt            📋 Python依赖列表
│
└── 📂 自动创建的目录 (Auto-created)
    ├── data/                       💿 数据输出目录
    │   ├── shimmer_gsr_*.csv      (数据文件)
    │   └── *_metadata.json        (元数据文件)
    │
    └── logs/                       📊 日志目录
        └── shimmer_lsl_*.log      (运行日志)
```

---

## 📊 文件大小和类型统计

### Python代码文件 (8个)
```
main.py             13KB  ⭐⭐⭐  主程序
shimmer_device.py   9.1KB ⭐⭐⭐  设备控制
lsl_manager.py      9.4KB ⭐⭐⭐  LSL集成
data_saver.py       11KB  ⭐⭐⭐  数据保存
config.py           2.3KB ⭐⭐⭐  配置
setup.py            7.6KB ⭐⭐   安装工具
scan_devices.py     6.7KB ⭐⭐   扫描工具
test_lsl_receiver.py 4.1KB ⭐   测试工具
───────────────────────────────
总计: ~63KB, 2000+行代码
```

### 文档文件 (6个)
```
INDEX.md              5.9KB ⭐⭐⭐  导航索引
GETTING_STARTED.md    3.7KB ⭐⭐⭐  入门指南
README.md             6.5KB ⭐⭐⭐  完整文档
QUICK_REFERENCE.md    4.8KB ⭐⭐   快速参考
PROJECT_SUMMARY.md    5.3KB ⭐    技术总结
PROJECT_CHECKLIST.md  5.9KB ⭐    完整性检查
───────────────────────────────
总计: ~32KB
```

### 配置文件 (1个)
```
requirements.txt      744B  ⭐⭐⭐  依赖列表
```

---

## 🎯 文件重要性评级

### ⭐⭐⭐ 必读/必用
- `INDEX.md` - 文档入口
- `GETTING_STARTED.md` - 快速开始
- `config.py` - 必须配置
- `main.py` - 主程序
- 核心模块 (shimmer_device, lsl_manager, data_saver)

### ⭐⭐ 常用
- `QUICK_REFERENCE.md` - 日常参考
- `README.md` - 详细文档
- `scan_devices.py` - 设备查找
- `setup.py` - 首次安装

### ⭐ 可选
- `PROJECT_SUMMARY.md` - 深入了解
- `PROJECT_CHECKLIST.md` - 验证完整性
- `test_lsl_receiver.py` - 功能测试

---

## 📍 关键文件说明

### 🔴 必须先看的文件

#### 1️⃣ INDEX.md
**用途**: 项目导航
**何时看**: 最先阅读
**内容**: 所有文档的导航索引

#### 2️⃣ GETTING_STARTED.md  
**用途**: 快速入门
**何时看**: 首次使用
**内容**: 5-10分钟快速上手指南

#### 3️⃣ config.py
**用途**: 系统配置
**何时编辑**: 运行程序前
**内容**: 端口、采样率、传感器设置

---

### 🟢 日常使用的文件

#### ▶️ main.py
**用途**: 主程序
**如何运行**: `python main.py`
**功能**: 启动完整的数据采集系统

#### 📋 QUICK_REFERENCE.md
**用途**: 快速查找
**何时看**: 忘记命令时
**内容**: 常用命令和配置速查

#### 🔍 scan_devices.py
**用途**: 查找设备
**如何运行**: `python scan_devices.py`
**功能**: 扫描并显示Shimmer设备信息

---

### 🟡 深入学习的文件

#### 📖 README.md
**用途**: 完整文档
**何时看**: 需要详细信息时
**内容**: 完整的功能说明和指南

#### 🔧 PROJECT_SUMMARY.md
**用途**: 技术细节
**何时看**: 想了解架构时
**内容**: 技术实现和设计思路

#### 🧪 test_lsl_receiver.py
**用途**: LSL测试
**如何运行**: `python test_lsl_receiver.py`
**功能**: 验证LSL流是否正常工作

---

## 🚀 使用流程与文件关系

### 第一次使用
```
1. INDEX.md 或 GETTING_STARTED.md
   ↓
2. setup.py (安装依赖)
   ↓
3. scan_devices.py (查找设备)
   ↓
4. config.py (配置端口)
   ↓
5. main.py (运行程序)
   ↓
6. test_lsl_receiver.py (验证)
```

### 日常使用
```
1. config.py (如需调整)
   ↓
2. main.py (开始采集)
   ↓
3. data/ (查看数据)
```

### 遇到问题
```
1. logs/ (查看日志)
   ↓
2. QUICK_REFERENCE.md (查找解决方案)
   ↓
3. README.md (详细说明)
   ↓
4. 测试脚本 (定位问题)
```

---

## 📦 模块依赖关系

```
main.py
├── config.py
├── shimmer_device.py
│   └── shimmer (外部库)
├── lsl_manager.py
│   └── pylsl (外部库)
└── data_saver.py

工具脚本 (独立运行)
├── setup.py
├── scan_devices.py
└── test_lsl_receiver.py
    └── pylsl
```

---

## 🔄 数据流向

```
Shimmer设备 (蓝牙)
    ↓
shimmer_device.py (读取)
    ↓
main.py (协调)
    ├→ lsl_manager.py → LSL网络 → 其他应用
    └→ data_saver.py → data/目录 → CSV文件
```

---

## 📂 输出文件位置

### 数据文件
```
data/
├── shimmer_gsr_20241112_143025.csv
├── shimmer_gsr_20241112_143025_metadata.json
├── shimmer_gsr_20241112_150230.csv
└── shimmer_gsr_20241112_150230_metadata.json
```

### 日志文件
```
logs/
├── shimmer_lsl_20241112_143025.log
└── shimmer_lsl_20241112_150230.log
```

---

## 🎨 文件命名规范

### 数据文件
格式: `shimmer_gsr_YYYYMMDD_HHMMSS.csv`
示例: `shimmer_gsr_20241112_143025.csv`

### 元数据文件
格式: `shimmer_gsr_YYYYMMDD_HHMMSS_metadata.json`
示例: `shimmer_gsr_20241112_143025_metadata.json`

### 日志文件
格式: `shimmer_lsl_YYYYMMDD_HHMMSS.log`
示例: `shimmer_lsl_20241112_143025.log`

---

## 💡 快速导航提示

### 我想...

#### 快速开始
→ `INDEX.md` 或 `GETTING_STARTED.md`

#### 查找命令
→ `QUICK_REFERENCE.md`

#### 详细了解
→ `README.md`

#### 配置系统
→ `config.py`

#### 运行程序
→ `main.py`

#### 查找设备
→ `scan_devices.py`

#### 测试功能
→ `test_lsl_receiver.py`

#### 查看数据
→ `data/` 目录

#### 检查日志
→ `logs/` 目录

---

## 📱 移动和重命名

### 可以移动的目录
- ✅ `data/` - 数据输出目录
- ✅ `logs/` - 日志目录

在 `config.py` 中修改路径即可

### 不建议修改
- ❌ 核心Python文件
- ❌ 文档文件
- ❌ requirements.txt

---

**提示**: 建议保持原始结构,方便使用和维护! 📌
