# 📚 Shimmer GSR+ LSL Integration - 文档索引

欢迎!这里是完整的文档导航。

---

## 🎯 我想...

### 快速开始使用
→ 阅读 [**GETTING_STARTED.md**](GETTING_STARTED.md) (5-10分钟)

### 查找常用命令
→ 查看 [**QUICK_REFERENCE.md**](QUICK_REFERENCE.md) (速查表)

### 了解详细功能
→ 阅读 [**README.md**](README.md) (完整文档)

### 理解项目架构
→ 查看 [**PROJECT_SUMMARY.md**](PROJECT_SUMMARY.md) (技术总结)

---

## 📁 项目文件说明

### 核心程序 (Core)
| 文件 | 说明 | 用途 |
|------|------|------|
| `main.py` | 主程序 | 运行主采集程序 |
| `shimmer_device.py` | 设备管理 | Shimmer设备连接和控制 |
| `lsl_manager.py` | LSL流管理 | 创建和管理LSL数据流 |
| `data_saver.py` | 数据保存 | 保存采集的数据到文件 |
| `config.py` | 配置文件 | **首先要编辑的文件** |

### 工具脚本 (Tools)
| 文件 | 说明 | 何时使用 |
|------|------|----------|
| `setup.py` | 安装脚本 | 首次使用时运行 |
| `scan_devices.py` | 设备扫描 | 查找Shimmer设备端口 |
| `test_lsl_receiver.py` | LSL测试 | 验证LSL流工作正常 |

### 文档 (Documentation)
| 文件 | 内容 | 适合对象 |
|------|------|----------|
| `GETTING_STARTED.md` | 入门指南 | 初次使用者 |
| `QUICK_REFERENCE.md` | 快速参考 | 日常使用者 |
| `README.md` | 完整文档 | 所有用户 |
| `PROJECT_SUMMARY.md` | 技术总结 | 开发者 |
| `INDEX.md` | 本文件 | 所有用户 |

### 配置和依赖 (Config)
| 文件 | 说明 |
|------|------|
| `requirements.txt` | Python依赖列表 |
| `config.py` | 系统配置文件 |

---

## 🚀 使用流程

### 第一次使用
1. 📖 阅读 `GETTING_STARTED.md`
2. ⚙️ 运行 `python setup.py`
3. 🔍 运行 `python scan_devices.py`
4. ✏️ 编辑 `config.py`
5. ▶️ 运行 `python main.py`

### 日常使用
1. 💻 `python main.py` - 开始采集
2. 📊 查看 `data/` 目录 - 获取数据
3. 📚 参考 `QUICK_REFERENCE.md` - 查找命令

### 遇到问题
1. 🔍 查看 `README.md` 的"故障排除"部分
2. 📋 检查 `QUICK_REFERENCE.md` 的"常见问题"
3. 🐛 查看 `logs/` 目录中的日志文件

---

## 📖 推荐阅读顺序

### 入门者 (Beginner)
1. `GETTING_STARTED.md` - 快速上手
2. `QUICK_REFERENCE.md` - 常用命令
3. `README.md` (可选) - 深入了解

### 高级用户 (Advanced)
1. `README.md` - 完整功能
2. `PROJECT_SUMMARY.md` - 技术细节
3. 源代码 - 自定义开发

### 集成者 (Integration)
1. `README.md` - 多模态同步部分
2. LSL官方文档
3. `test_lsl_receiver.py` - 参考示例

---

## 🎓 学习路径

### Level 1: 基础使用
- [ ] 成功连接Shimmer设备
- [ ] 采集并保存数据
- [ ] 查看和理解CSV输出

**完成标志**: 能够独立运行完整的数据采集会话

### Level 2: LSL集成
- [ ] 理解LSL工作原理
- [ ] 运行LSL接收器测试
- [ ] 使用LabRecorder录制数据

**完成标志**: 能够同步多个数据流

### Level 3: 自定义配置
- [ ] 修改采样率和传感器
- [ ] 调整数据保存格式
- [ ] 优化性能参数

**完成标志**: 能够针对特定实验需求配置系统

### Level 4: 高级开发
- [ ] 理解代码架构
- [ ] 添加自定义处理
- [ ] 集成新的传感器

**完成标志**: 能够扩展和修改系统功能

---

## 🔗 外部资源

### Shimmer
- [官方网站](https://www.shimmersensing.com)
- [文档中心](https://www.shimmersensing.com/support/)
- [Python库](https://github.com/matmont/shimmer3)

### Lab Streaming Layer
- [官方文档](https://labstreaminglayer.readthedocs.io)
- [GitHub](https://github.com/labstreaminglayer)
- [LabRecorder下载](https://github.com/labstreaminglayer/App-LabRecorder/releases)

### Python库
- [pylsl文档](https://labstreaminglayer.readthedocs.io/projects/liblsl/ref/pylsl.html)
- [NumPy](https://numpy.org/doc/)
- [PySerial](https://pythonhosted.org/pyserial/)

---

## 💡 实用提示

### 快速命令
```bash
# 完整工作流
python scan_devices.py     # 1. 找设备
# 编辑 config.py            # 2. 配置
python main.py             # 3. 采集
python test_lsl_receiver.py # 4. 验证
```

### 常见操作
- **修改端口**: 编辑 `config.py` 中的 `com_port`
- **查看数据**: 打开 `data/*.csv`
- **查看日志**: 打开 `logs/*.log`
- **测试模块**: 直接运行任何 `.py` 文件

### 调试技巧
1. 启用DEBUG日志: `config.py` → `'level': 'DEBUG'`
2. 单独测试模块: `python shimmer_device.py`
3. 查看实时日志: `tail -f logs/*.log` (Linux/Mac)

---

## ✅ 快速检查

使用这个检查清单确保系统就绪:

### 环境检查
- [ ] Python 3.7+ 已安装
- [ ] 所有依赖已安装 (`python setup.py`)
- [ ] Shimmer设备已充电
- [ ] 蓝牙功能正常

### 配置检查
- [ ] `config.py` 中的端口号正确
- [ ] 采样率设置合理(推荐128Hz)
- [ ] 传感器配置正确

### 功能检查
- [ ] 设备扫描成功 (`python scan_devices.py`)
- [ ] 主程序能运行 (`python main.py`)
- [ ] LSL流可接收 (`python test_lsl_receiver.py`)
- [ ] 数据成功保存在 `data/` 目录

---

## 🤔 还有疑问?

### 按优先级查找答案:
1. **本项目文档** - 大多数问题都有答案
2. **测试脚本** - 运行测试找出问题
3. **日志文件** - 查看详细错误信息
4. **外部文档** - Shimmer和LSL官方文档
5. **源代码** - 代码中有详细注释

---

## 📞 需要支持?

如果你遇到了无法解决的问题:

1. **收集信息**
   - 错误消息
   - 日志文件
   - 系统环境(OS, Python版本等)

2. **检查文档**
   - README.md的故障排除部分
   - QUICK_REFERENCE.md的常见问题

3. **尝试测试**
   - 运行相关的测试脚本
   - 检查配置文件

---

## 📅 文档更新

- **创建日期**: 2024年11月
- **最后更新**: 2024年11月
- **版本**: 1.0.0
- **状态**: 完整可用

---

**提示**: 建议将此文档收藏,作为项目使用的起点! 🌟
