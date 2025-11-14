"""
LSL Receiver Test Script
用于测试和验证LSL流是否正常工作
可以在运行主程序后,用这个脚本接收数据验证同步
"""

import time
import sys
from pylsl import StreamInlet, resolve_stream
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    """主函数"""
    logger = logging.getLogger(__name__)
    
    print("="*60)
    print("LSL Stream Receiver Test")
    print("="*60)
    print("\nLooking for Shimmer GSR stream...")
    
    # 查找流
    try:
        # 可以通过name, type等来查找流
        # 这里查找所有GSR类型的流
        streams = resolve_stream('type', 'GSR')
        
        if not streams:
            print("\nNo GSR streams found!")
            print("Make sure the Shimmer LSL application is running.")
            return
        
        print(f"\nFound {len(streams)} GSR stream(s):")
        for i, stream in enumerate(streams):
            print(f"\n  Stream {i+1}:")
            print(f"    Name: {stream.name()}")
            print(f"    Type: {stream.type()}")
            print(f"    Channel count: {stream.channel_count()}")
            print(f"    Sampling rate: {stream.nominal_srate()} Hz")
            print(f"    Source ID: {stream.source_id()}")
        
        # 创建inlet连接到第一个流
        print("\nConnecting to the first stream...")
        inlet = StreamInlet(streams[0])
        
        # 获取流信息
        info = inlet.info()
        print(f"\nStream info:")
        print(f"  Name: {info.name()}")
        print(f"  Channels: {info.channel_count()}")
        print(f"  Sampling rate: {info.nominal_srate()} Hz")
        
        # 尝试获取通道信息
        print("\nChannel details:")
        channels = info.desc().child("channels")
        if channels.empty():
            print("  No channel metadata available")
        else:
            ch = channels.child("channel")
            i = 1
            while not ch.empty():
                label = ch.child_value("label")
                unit = ch.child_value("unit")
                ch_type = ch.child_value("type")
                print(f"  {i}. {label} ({unit}) - Type: {ch_type}")
                ch = ch.next_sibling()
                i += 1
        
        print("\n" + "="*60)
        print("Receiving data... (Press Ctrl+C to stop)")
        print("="*60 + "\n")
        
        # 接收数据
        sample_count = 0
        start_time = time.time()
        last_print_time = start_time
        
        try:
            while True:
                # 拉取样本(超时1秒)
                sample, timestamp = inlet.pull_sample(timeout=1.0)
                
                if sample:
                    sample_count += 1
                    
                    # 每秒打印一次统计和示例数据
                    current_time = time.time()
                    if current_time - last_print_time >= 1.0:
                        elapsed = current_time - start_time
                        rate = sample_count / elapsed if elapsed > 0 else 0
                        
                        print(f"Time: {elapsed:.1f}s | Samples: {sample_count} | "
                              f"Rate: {rate:.1f} Hz")
                        print(f"  Latest sample: {[f'{x:.2f}' for x in sample]}")
                        print(f"  Timestamp: {timestamp:.6f}\n")
                        
                        last_print_time = current_time
        
        except KeyboardInterrupt:
            print("\n\nStopped by user")
        
        # 打印最终统计
        elapsed = time.time() - start_time
        rate = sample_count / elapsed if elapsed > 0 else 0
        
        print("\n" + "="*60)
        print("Final Statistics:")
        print(f"  Total samples received: {sample_count}")
        print(f"  Duration: {elapsed:.2f} seconds")
        print(f"  Average rate: {rate:.2f} Hz")
        print("="*60)
    
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
