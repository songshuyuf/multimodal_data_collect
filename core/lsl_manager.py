"""
LSL Stream Manager
管理Lab Streaming Layer的数据流输出
"""

import time
import numpy as np
from typing import List, Optional, Dict
import logging

try:
    from pylsl import StreamInfo, StreamOutlet, local_clock
    LSL_AVAILABLE = True
except ImportError:
    LSL_AVAILABLE = False
    logging.warning("pylsl not found. Please install: pip install pylsl")


class LSLStreamManager:
    """LSL数据流管理器"""
    
    def __init__(self, config: dict, channel_names: List[str], sampling_rate: float):
        """
        初始化LSL流管理器
        
        Args:
            config: LSL配置字典
            channel_names: 通道名称列表
            sampling_rate: 采样率
        """
        if not LSL_AVAILABLE:
            raise ImportError("pylsl not available. Install with: pip install pylsl")
        
        self.config = config
        self.channel_names = channel_names
        self.sampling_rate = sampling_rate
        self.outlet = None
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
        # 统计信息
        self.samples_pushed = 0
        self.start_time = None
        
    def create_outlet(self) -> bool:
        """
        创建LSL outlet
        
        Returns:
            bool: 是否成功创建outlet
        """
        try:
            # 创建StreamInfo对象
            stream_name = self.config.get('stream_name', 'ShimmerGSR')
            stream_type = self.config.get('stream_type', 'GSR')
            source_id = self.config.get('source_id', 'shimmer_gsr_001')
            
            n_channels = len(self.channel_names)
            
            self.logger.info(f"Creating LSL stream: {stream_name}")
            self.logger.info(f"Channels: {n_channels}, Sampling rate: {self.sampling_rate} Hz")
            
            # 创建stream info
            info = StreamInfo(
                name=stream_name,
                type=stream_type,
                channel_count=n_channels,
                nominal_srate=self.sampling_rate,
                channel_format='float32',
                source_id=source_id
            )
            
            # 添加元数据
            self._add_metadata(info)
            
            # 创建outlet
            self.outlet = StreamOutlet(info)
            self.start_time = time.time()
            
            self.logger.info(f"LSL outlet created successfully: {stream_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create LSL outlet: {e}")
            return False
    
    def _add_metadata(self, info: StreamInfo):
        """
        向StreamInfo添加元数据
        
        Args:
            info: StreamInfo对象
        """
        try:
            # 获取描述节点
            desc = info.desc()
            
            # 添加设备信息
            acquisition = desc.append_child("acquisition")
            acquisition.append_child_value("manufacturer", 
                                           self.config.get('manufacturer', 'Shimmer'))
            acquisition.append_child_value("model", 
                                          self.config.get('model', 'GSR+'))
            
            # 添加通道信息
            channels = desc.append_child("channels")
            
            # 从config导入通道类型和单位信息
            from config import SENSOR_CHANNELS
            
            for i, ch_name in enumerate(self.channel_names):
                channel = channels.append_child("channel")
                channel.append_child_value("label", ch_name)
                
                # 查找对应的单位和类型
                for sensor_type, sensor_info in SENSOR_CHANNELS.items():
                    if ch_name in sensor_info['names']:
                        idx = sensor_info['names'].index(ch_name)
                        channel.append_child_value("unit", sensor_info['units'][idx])
                        channel.append_child_value("type", sensor_info['types'][idx])
                        break
                else:
                    # 默认值
                    channel.append_child_value("unit", "unknown")
                    channel.append_child_value("type", "unknown")
            
            self.logger.info("Added metadata to LSL stream")
            
        except Exception as e:
            self.logger.warning(f"Failed to add metadata: {e}")
    
    def push_sample(self, sample: List[float], timestamp: Optional[float] = None):
        """
        推送单个样本到LSL流
        
        Args:
            sample: 样本数据列表
            timestamp: 可选的时间戳,如果为None则使用local_clock()
        """
        if self.outlet is None:
            self.logger.warning("Outlet not created. Call create_outlet() first.")
            return
        
        try:
            if timestamp is None:
                timestamp = local_clock()
            
            self.outlet.push_sample(sample, timestamp)
            self.samples_pushed += 1
            
        except Exception as e:
            self.logger.error(f"Error pushing sample: {e}")
    
    def push_chunk(self, samples: List[List[float]], timestamps: Optional[List[float]] = None):
        """
        推送多个样本到LSL流
        
        Args:
            samples: 样本数据列表的列表 [[ch1, ch2, ...], [ch1, ch2, ...], ...]
            timestamps: 可选的时间戳列表
        """
        if self.outlet is None:
            self.logger.warning("Outlet not created. Call create_outlet() first.")
            return
        
        try:
            if timestamps is None:
                # 生成时间戳
                timestamps = [local_clock() for _ in range(len(samples))]
            
            self.outlet.push_chunk(samples, timestamps)
            self.samples_pushed += len(samples)
            
        except Exception as e:
            self.logger.error(f"Error pushing chunk: {e}")
    
    def get_statistics(self) -> Dict:
        """
        获取流统计信息
        
        Returns:
            Dict: 统计信息字典
        """
        if self.start_time is None:
            return {}
        
        elapsed_time = time.time() - self.start_time
        effective_rate = self.samples_pushed / elapsed_time if elapsed_time > 0 else 0
        
        return {
            'samples_pushed': self.samples_pushed,
            'elapsed_time': elapsed_time,
            'effective_rate': effective_rate,
            'nominal_rate': self.sampling_rate,
            'rate_accuracy': (effective_rate / self.sampling_rate * 100) if self.sampling_rate > 0 else 0
        }
    
    def destroy_outlet(self):
        """销毁outlet"""
        if self.outlet is not None:
            stats = self.get_statistics()
            self.logger.info(f"Destroying LSL outlet. Statistics: {stats}")
            self.outlet = None
            self.samples_pushed = 0
            self.start_time = None
    
    def __del__(self):
        """析构函数"""
        self.destroy_outlet()


# 用于测试的独立脚本
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 导入配置
    import sys
    sys.path.append('..')
    from config import LSL_CONFIG
    
    # 测试LSL流
    print("=== Testing LSL Stream Manager ===\n")
    
    # 创建测试通道
    test_channels = ['GSR_Skin_Conductance', 'GSR_Skin_Resistance', 'PPG_A13']
    test_rate = 128.0
    
    # 创建LSL管理器
    lsl_manager = LSLStreamManager(LSL_CONFIG, test_channels, test_rate)
    
    # 创建outlet
    if lsl_manager.create_outlet():
        print("LSL outlet created successfully\n")
        print("You can now use LabRecorder or another LSL application to view this stream.\n")
        print("Streaming test data for 10 seconds...\n")
        
        try:
            start_time = time.time()
            sample_count = 0
            
            # 生成并推送测试数据
            while time.time() - start_time < 10:
                # 生成正弦波测试数据
                t = time.time() - start_time
                sample = [
                    np.sin(2 * np.pi * 1 * t) + 5,  # GSR conductance
                    np.cos(2 * np.pi * 1 * t) + 100,  # GSR resistance
                    np.sin(2 * np.pi * 2 * t) * 50 + 512  # PPG
                ]
                
                lsl_manager.push_sample(sample)
                sample_count += 1
                
                # 控制采样率
                time.sleep(1.0 / test_rate)
                
                # 每秒打印一次统计
                if sample_count % int(test_rate) == 0:
                    stats = lsl_manager.get_statistics()
                    print(f"Time: {t:.1f}s, Samples: {stats['samples_pushed']}, "
                          f"Rate: {stats['effective_rate']:.1f} Hz "
                          f"({stats['rate_accuracy']:.1f}% of nominal)")
        
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        
        # 显示最终统计
        print("\n=== Final Statistics ===")
        final_stats = lsl_manager.get_statistics()
        for key, value in final_stats.items():
            print(f"{key}: {value}")
        
        lsl_manager.destroy_outlet()
        print("\nLSL outlet destroyed")
    
    else:
        print("Failed to create LSL outlet")
