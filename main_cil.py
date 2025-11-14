"""
Shimmer GSR+ LSL Integration - Main Application
主程序：整合设备连接、LSL流和数据保存
"""

import time
import logging
import sys
import signal
from typing import Optional
from datetime import datetime

# 导入自定义模块
from core.config import SHIMMER_CONFIG, LSL_CONFIG, DATA_SAVING_CONFIG, LOGGING_CONFIG
from core.shimmer_device import ShimmerGSRDevice
from core.lsl_manager import LSLStreamManager
from core.data_saver import DataSaver


class ShimmerLSLApp:
    """Shimmer LSL集成应用主类"""
    
    def __init__(self):
        """初始化应用"""
        # 设置日志
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # 初始化组件
        self.device = None
        self.lsl_manager = None
        self.data_saver = None
        
        # 运行状态
        self.is_running = False
        self.total_samples = 0
        
        # 注册信号处理器(用于Ctrl+C退出)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _setup_logging(self):
        """配置日志系统"""
        log_level = getattr(logging, LOGGING_CONFIG.get('level', 'INFO'))
        
        # 基本配置
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        handlers = []
        
        # 控制台输出
        if LOGGING_CONFIG.get('console_output', True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(console_handler)
        
        # 文件输出
        if LOGGING_CONFIG.get('log_to_file', True):
            import os
            log_dir = LOGGING_CONFIG.get('log_directory', './logs')
            os.makedirs(log_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(log_dir, f"shimmer_lsl_{timestamp}.log")
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)
        
        # 配置根日志
        logging.basicConfig(
            level=log_level,
            handlers=handlers
        )
    
    def _signal_handler(self, signum, frame):
        """处理Ctrl+C信号"""
        self.logger.info("\nReceived interrupt signal. Shutting down...")
        self.stop()
        sys.exit(0)
    
    def initialize(self, com_port: Optional[str] = None) -> bool:
        """
        初始化所有组件
        
        Args:
            com_port: 可选的COM端口
            
        Returns:
            bool: 是否成功初始化
        """
        try:
            self.logger.info("="*60)
            self.logger.info("Shimmer GSR+ LSL Integration")
            self.logger.info("="*60)
            
            # 1. 初始化Shimmer设备
            self.logger.info("\n[1/4] Initializing Shimmer GSR+ device...")
            self.device = ShimmerGSRDevice(SHIMMER_CONFIG)
            
            if not self.device.connect(com_port):
                self.logger.error("Failed to connect to Shimmer device")
                return False
            
            # 获取设备信息
            device_info = self.device.get_device_info()
            self.logger.info(f"Device info: {device_info}")
            
            # 获取通道信息
            channel_names = self.device.get_channel_names()
            sampling_rate = SHIMMER_CONFIG.get('sampling_rate', 128.0)
            
            self.logger.info(f"Channels: {channel_names}")
            self.logger.info(f"Sampling rate: {sampling_rate} Hz")
            
            # 2. 初始化LSL流
            self.logger.info("\n[2/4] Initializing LSL stream...")
            self.lsl_manager = LSLStreamManager(LSL_CONFIG, channel_names, sampling_rate)
            
            if not self.lsl_manager.create_outlet():
                self.logger.error("Failed to create LSL outlet")
                return False
            
            # 3. 初始化数据保存器
            self.logger.info("\n[3/4] Initializing data saver...")
            if DATA_SAVING_CONFIG.get('save_raw_data', True):
                full_config = {**DATA_SAVING_CONFIG, 'enabled_sensors': SHIMMER_CONFIG['enabled_sensors']}
                self.data_saver = DataSaver(full_config, channel_names, sampling_rate)
                
                session_name = f"shimmer_gsr_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                if not self.data_saver.start_saving(session_name):
                    self.logger.warning("Failed to start data saving (continuing without saving)")
                    self.data_saver = None
            else:
                self.logger.info("Data saving disabled in config")
                self.data_saver = None
            
            # 4. 开始数据流
            self.logger.info("\n[4/4] Starting data streaming...")
            if not self.device.start_streaming():
                self.logger.error("Failed to start streaming")
                return False
            
            self.logger.info("\n" + "="*60)
            self.logger.info("Initialization complete! Ready to stream data.")
            self.logger.info("="*60 + "\n")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False
    
    def run(self, duration: Optional[float] = None):
        """
        运行主数据采集循环
        
        Args:
            duration: 可选的运行时长(秒),None表示无限运行
        """
        if not self.device or not self.device.is_streaming:
            self.logger.error("Device not initialized or not streaming")
            return
        
        self.is_running = True
        start_time = time.time()
        last_stats_time = start_time
        stats_interval = 1.0  # 每秒打印一次统计
        
        self.logger.info("Starting data acquisition loop...")
        self.logger.info("Press Ctrl+C to stop\n")
        
        try:
            while self.is_running:
                # 检查运行时长
                if duration is not None and (time.time() - start_time) >= duration:
                    self.logger.info(f"Reached duration limit of {duration} seconds")
                    break
                
                # 读取数据
                has_data, packet = self.device.read_data()
                
                if has_data and packet:
                    # 提取数据和时间戳
                    sample, timestamp = self.device.extract_sample_from_packet(packet)
                    
                    if sample is not None:
                            # 推送到LSL
                            if self.lsl_manager:
                                self.lsl_manager.push_sample(sample, timestamp)
                            
                            # 保存数据
                            if self.data_saver:
                                self.data_saver.add_sample(sample, timestamp)
                            
                            self.total_samples += 1
                
                # 定期打印统计信息
                current_time = time.time()
                if current_time - last_stats_time >= stats_interval:
                    self._print_statistics()
                    last_stats_time = current_time
                
                # 短暂休眠,避免CPU占用过高
                time.sleep(0.001)
        
        except KeyboardInterrupt:
            self.logger.info("\nInterrupted by user")
        
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        
        finally:
            self.stop()
    
    def _print_statistics(self):
        """打印统计信息"""
        try:
            stats_lines = []
            stats_lines.append(f"\n{'='*60}")
            stats_lines.append(f"Total samples: {self.total_samples}")
            
            # LSL统计
            if self.lsl_manager:
                lsl_stats = self.lsl_manager.get_statistics()
                stats_lines.append(f"LSL pushed: {lsl_stats.get('samples_pushed', 0)}")
                stats_lines.append(f"LSL rate: {lsl_stats.get('effective_rate', 0):.2f} Hz "
                                 f"({lsl_stats.get('rate_accuracy', 0):.1f}% of nominal)")
            
            # 数据保存统计
            if self.data_saver:
                save_stats = self.data_saver.get_statistics()
                stats_lines.append(f"Saved: {save_stats.get('samples_saved', 0)}")
                stats_lines.append(f"Buffer: {save_stats.get('buffer_size', 0)}")
            
            stats_lines.append('='*60)
            
            # 打印所有统计行
            for line in stats_lines:
                self.logger.info(line)
            
        except Exception as e:
            self.logger.error(f"Error printing statistics: {e}")
    
    def stop(self):
        """停止所有组件"""
        self.is_running = False
        
        self.logger.info("\nStopping components...")
        
        # 停止设备流
        if self.device:
            self.device.stop_streaming()
            self.device.disconnect()
            self.logger.info("Device disconnected")
        
        # 停止数据保存
        if self.data_saver:
            self.data_saver.stop_saving()
            self.logger.info("Data saving stopped")
        
        # 销毁LSL流
        if self.lsl_manager:
            stats = self.lsl_manager.get_statistics()
            self.logger.info(f"Final LSL statistics: {stats}")
            self.lsl_manager.destroy_outlet()
            self.logger.info("LSL outlet destroyed")
        
        self.logger.info("\n" + "="*60)
        self.logger.info(f"Session ended. Total samples processed: {self.total_samples}")
        self.logger.info("="*60)


def main():
    """主函数"""
    import argparse
    
    # 命令行参数解析
    parser = argparse.ArgumentParser(
        description='Shimmer GSR+ LSL Integration Application'
    )
    parser.add_argument(
        '--port',
        type=str,
        default=None,
        help='COM port or Bluetooth device path (e.g., COM14 or /dev/rfcomm0)'
    )
    parser.add_argument(
        '--duration',
        type=float,
        default=None,
        help='Duration in seconds (default: run indefinitely)'
    )
    
    args = parser.parse_args()
    
    # 创建并运行应用
    app = ShimmerLSLApp()
    
    if app.initialize(com_port=args.port):
        app.run(duration=args.duration)
    else:
        print("Failed to initialize application")
        sys.exit(1)


if __name__ == "__main__":
    main()
