"""
GSR + EMG 双设备同时连接单元测试
=================================
使用 unittest.mock 模拟所有硬件依赖（serial / pyshimmer / heartpy），
无需真实 Shimmer 设备即可验证：
  - GSR / EMG 各自连接成功/失败
  - EMG 自动排除 GSR 已占用的 COM 端口
  - 双设备并行数据流与回调
  - 断开与资源清理

运行: pytest tests/test_dual_shimmer.py -v
"""

import os
import sys
import json
import time
import pytest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── 预注入硬件依赖的 stub（测试环境可能未安装） ─────────────
for _name in [
    "pyshimmer", "pyshimmer.dev", "pyshimmer.dev.channels",
    "pyshimmer.dev.exg", "pyshimmer.serial_base",
    "heartpy",
]:
    sys.modules.setdefault(_name, MagicMock())

try:
    import devices.heeg  # noqa: F401
except Exception:
    sys.modules.setdefault("devices.heeg", MagicMock())

import devices.controller as ctrl_mod
from devices.controller import DeviceController


# ── 辅助工具 ──────────────────────────────────────────────

class FakeComPort:
    """模拟 serial.tools.list_ports 返回的端口对象"""

    def __init__(self, device: str):
        self.device = device
        self.description = f"Bluetooth Serial Port ({device})"


def _make_mock_gsr(available_ports, connect_ok_ports):
    """
    构造一个 mock GSR 设备实例。

    Args:
        available_ports: _list_com_ports() 返回的端口列表
        connect_ok_ports: connect(port) 返回 True 的端口集合
    """
    dev = MagicMock()
    dev._list_com_ports.return_value = list(available_ports)
    dev._ser = None

    def _connect(port):
        if port in connect_ok_ports:
            ser = MagicMock()
            ser.port = port
            ser.is_open = True
            dev._ser = ser
            dev.is_connected = True
            return True
        return False

    dev.connect.side_effect = _connect
    dev.get_device_info.return_value = {"sampling_rate": 128.0}
    dev.start_streaming.return_value = True
    dev.stop_streaming.return_value = True
    return dev


def _make_mock_emg(connect_ok_ports):
    """
    构造一个 mock EMG 设备实例。

    Args:
        connect_ok_ports: connect(port) 返回 True 的端口集合
    """
    dev = MagicMock()
    dev._ser = None
    dev._connected = False
    dev.is_connected = False

    def _connect(port):
        if port in connect_ok_ports:
            ser = MagicMock()
            ser.port = port
            ser.is_open = True
            dev._ser = ser
            dev._connected = True
            dev.is_connected = True
            return True
        return False

    dev.connect.side_effect = _connect
    dev.get_device_info.return_value = {
        "type": "Shimmer3 ExG EMG",
        "sampling_rate": 1000.0,
    }
    return dev


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture()
def port_config_file(tmp_path):
    """用临时文件隔离端口记忆，避免污染真实配置"""
    f = tmp_path / "device_ports.json"
    f.write_text("{}", encoding="utf-8")
    return str(f)


@pytest.fixture()
def controller(port_config_file):
    """
    创建 DeviceController 实例，
    启用真实代码路径（CORE / SHIMMER / EMG 标志均为 True），
    端口记忆指向临时文件。
    """
    saved = {
        "CORE": ctrl_mod.CORE_AVAILABLE,
        "SHIMMER": ctrl_mod.SHIMMER_AVAILABLE,
        "EMG": ctrl_mod.SHIMMER_EMG_AVAILABLE,
        "PATH": ctrl_mod._PORT_CONFIG_PATH,
    }

    ctrl_mod.CORE_AVAILABLE = True
    ctrl_mod.SHIMMER_AVAILABLE = True
    ctrl_mod.SHIMMER_EMG_AVAILABLE = True
    ctrl_mod._PORT_CONFIG_PATH = port_config_file

    dc = DeviceController(use_mock_devices=False)
    yield dc

    if dc.is_recording:
        dc.is_recording = False

    ctrl_mod.CORE_AVAILABLE = saved["CORE"]
    ctrl_mod.SHIMMER_AVAILABLE = saved["SHIMMER"]
    ctrl_mod.SHIMMER_EMG_AVAILABLE = saved["EMG"]
    ctrl_mod._PORT_CONFIG_PATH = saved["PATH"]


def _connect_both(controller):
    """辅助：先连 GSR(COM6)，再连 EMG(COM7)，返回两个 mock 设备"""
    mock_gsr = _make_mock_gsr(["COM6", "COM7"], ["COM6"])
    with patch("devices.shimmer_gsr.ShimmerGSRDevice", return_value=mock_gsr):
        controller.initialize_shimmer()

    mock_emg = _make_mock_emg(["COM7"])
    fake_ports = [FakeComPort("COM6"), FakeComPort("COM7")]
    with patch("devices.shimmer_emg.ShimmerEMGDevice", return_value=mock_emg), \
         patch("serial.tools.list_ports.comports", return_value=fake_ports):
        controller.initialize_shimmer_emg()

    return mock_gsr, mock_emg


# ══════════════════════════════════════════════════════════
#  1. GSR 单独连接
# ══════════════════════════════════════════════════════════

class TestGSRConnect:

    def test_gsr_connect_success(self, controller):
        """COM6 可用 → GSR 连接成功"""
        mock_dev = _make_mock_gsr(["COM6", "COM7"], ["COM6"])

        with patch("devices.shimmer_gsr.ShimmerGSRDevice", return_value=mock_dev):
            result = controller.initialize_shimmer()

        assert result is True
        assert controller.shimmer_connected is True
        assert controller.shimmer_device is mock_dev
        mock_dev.connect.assert_called_with("COM6")

    def test_gsr_connect_no_ports(self, controller):
        """无 COM 端口 → GSR 连接失败"""
        mock_dev = _make_mock_gsr([], [])

        with patch("devices.shimmer_gsr.ShimmerGSRDevice", return_value=mock_dev):
            result = controller.initialize_shimmer()

        assert result is False
        assert controller.shimmer_connected is False

    def test_gsr_connect_port_memory(self, controller, port_config_file):
        """记忆端口 COM7 → 优先尝试 COM7 而非 COM6"""
        with open(port_config_file, "w", encoding="utf-8") as f:
            json.dump({"shimmer_gsr": {"port": "COM7"}}, f)

        tried = []
        mock_dev = _make_mock_gsr(["COM6", "COM7"], ["COM7"])
        _orig = mock_dev.connect.side_effect

        def _track(port):
            tried.append(port)
            return _orig(port)

        mock_dev.connect.side_effect = _track

        with patch("devices.shimmer_gsr.ShimmerGSRDevice", return_value=mock_dev):
            result = controller.initialize_shimmer()

        assert result is True
        assert tried[0] == "COM7"


# ══════════════════════════════════════════════════════════
#  2. EMG 单独连接
# ══════════════════════════════════════════════════════════

class TestEMGConnect:

    def test_emg_connect_success(self, controller):
        """COM7 可用 → EMG 连接成功（无 GSR）"""
        mock_dev = _make_mock_emg(["COM7"])
        fake_ports = [FakeComPort("COM6"), FakeComPort("COM7")]

        with patch("devices.shimmer_emg.ShimmerEMGDevice", return_value=mock_dev), \
             patch("serial.tools.list_ports.comports", return_value=fake_ports):
            result = controller.initialize_shimmer_emg()

        assert result is True
        assert controller.shimmer_emg_connected is True
        assert controller.shimmer_emg_device is mock_dev

    def test_emg_connect_no_ports(self, controller):
        """无 COM 端口 → EMG 连接失败"""
        mock_dev = _make_mock_emg([])

        with patch("devices.shimmer_emg.ShimmerEMGDevice", return_value=mock_dev), \
             patch("serial.tools.list_ports.comports", return_value=[]):
            result = controller.initialize_shimmer_emg()

        assert result is False
        assert controller.shimmer_emg_connected is False


# ══════════════════════════════════════════════════════════
#  3. 双设备端口互斥（核心）
# ══════════════════════════════════════════════════════════

class TestPortExclusion:

    def test_emg_excludes_gsr_port(self, controller):
        """GSR 占用 COM6 → EMG 候选中不含 COM6"""
        mock_gsr = _make_mock_gsr(["COM6", "COM7"], ["COM6"])
        with patch("devices.shimmer_gsr.ShimmerGSRDevice", return_value=mock_gsr):
            controller.initialize_shimmer()

        assert controller.shimmer_device._ser.port == "COM6"

        emg_tried = []
        mock_emg = _make_mock_emg(["COM7"])
        _orig = mock_emg.connect.side_effect

        def _track(port):
            emg_tried.append(port)
            return _orig(port)

        mock_emg.connect.side_effect = _track

        fake_ports = [FakeComPort("COM6"), FakeComPort("COM7")]
        with patch("devices.shimmer_emg.ShimmerEMGDevice", return_value=mock_emg), \
             patch("serial.tools.list_ports.comports", return_value=fake_ports):
            result = controller.initialize_shimmer_emg()

        assert result is True
        assert "COM6" not in emg_tried
        assert "COM7" in emg_tried

    def test_both_connect_different_ports(self, controller):
        """GSR → COM6, EMG → COM7, 两者均成功"""
        mock_gsr, mock_emg = _connect_both(controller)

        assert controller.shimmer_connected is True
        assert controller.shimmer_emg_connected is True
        assert controller.shimmer_device._ser.port == "COM6"
        assert controller.shimmer_emg_device._ser.port == "COM7"


# ══════════════════════════════════════════════════════════
#  4. 双设备并行数据流
# ══════════════════════════════════════════════════════════

class TestDualStreaming:

    def test_dual_streaming_start(self, controller):
        """两设备同时启动数据流，各自的 start_streaming 被调用"""
        mock_gsr, mock_emg = _connect_both(controller)

        controller._start_device_streams()

        mock_gsr.start_streaming.assert_called_once()
        mock_emg.start_streaming.assert_called_once()

    def test_dual_data_callbacks(self, controller):
        """两路回调独立计数"""
        _connect_both(controller)

        gsr_sample = {
            "timestamp": time.time(),
            "gsr_conductance": 0.5,
            "gsr_resistance": 200.0,
            "ppg": 2250.0,
            "accel_x": 0.0, "accel_y": 0.0, "accel_z": 1.0,
            "gyro_x": 0.0, "gyro_y": 0.0, "gyro_z": 0.0,
            "mag_x": 0.0, "mag_y": 0.0, "mag_z": 0.0,
            "temperature": 23.0, "pressure": 1013.0,
            "heart_rate": 72.0, "battery": 3.8,
        }
        for _ in range(3):
            controller._shimmer_data_callback(gsr_sample)

        emg_sample = {
            "timestamp": time.time(),
            "emg_ch1_mv": 0.12, "emg_ch2_mv": 0.08,
            "accel_x_ms2": 0.0, "accel_y_ms2": 0.0, "accel_z_ms2": 9.8,
            "gyro_x_dps": 0.0, "gyro_y_dps": 0.0, "gyro_z_dps": 0.0,
            "emg_status": 0,
        }
        for _ in range(2):
            controller._shimmer_emg_data_callback(emg_sample)

        assert controller.shimmer_packet_count == 3
        assert controller.shimmer_emg_packet_count == 2


# ══════════════════════════════════════════════════════════
#  5. 断开与清理
# ══════════════════════════════════════════════════════════

class TestDisconnect:

    def test_disconnect_gsr(self, controller):
        """断开 GSR → shimmer_connected 置 False"""
        mock_gsr, _ = _connect_both(controller)

        result = controller.disconnect_shimmer()

        assert result is True
        assert controller.shimmer_connected is False
        assert controller.shimmer_device is None
        mock_gsr.disconnect.assert_called_once()

    def test_disconnect_emg(self, controller):
        """断开 EMG → shimmer_emg_connected 置 False"""
        _, mock_emg = _connect_both(controller)

        result = controller.disconnect_shimmer_emg()

        assert result is True
        assert controller.shimmer_emg_connected is False
        assert controller.shimmer_emg_device is None
        mock_emg.disconnect.assert_called_once()

    def test_cleanup_both(self, controller):
        """cleanup() 一次清理所有设备"""
        mock_gsr, mock_emg = _connect_both(controller)

        controller.cleanup()

        assert controller.shimmer_connected is False
        assert controller.shimmer_emg_connected is False
        mock_gsr.disconnect.assert_called_once()
        mock_emg.disconnect.assert_called_once()


# ══════════════════════════════════════════════════════════
#  6. 边界 / 异常
# ══════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_emg_all_ports_fail(self, controller):
        """所有端口都连不上 → EMG 连接失败"""
        mock_dev = _make_mock_emg([])
        fake_ports = [FakeComPort("COM7"), FakeComPort("COM8")]

        with patch("devices.shimmer_emg.ShimmerEMGDevice", return_value=mock_dev), \
             patch("serial.tools.list_ports.comports", return_value=fake_ports):
            result = controller.initialize_shimmer_emg()

        assert result is False
        assert controller.shimmer_emg_connected is False
