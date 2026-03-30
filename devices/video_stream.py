"""
视频采集LSL流
使用摄像头采集视频并通过LSL推送帧信息
"""

import cv2
import time
import numpy as np
from pylsl import StreamInfo, StreamOutlet, local_clock
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class VideoLSLStream:
    """视频LSL流"""

    def __init__(self, camera_id=0, fps=30, resolution=(640, 480)):
        """
        初始化视频流

        Args:
            camera_id: 摄像头ID (0=默认摄像头)
            fps: 帧率
            resolution: 分辨率 (width, height)
        """
        self.camera_id = camera_id
        self.fps = fps
        self.resolution = resolution
        self.cap = None
        self.outlet = None
        self.is_streaming = False

    def start(self):
        """启动视频采集和LSL流（带重试）"""
        import sys as _sys

        backends = [cv2.CAP_ANY]
        if _sys.platform == "win32":
            backends.append(cv2.CAP_DSHOW)

        MAX_RETRIES = 5
        RETRY_DELAY = 1.0

        opened = False
        for attempt in range(1, MAX_RETRIES + 1):
            for backend in backends:
                cap = cv2.VideoCapture(self.camera_id, backend)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        self.cap = cap
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                        logging.info(
                            f"摄像头已打开 (camera_id={self.camera_id}, "
                            f"backend={backend}, attempt={attempt})"
                        )
                        opened = True
                        break
                    cap.release()
                else:
                    cap.release()
            if opened:
                break
            logging.warning(f"摄像头打开失败，第 {attempt}/{MAX_RETRIES} 次重试...")
            time.sleep(RETRY_DELAY)

        if not opened:
            logging.error(f"摄像头 {self.camera_id} 重试 {MAX_RETRIES} 次后仍无法打开")
            return False

        # 创建LSL流 (只推送元数据,不推送图像数据)
        info = StreamInfo(
            name='VideoStream',
            type='VideoMarkers',
            channel_count=4,  # timestamp, frame_number, width, height
            nominal_srate=self.fps,
            channel_format='float32',
            source_id='webcam_001'
        )

        # 添加元数据
        desc = info.desc()
        desc.append_child_value("camera_id", str(self.camera_id))
        desc.append_child_value("resolution", f"{self.resolution[0]}x{self.resolution[1]}")
        desc.append_child_value("fps", str(self.fps))

        self.outlet = StreamOutlet(info)
        self.is_streaming = True

        logging.info(f"视频LSL流已启动: {self.resolution[0]}x{self.resolution[1]} @ {self.fps}fps")
        return True

    def run(self, duration=None, save_video=False, output_path="video_output.mp4"):
        """
        运行视频采集

        Args:
            duration: 持续时间(秒),None=无限
            save_video: 是否保存视频文件
            output_path: 视频保存路径
        """
        if not self.is_streaming:
            logging.error("请先调用start()启动流")
            return

        # 视频写入器
        writer = None
        if save_video:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(output_path, fourcc, self.fps, self.resolution)

        start_time = time.time()
        frame_count = 0

        try:
            while self.is_streaming:
                ret, frame = self.cap.read()
                if not ret:
                    logging.warning("无法读取帧")
                    break

                # 获取时间戳
                timestamp = local_clock()

                # 推送元数据到LSL
                sample = [
                    timestamp,
                    float(frame_count),
                    float(frame.shape[1]),  # width
                    float(frame.shape[0])  # height
                ]
                self.outlet.push_sample(sample, timestamp)

                # 保存视频
                if save_video and writer:
                    writer.write(frame)

                # 显示视频
                cv2.imshow('Video Stream (Press Q to quit)', frame)

                frame_count += 1

                # 控制帧率
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

                # 检查持续时间
                if duration and (time.time() - start_time) >= duration:
                    break

        except KeyboardInterrupt:
            logging.info("用户中断")

        finally:
            if writer:
                writer.release()
            cv2.destroyAllWindows()
            logging.info(f"采集完成,共 {frame_count} 帧")

    def stop(self):
        """停止采集"""
        self.is_streaming = False
        if self.cap:
            self.cap.release()
            self.cap = None
        logging.info("视频流已停止")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='视频LSL流采集')
    parser.add_argument('--camera', type=int, default=0, help='摄像头ID')
    parser.add_argument('--fps', type=int, default=30, help='帧率')
    parser.add_argument('--width', type=int, default=640, help='宽度')
    parser.add_argument('--height', type=int, default=480, help='高度')
    parser.add_argument('--duration', type=float, default=None, help='持续时间(秒)')
    parser.add_argument('--save', action='store_true', help='保存视频文件')
    parser.add_argument('--output', type=str, default='video_output.mp4', help='输出文件名')

    args = parser.parse_args()

    video_stream = VideoLSLStream(
        camera_id=args.camera,
        fps=args.fps,
        resolution=(args.width, args.height)
    )

    if video_stream.start():
        video_stream.run(
            duration=args.duration,
            save_video=args.save,
            output_path=args.output
        )
        video_stream.stop()