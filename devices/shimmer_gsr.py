"""
Shimmer GSR+ Device Handler
处理与Shimmer GSR+设备的蓝牙连接和数据采集
基于pyshimmer库实现
"""

import time
import serial
import serial.tools.list_ports
from typing import Optional, List, Dict, Tuple
import logging

try:
    from pyshimmer import ShimmerBluetooth, EChannelType, DataPacket

    SHIMMER_AVAILABLE = True
except ImportError as e:
    SHIMMER_AVAILABLE = False
    logging.warning(f"pyshimmer library not available: {e}")

    # 备用定义
    from typing import NamedTuple


    class DataPacket(NamedTuple):
        timestamp: float
        gsr: float = 0.0
        ppg: float = 0.0


    class ShimmerBluetooth:
        pass


    class EChannelType:
        TIMESTAMP = 0
        GSR_RAW = 1
        PPG_RAW = 2

import heartpy as hp


class HeartRateCalculator:
    """使用heartpy计算心率"""

    def __init__(self, sampling_rate=128.0, window_size=10):
        self.sampling_rate = sampling_rate
        self.window_size = window_size
        self.ppg_buffer = []
        self.last_hr = 0.0

    def add_sample(self, ppg_value):
        self.ppg_buffer.append(ppg_value)
        max_samples = int(self.sampling_rate * self.window_size)
        if len(self.ppg_buffer) > max_samples:
            self.ppg_buffer.pop(0)

    def calculate_heart_rate(self):
        if len(self.ppg_buffer) < self.sampling_rate * 4:
            return self.last_hr

        try:
            # 使用heartpy处理
            working_data, measures = hp.process(
                self.ppg_buffer,
                self.sampling_rate,
                report_time=False
            )
            self.last_hr = measures['bpm']
            return self.last_hr
        except:
            return self.last_hr


class ShimmerGSRDevice:
    """Shimmer GSR+设备管理类 (使用pyshimmer)"""

    def __init__(self, config: dict):
        """
        初始化Shimmer设备

        Args:
            config: 设备配置字典
        """
        if not SHIMMER_AVAILABLE:
            raise ImportError("pyshimmer library not available. Install with: pip install pyshimmer")

        self.config = config
        self.shimmer = None
        self.serial_obj = None
        self.is_connected = False
        self.is_streaming = False

        # 设置日志
        self.logger = logging.getLogger(__name__)

        # 通道名称
        self._channel_names = []

        # 数据缓冲队列
        self.data_buffer = []

        self.hr_calculator = HeartRateCalculator(
            sampling_rate=config.get('sampling_rate', 128.0)
        )

    def _list_com_ports(self) -> List[str]:
        """列出所有可用的COM端口"""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def connect(self, com_port: Optional[str] = None) -> bool:
        """
        连接到Shimmer设备

        Args:
            com_port: COM端口或蓝牙设备路径

        Returns:
            bool: 连接是否成功
        """
        if com_port is None:
            com_port = self.config.get('com_port')

        try:
            self.logger.info(f"Attempting to connect to Shimmer on {com_port}...")

            # 打开串口
            self.serial_obj = serial.Serial(
                com_port,
                baudrate=115200,
                timeout=None
            )
            time.sleep(0.2)

            if not self.serial_obj.is_open:
                self.logger.error(f"Failed to open serial port {com_port}")
                return False

            # 创建ShimmerBluetooth实例
            self.shimmer = ShimmerBluetooth(self.serial_obj)

            # 初始化设备
            self.logger.info("Initializing Shimmer device...")
            self.shimmer.initialize()

            self.is_connected = True
            self.logger.info(f"Successfully connected and initialized Shimmer on {com_port}")

            # 设置通道名称
            self._setup_channel_names()

            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to Shimmer: {e}")
            self.is_connected = False
            if self.serial_obj and self.serial_obj.is_open:
                self.serial_obj.close()
            return False

    def _setup_channel_names(self):
        """设置通道名称"""
        enabled_sensors = self.config.get('enabled_sensors', ['gsr', 'battery'])

        # 从配置导入传感器通道信息
        from devices.config import SENSOR_CHANNELS

        self._channel_names = []
        for sensor in enabled_sensors:
            if sensor in SENSOR_CHANNELS:
                self._channel_names.extend(SENSOR_CHANNELS[sensor]['names'])

        self.logger.info(f"Channel names: {self._channel_names}")

    def _stream_callback(self, packet):
        """数据流回调函数"""
        # 将数据包添加到缓冲区
        self.data_buffer.append(packet)

    def start_streaming(self) -> bool:
        """
        开始数据流传输

        Returns:
            bool: 是否成功开始流传输
        """
        if not self.is_connected:
            self.logger.error("Device not connected. Call connect() first.")
            return False

        try:
            self.logger.info("Starting data streaming...")

            # 清空缓冲区
            self.data_buffer = []

            # 注册回调函数
            self.shimmer.add_stream_callback(self._stream_callback)

            # 开始流传输
            self.shimmer.start_streaming()

            self.is_streaming = True
            self.logger.info("Data streaming started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start streaming: {e}")
            return False

    def stop_streaming(self) -> bool:
        """
        停止数据流传输

        Returns:
            bool: 是否成功停止流传输
        """
        if not self.is_streaming:
            return True

        try:
            # 移除回调
            self.shimmer.remove_stream_callback(self._stream_callback)

            # 停止流传输
            self.shimmer.stop_streaming()

            self.is_streaming = False
            self.logger.info("Stopped data streaming")
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop streaming: {e}")
            return False

    def read_data(self) -> Tuple[bool, Optional[DataPacket]]:
        """
        从缓冲区读取数据包

        Returns:
            Tuple[bool, Optional[DataPacket]]: (是否有数据, 数据包)
        """
        if not self.is_streaming:
            return False, None

        try:
            # 从缓冲区获取数据
            if len(self.data_buffer) > 0:
                packet = self.data_buffer.pop(0)
                return True, packet
            else:
                return False, None

        except Exception as e:
            self.logger.error(f"Error reading data: {e}")
            return False, None

    def extract_sample_from_packet(self, packet: DataPacket) -> Tuple[Optional[List[float]], float]:
        """
        从数据包中提取样本数据

        Args:
            packet: pyshimmer的DataPacket对象

        Returns:
            Tuple[Optional[List[float]], float]: (样本数据列表, 时间戳)
        """
        try:
            sample = []
            timestamp = time.time()

            if hasattr(packet, '_values'):
                values_dict = packet._values

                # 提取时间戳
                if EChannelType.TIMESTAMP in values_dict:
                    timestamp = float(values_dict[EChannelType.TIMESTAMP])

                enabled_sensors = self.config.get('enabled_sensors', ['gsr'])

                for sensor in enabled_sensors:
                    if sensor == 'gsr':
                        # GSR数据
                        if EChannelType.GSR_RAW in values_dict:
                            gsr_raw = float(values_dict[EChannelType.GSR_RAW])

                            # 计算电导和电阻
                            gsr_range = 8  # GSR+ 默认range
                            gsr_resistance = (gsr_raw / 4095.0) * (gsr_range * 1000.0)  # kOhm
                            gsr_conductance = 1000.0 / gsr_resistance if gsr_resistance > 0 else 0  # uS

                            sample.extend([gsr_conductance, gsr_resistance])
                        else:
                            sample.extend([0.0, 0.0])


                    elif sensor == 'ppg':

                        # PPG数据 - 使用INTERNAL_ADC_13

                        if EChannelType.INTERNAL_ADC_13 in values_dict:

                            ppg_value = float(values_dict[EChannelType.INTERNAL_ADC_13])

                            sample.append(ppg_value)

                            # 计算心率 (添加PPG样本到缓冲区)

                            self.hr_calculator.add_sample(ppg_value)

                        else:

                            sample.append(0.0)

                    elif sensor == 'accelerometer_ln':
                        # 加速度计
                        accel_x = float(values_dict.get(EChannelType.ACCEL_LN_X, 0.0))
                        accel_y = float(values_dict.get(EChannelType.ACCEL_LN_Y, 0.0))
                        accel_z = float(values_dict.get(EChannelType.ACCEL_LN_Z, 0.0))
                        sample.extend([accel_x, accel_y, accel_z])


                    elif sensor == 'gyroscope':

                        # 陀螺仪 - 直接检查是否存在

                        if EChannelType.GYRO_MPU9150_X in values_dict:

                            gyro_x = float(values_dict[EChannelType.GYRO_MPU9150_X])

                            gyro_y = float(values_dict[EChannelType.GYRO_MPU9150_Y])

                            gyro_z = float(values_dict[EChannelType.GYRO_MPU9150_Z])

                            sample.extend([gyro_x, gyro_y, gyro_z])

                        else:

                            sample.extend([0.0, 0.0, 0.0])


                    elif sensor == 'magnetometer':

                        # 磁力计

                        if EChannelType.MAG_LSM303DLHC_X in values_dict:

                            mag_x = float(values_dict[EChannelType.MAG_LSM303DLHC_X])

                            mag_y = float(values_dict[EChannelType.MAG_LSM303DLHC_Y])

                            mag_z = float(values_dict[EChannelType.MAG_LSM303DLHC_Z])

                            sample.extend([mag_x, mag_y, mag_z])

                        else:

                            sample.extend([0.0, 0.0, 0.0])


                    elif sensor == 'temperature':

                        # 温度

                        if EChannelType.TEMP_BMPX80 in values_dict:

                            temp = float(values_dict[EChannelType.TEMP_BMPX80])

                            sample.append(temp)

                        else:

                            sample.append(0.0)


                    elif sensor == 'pressure':

                        # 气压

                        if EChannelType.PRESSURE_BMPX80 in values_dict:

                            pressure = float(values_dict[EChannelType.PRESSURE_BMPX80])

                            sample.append(pressure)

                        else:

                            sample.append(0.0)

                    elif sensor == 'battery':
                        # 电池电压
                        if EChannelType.VBATT in values_dict:
                            sample.append(float(values_dict[EChannelType.VBATT]))
                        else:
                            sample.append(0.0)
                    elif sensor == 'accelerometer_wr':
                        # Wide-Range加速度计
                        if EChannelType.ACCEL_LSM303DLHC_X in values_dict:
                            accel_wr_x = float(values_dict[EChannelType.ACCEL_LSM303DLHC_X])
                            accel_wr_y = float(values_dict[EChannelType.ACCEL_LSM303DLHC_Y])
                            accel_wr_z = float(values_dict[EChannelType.ACCEL_LSM303DLHC_Z])
                            sample.extend([accel_wr_x, accel_wr_y, accel_wr_z])
                        else:
                            sample.extend([0.0, 0.0, 0.0])

                    elif sensor == 'external_adc':
                        # 外部ADC通道
                        if EChannelType.EXTERNAL_ADC_7 in values_dict:
                            ext_adc = float(values_dict[EChannelType.EXTERNAL_ADC_7])
                            sample.append(ext_adc)
                        else:
                            sample.append(0.0)



                    # 在最后添加心率通道
                    elif sensor == 'heart_rate':
                        # 计算心率
                        hr = self.hr_calculator.calculate_heart_rate()
                        sample.append(hr)  # 只添加心率,不要IBI

                # 在 return sample, timestamp 之前
                    # 在 return sample, timestamp 之前
                   # print(f"Sample length: {len(sample)}")
                  #  print(f"Expected channels: {len(self._channel_names)}")
                  #  print(f"Channels: {self._channel_names}")
                   # print(f"Sample: {sample}")

                return sample, timestamp

            else:
                self.logger.warning("Packet has no _values attribute")
                return None, timestamp

        except Exception as e:
            self.logger.error(f"Error extracting sample: {e}")
            import traceback
            traceback.print_exc()
            return None, time.time()

    def get_channel_names(self) -> List[str]:
        """
        获取当前启用的通道名称

        Returns:
            List[str]: 通道名称列表
        """
        return self._channel_names

    def disconnect(self):
        """断开与设备的连接"""
        try:
            if self.is_streaming:
                self.stop_streaming()

            if self.shimmer and hasattr(self.shimmer, 'shutdown'):
                self.shimmer.shutdown()
                self.logger.info("Shimmer device shutdown")

            if self.serial_obj and self.serial_obj.is_open:
                self.serial_obj.close()
                self.logger.info("Serial port closed")

            self.is_connected = False
            self.logger.info("Disconnected from Shimmer device")

        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")

    def __del__(self):
        """析构函数,确保断开连接"""
        try:
            self.disconnect()
        except:
            pass

    def get_device_info(self) -> Dict:
        """
        获取设备信息

        Returns:
            Dict: 设备信息字典
        """
        if not self.is_connected:
            return {}

        try:
            info = {
                'sampling_rate': self.config.get('sampling_rate', 128.0),
                'enabled_sensors': self.config.get('enabled_sensors'),
                'channel_names': self._channel_names,
                'com_port': self.config.get('com_port'),
            }
            return info
        except Exception as e:
            self.logger.error(f"Error getting device info: {e}")
            return {}


# 用于测试和调试的独立脚本
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 从配置文件导入
    from devices.config import SHIMMER_CONFIG

    # 列出可用端口
    print("\n=== Available COM Ports ===")
    ports = serial.tools.list_ports.comports()
    for p in ports:
        print(f"  - {p.device}: {p.description}")

    # 创建设备实例
    device = ShimmerGSRDevice(SHIMMER_CONFIG)

    # 测试连接
    print("\n=== Testing Connection ===")
    if device.connect():
        print("\n=== Device Info ===")
        info = device.get_device_info()
        for key, value in info.items():
            print(f"{key}: {value}")

        # 测试数据采集
        if device.start_streaming():
            print("\n=== Streaming Data (10 seconds) ===")
            start_time = time.time()
            packet_count = 0

            try:
                while time.time() - start_time < 10:
                    has_data, packet = device.read_data()

                    if has_data and packet:
                        sample, timestamp = device.extract_sample_from_packet(packet)
                        if sample:
                            packet_count += 1
                            if packet_count % 10 == 0:
                                print(f"Packet #{packet_count}: {sample[:3]}... (timestamp: {timestamp:.3f})")

                    time.sleep(0.01)

            except KeyboardInterrupt:
                print("\nInterrupted by user")

            print(f"\nTotal packets received: {packet_count}")
            device.stop_streaming()

        device.disconnect()
    else:
        print("Failed to connect to device")