"""
Data Saver Module
负责将采集的生理信号数据保存到本地文件
"""

import os
import csv
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import logging
import numpy as np
from datetime import datetime

class DataSaver:
    """数据保存器类"""
    
    def __init__(self, config: dict, channel_names: List[str], sampling_rate: float):
        """
        初始化数据保存器
        
        Args:
            config: 数据保存配置
            channel_names: 通道名称列表
            sampling_rate: 采样率
        """
        self.config = config
        self.channel_names = channel_names
        self.sampling_rate = sampling_rate
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
        # 数据缓冲区
        self.data_buffer = []
        self.timestamp_buffer = []
        self.buffer_size = config.get('buffer_size', 1000)
        
        # 文件路径
        self.output_dir = config.get('output_directory', './data')
        self.file_format = config.get('file_format', 'csv')
        self.file_path = None
        self.metadata_path = None
        
        # 统计信息
        self.samples_saved = 0
        self.start_time = None
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        device_id = config.get('device_id', 'A5E0')

        # CSV文件路径
        if self.file_format in ['csv', 'both']:
            filename = f'shimmer_gsr_{timestamp}.csv'
            self.file_path = os.path.join(self.output_dir, filename)
            self._create_csv_file()

        # 元数据文件路径
        metadata_filename = f'shimmer_gsr_{timestamp}_metadata.json'
        self.metadata_path = os.path.join(self.output_dir, metadata_filename)
        self._save_metadata()

        self.logger.info(f"DataSaver初始化完成,文件: {self.file_path}")

        # EEG设备
        self.heeg_file = None
        self.heeg_writer = None
        self.heeg_header_written = False

    def _init_heeg_csv(self, timestamp: str):
        """初始化HEEG数据CSV文件"""
        try:
            filepath = os.path.join(self.output_dir, f'heeg_{timestamp}.csv')

            self.heeg_file = open(filepath, 'w', newline='')
            self.heeg_writer = csv.writer(self.heeg_file)

            # 临时表头，会在第一次写入时更新
            header = ['system_time', 'device_time', 'sample_index']
            self.heeg_writer.writerow(header)
            self.heeg_header_written = False

            self.logger.info(f"✅ HEEG CSV文件已创建: {filepath}")

        except Exception as e:
            self.logger.error(f"❌ 创建HEEG CSV文件失败: {e}")

    def _write_heeg_header(self, channel_count: int):
        """写入HEEG CSV的完整表头"""
        # 回到文件开头
        self.heeg_file.seek(0)

        # 构建表头
        header = ['system_time', 'device_time', 'sample_index']

        # 添加通道名
        for i in range(channel_count):
            header.append(f'ch_{i + 1}')

        # 添加trigger列
        header.append('trigger')

        # 写入表头
        self.heeg_writer.writerow(header)

        self.logger.info(f"✅ HEEG表头已写入: {channel_count}通道")

    def save_heeg_data(self, data: Dict, system_timestamp: float,
                       device_timestamp: Optional[float] = None):
        """
        保存HEEG数据

        Args:
            data: HEEG数据字典
                - timeStamp: 设备时间戳(ms)
                - channelCount: 通道数
                - sampleRate: 采样率
                - dataCountPerChannel: 每通道样本数
                - datas: 数据数组, shape=(channels, samples)
                - trigger: trigger值（可选）
            system_timestamp: 系统时间戳
            device_timestamp: 设备时间戳（可选）
        """
        if not self.heeg_writer:
            return

        try:
            channel_count = data['channelCount']
            sample_count = data['dataCountPerChannel']
            datas = data['datas']  # shape: (channels, samples)
            device_time = device_timestamp if device_timestamp else data['timeStamp'] / 1000.0
            trigger = data.get('trigger', None)

            # 第一次写入时，更新表头
            if not self.heeg_header_written:
                self._write_heeg_header(channel_count)
                self.heeg_header_written = True

            # 写入每个样本点（每行一个样本）
            for sample_idx in range(sample_count):
                row = [
                    f"{system_timestamp:.6f}",
                    f"{device_time:.6f}",
                    sample_idx,
                ]

                # 添加所有通道的数据
                for ch_idx in range(channel_count):
                    row.append(f"{datas[ch_idx, sample_idx]:.6f}")

                # 添加trigger
                row.append(trigger if trigger else "")

                self.heeg_writer.writerow(row)

        except Exception as e:
            self.logger.error(f"保存HEEG数据失败: {e}", exc_info=True)


    def start_saving(self, session_name: Optional[str] = None) -> bool:
        """
        开始数据保存会话
        
        Args:
            session_name: 可选的会话名称
            
        Returns:
            bool: 是否成功开始保存
        """
        try:
            # 生成文件名
            if session_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                session_name = f"shimmer_gsr_{timestamp}"
            
            # 设置文件路径
            if self.file_format in ['csv', 'both']:
                self.file_path = os.path.join(self.output_dir, f"{session_name}.csv")
                self._create_csv_file()
            
            if self.file_format in ['hdf5', 'both']:
                # HDF5支持(如果需要)
                self.logger.warning("HDF5 format not yet implemented")
            
            # 保存元数据
            self.metadata_path = os.path.join(self.output_dir, f"{session_name}_metadata.json")
            self._save_metadata()
            
            self.start_time = time.time()
            self.logger.info(f"Started saving data to: {self.file_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start saving: {e}")
            return False

    def _create_csv_file(self):
        """创建CSV文件并写入表头(带单位)"""
        try:
            device_id = self.config.get('device_id', 'A5E0')

            from devices.config import SENSOR_CHANNELS

            # 创建通道名到单位的映射
            channel_to_unit = {}
            for sensor, info in SENSOR_CHANNELS.items():
                for i, ch_name in enumerate(info['names']):
                    channel_to_unit[ch_name] = info['units'][i]

            with open(self.file_path, 'w', newline='') as f:
                writer = csv.writer(f)

                header = []

                # 时间戳
                timestamp_col = f"Shimmer_{device_id}_Timestamp_Unix_CAL"
                header.append(timestamp_col)

                # 其他通道(带单位)
                for ch_name in self.channel_names:
                    unit = channel_to_unit.get(ch_name, '')  # 获取单位,没有则为空
                    if unit:
                        column_name = f"Shimmer_{device_id}_{ch_name}_CAL_{unit}"
                    else:
                        column_name = f"Shimmer_{device_id}_{ch_name}_CAL"
                    header.append(column_name)

                writer.writerow(header)

            self.logger.info(f"Created CSV file: {self.file_path}")

        except Exception as e:
            self.logger.error(f"Failed to create CSV file: {e}")
            raise
    
    def _save_metadata(self):
        """保存会话元数据"""
        try:
            metadata = {
                'session_info': {
                    'start_time': datetime.now().isoformat(),
                    'sampling_rate': self.sampling_rate,
                    'channel_count': len(self.channel_names),
                },
                'channels': self.channel_names,
                'device_info': {
                    'manufacturer': 'Shimmer',
                    'model': 'GSR+',
                },
                'file_info': {
                    'format': self.file_format,
                    'data_file': os.path.basename(self.file_path) if self.file_path else None,
                }
            }
            
            with open(self.metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"Saved metadata to: {self.metadata_path}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save metadata: {e}")
    
    def add_sample(self, sample: List[float], timestamp: float):
        """
        添加样本到缓冲区
        
        Args:
            sample: 样本数据
            timestamp: 时间戳
        """
        self.data_buffer.append(sample)
        self.timestamp_buffer.append(timestamp)
        
        # 当缓冲区达到指定大小时写入文件
        if len(self.data_buffer) >= self.buffer_size:
            self._flush_buffer()
    
    def add_chunk(self, samples: List[List[float]], timestamps: List[float]):
        """
        添加多个样本到缓冲区
        
        Args:
            samples: 样本数据列表
            timestamps: 时间戳列表
        """
        self.data_buffer.extend(samples)
        self.timestamp_buffer.extend(timestamps)
        
        # 当缓冲区达到指定大小时写入文件
        if len(self.data_buffer) >= self.buffer_size:
            self._flush_buffer()
    
    def _flush_buffer(self):
        """将缓冲区数据写入文件"""
        if not self.data_buffer:
            return
        
        try:
            if self.file_format in ['csv', 'both']:
                self._write_csv_buffer()
            
            # 更新统计
            self.samples_saved += len(self.data_buffer)
            
            # 清空缓冲区
            self.data_buffer = []
            self.timestamp_buffer = []
            
        except Exception as e:
            self.logger.error(f"Error flushing buffer: {e}")

    def _write_csv_buffer(self):
        """将缓冲区写入CSV文件"""
        try:
            with open(self.file_path, 'a', newline='') as f:
                writer = csv.writer(f)

                for i in range(len(self.data_buffer)):
                    timestamp = self.timestamp_buffer[i]

                    # 转换为毫秒级Unix时间戳
                    timestamp_ms = int(timestamp * 1000)

                    # 写入数据行
                    row = [timestamp_ms] + self.data_buffer[i]
                    writer.writerow(row)

        except Exception as e:
            self.logger.error(f"Error writing to CSV: {e}")
            raise
    
    def stop_saving(self):
        """停止保存并刷新所有缓冲数据"""
        # 刷新剩余数据
        if self.data_buffer:
            self._flush_buffer()
        
        # 更新元数据
        if self.metadata_path and os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                metadata['session_info']['end_time'] = datetime.now().isoformat()
                metadata['session_info']['samples_saved'] = self.samples_saved
                
                if self.start_time:
                    duration = time.time() - self.start_time
                    metadata['session_info']['duration_seconds'] = duration
                    metadata['session_info']['effective_rate'] = self.samples_saved / duration if duration > 0 else 0
                
                with open(self.metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
            except Exception as e:
                self.logger.warning(f"Failed to update metadata: {e}")
        
        self.logger.info(f"Stopped saving. Total samples saved: {self.samples_saved}")

        if self.heeg_file:
            try:
                self.heeg_file.close()
                self.logger.info("✅ HEEG文件已关闭")
            except Exception as e:
                self.logger.error(f"关闭HEEG文件失败: {e}")

    def get_statistics(self) -> Dict:
        """
        获取保存统计信息
        
        Returns:
            Dict: 统计信息字典
        """
        stats = {
            'samples_saved': self.samples_saved,
            'buffer_size': len(self.data_buffer),
            'file_path': self.file_path,
        }
        
        if self.start_time:
            elapsed = time.time() - self.start_time
            stats['elapsed_time'] = elapsed
            stats['effective_rate'] = self.samples_saved / elapsed if elapsed > 0 else 0
        
        return stats


# 测试代码
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 导入配置
    from devices.config import DATA_SAVING_CONFIG
    
    print("=== Testing Data Saver ===\n")
    
    # 创建测试通道
    test_channels = ['GSR_Conductance', 'GSR_Resistance', 'PPG']
    test_rate = 128.0
    
    # 创建数据保存器
    saver = DataSaver(DATA_SAVING_CONFIG, test_channels, test_rate)
    
    # 开始保存
    if saver.start_saving("test_session"):
        print("Started data saving\n")
        
        # 生成并保存测试数据
        print("Generating test data for 5 seconds...\n")
        
        start_time = time.time()
        sample_count = 0
        
        try:
            while time.time() - start_time < 5:
                # 生成测试数据
                t = time.time()
                sample = [
                    np.sin(2 * np.pi * 1 * (t - start_time)) + 5,
                    np.cos(2 * np.pi * 1 * (t - start_time)) + 100,
                    np.sin(2 * np.pi * 2 * (t - start_time)) * 50 + 512
                ]
                
                saver.add_sample(sample, t)
                sample_count += 1
                
                # 控制采样率
                time.sleep(1.0 / test_rate)
                
                # 每秒打印统计
                if sample_count % int(test_rate) == 0:
                    stats = saver.get_statistics()
                    print(f"Saved: {stats['samples_saved']} samples, "
                          f"Buffer: {stats['buffer_size']} samples")
        
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        
        # 停止保存
        saver.stop_saving()
        
        # 显示最终统计
        print("\n=== Final Statistics ===")
        final_stats = saver.get_statistics()
        for key, value in final_stats.items():
            print(f"{key}: {value}")
        
        print(f"\nData saved to: {final_stats['file_path']}")
    
    else:
        print("Failed to start data saving")
