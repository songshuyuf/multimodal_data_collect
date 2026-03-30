"""
VR ADB 控制器 ── 通过 ADB 控制 PICO 4 播放本地视频
====================================================
方案：
  · 视频在 PICO 本地（/sdcard/Movies/ScreenRecording/）
  · PC 通过 Wi-Fi ADB 向 PICO 发送播放/停止命令
  · 不需要浏览器，不需要额外 App

用法：
  from devices.vr_sync import VRADBController

  vr = VRADBController(pico_ip="172.20.10.6")
  vr.connect()
  vr.play_all()      # 依次播放目录内所有视频
  vr.stop()          # 提前停止
  vr.disconnect()
"""

import logging
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# 项目根目录（相对路径基准）
_ROOT = Path(__file__).parent.parent

# ADB 可执行文件：优先用项目内的，其次用系统 PATH
_ADB_LOCAL = _ROOT / "vr" / "platform-tools" / ("adb.exe" if sys.platform == "win32" else "adb")
_ADB_CMD = str(_ADB_LOCAL) if _ADB_LOCAL.exists() else "adb"

# 默认配置
DEFAULT_PORT         = 5555
DEFAULT_PICO_DIR     = "/sdcard/Movies/ScreenRecording"  # PICO 上的视频目录
VIDEO_EXTENSIONS     = (".mp4", ".mkv", ".avi", ".mov", ".wmv")

# PICO 4 360° VR 播放器
PICO_PLAYER_PACKAGE  = "cn.vr4p.pico4xvrplayer"
PICO_PLAYER_ACTIVITY = "cn.vr4p.pico4xvrplayer/.V4FileLoadActivity"


class VRADBController:
    """
    通过 ADB 控制 PICO 4 播放本地视频。
    支持两种连接模式：
      - USB 模式：pico_serial 指定设备序列号（如 PA8210MGH3300381G），更稳定
      - WiFi 模式：pico_ip 指定 IP（如 192.168.1.88），需提前 tcpip 5555

    参数：
        pico_ip       : PICO 的局域网 IP（WiFi 模式）
        pico_port     : ADB 端口，默认 5555
        pico_serial   : PICO USB 序列号（USB 模式，优先于 IP）
        pico_video_dir: PICO 上的视频目录
        adb_cmd       : adb 可执行文件路径（默认自动查找）
    """

    def __init__(
        self,
        pico_ip: str = "",
        pico_port: int = DEFAULT_PORT,
        pico_serial: str = "",
        pico_video_dir: str = DEFAULT_PICO_DIR,
        adb_cmd: str = _ADB_CMD,
    ):
        self.pico_ip        = pico_ip
        self.pico_port      = pico_port
        self.pico_serial    = pico_serial
        self.pico_video_dir = pico_video_dir
        self.adb_cmd        = adb_cmd
        # USB 模式用序列号，WiFi 模式用 IP:port
        self._target        = pico_serial if pico_serial else f"{pico_ip}:{pico_port}"
        self._connected     = False
        self._stop_flag     = False

    # ── 内部工具 ──────────────────────────────────────────

    def _run(self, *args, timeout: int = 10) -> tuple[int, str, str]:
        """执行 adb 命令，返回 (returncode, stdout, stderr)"""
        cmd = [self.adb_cmd] + list(args)
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, encoding="utf-8", errors="replace"
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "命令超时"
        except FileNotFoundError:
            return -1, "", f"找不到 adb：{self.adb_cmd}"

    def _shell(self, shell_cmd: str, timeout: int = 10) -> tuple[int, str]:
        """adb -s TARGET shell <cmd>"""
        code, out, err = self._run("-s", self._target, "shell", shell_cmd, timeout=timeout)
        return code, out or err

    # ── 连接 ──────────────────────────────────────────────

    def connect(self, retries: int = 3) -> bool:
        """连接 PICO，自动重试。USB 模式直接检测，WiFi 模式执行 connect"""
        self._run("start-server", timeout=10)

        # USB 模式：直接检查设备是否在线
        if self.pico_serial:
            code, out, err = self._run("devices", timeout=5)
            if self.pico_serial in out and "offline" not in out.split(self.pico_serial)[-1][:10]:
                self._connected = True
                self._target = self.pico_serial
                logger.info("[VR] USB 已连接：%s", self.pico_serial)
                return True
            logger.error("[VR] USB 设备未找到，请检查 USB 连接：%s", self.pico_serial)
            return False

        # 无显式 serial/IP 时，尝试自动检测已连接的设备
        if not self.pico_ip:
            code, out, err = self._run("devices", timeout=5)
            for line in out.splitlines():
                line = line.strip()
                if "\tdevice" in line and "List" not in line:
                    detected = line.split("\t")[0].strip()
                    if detected:
                        self._target = detected
                        self._connected = True
                        logger.info("[VR] 自动检测到设备：%s", detected)
                        return True
            logger.info("[VR] 未检测到已连接设备，等待…")
            return False

        # WiFi 模式：执行 adb connect
        for i in range(retries):
            logger.info("[VR] WiFi 连接 %s（第 %d 次）...", self._target, i + 1)
            code, out, err = self._run("connect", self._target, timeout=15)
            msg = (out + err).strip()
            if "connected" in msg or "already connected" in msg:
                self._connected = True
                logger.info("[VR] 已连接：%s", msg)
                return True
            if "offline" in msg or not msg:
                self._run("disconnect", self._target, timeout=5)
                time.sleep(1)
            logger.warning("[VR] 第 %d 次失败：%s", i + 1, msg or "无响应")
            time.sleep(2)
        logger.error("[VR] 连接失败，请确认 PICO 已唤醒且在同一网络")
        return False

    def ensure_connected(self) -> bool:
        """检查连接状态，断线则自动唤醒重连"""
        code, out, err = self._run("devices", timeout=5)
        if self._target in out and "offline" not in out:
            return True
        logger.warning("[VR] 设备离线，尝试重连...")
        # 尝试唤醒（即使 offline 有时也能收到）
        self._run("-s", self._target, "shell", "input keyevent KEYCODE_WAKEUP", timeout=3)
        time.sleep(1)
        return self.connect(retries=2)

    def disconnect(self):
        """断开 ADB 连接"""
        self._run("disconnect", self._target)
        self._connected = False
        logger.info("[VR] 已断开连接")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── 视频控制 ──────────────────────────────────────────

    def _play_file(self, video_path: str) -> bool:
        """用系统默认 360° VR 播放器打开视频文件"""
        # 不指定包名，由系统默认播放器处理（用户手动设置的默认 App）
        intent = (
            f"am start -a android.intent.action.VIEW "
            f"-d 'file://{video_path}' "
            f"-t 'video/mp4'"
        )
        code, out = self._shell(intent)
        ok = code == 0 or "Starting" in out
        if ok:
            logger.info("[VR] 播放：%s", video_path)
        else:
            logger.error("[VR] 启动失败：%s", out)
        return ok

    def play_all(self, interval: float = 30.0) -> bool:
        """
        依次播放目录内所有视频文件，按文件名排序。
        interval: 每个视频播放秒数（默认 30 秒），到时自动切换下一个。
        播放过程中调用 stop() 可中断。
        """
        if not self.ensure_connected():
            logger.warning("[VR] 无法连接，无法播放")
            return False

        videos = self.list_videos_on_pico()
        if not videos:
            logger.error("[VR] 目录内没有视频：%s", self.pico_video_dir)
            return False

        self._stop_flag = False
        logger.info("[VR] 共 %d 个视频，开始依次播放...", len(videos))

        for i, filename in enumerate(videos):
            if self._stop_flag:
                logger.info("[VR] 已中断")
                break
            path = f"{self.pico_video_dir}/{filename}"
            print(f"  [{i+1}/{len(videos)}] 播放: {filename}（等待 {interval:.0f}s）")
            self._play_file(path)
            # 等待当前视频播放完（interval 秒），期间可被 stop() 中断
            for _ in range(int(interval)):
                if self._stop_flag:
                    break
                time.sleep(1)

        return True

    def play(self, filename: str = None) -> bool:
        """
        播放单个视频。
        filename: 文件名（如 hangyi.mp4），不传则播目录第一个。
        """
        if not self.ensure_connected():
            logger.warning("[VR] 无法连接，无法播放")
            return False

        if filename is None:
            videos = self.list_videos_on_pico()
            if not videos:
                logger.error("[VR] 目录内没有视频：%s", self.pico_video_dir)
                return False
            filename = videos[0]

        path = f"{self.pico_video_dir}/{filename}"
        return self._play_file(path)

    def pause(self) -> bool:
        """发送媒体暂停键"""
        if not self._connected:
            return False
        self._shell("input keyevent KEYCODE_MEDIA_PAUSE")
        logger.info("[VR] 已暂停")
        return True

    def resume(self) -> bool:
        """从暂停恢复播放"""
        if not self._connected:
            return False
        self._shell("input keyevent KEYCODE_MEDIA_PLAY")
        logger.info("[VR] 已恢复播放")
        return True

    def stop(self) -> bool:
        """停止视频并退出播放器"""
        self._stop_flag = True
        if not self._connected:
            return False
        self._shell("input keyevent KEYCODE_MEDIA_STOP")
        time.sleep(0.3)
        self._shell(f"am force-stop {PICO_PLAYER_PACKAGE}")
        logger.info("[VR] 视频已停止")
        return True

    # ── 辅助信息 ──────────────────────────────────────────

    def list_videos_on_pico(self) -> list:
        """列出 PICO 视频目录内的所有视频文件，按文件名排序"""
        _, out = self._shell(f"ls {self.pico_video_dir}/")
        files = [
            f.strip() for f in out.splitlines()
            if f.strip().lower().endswith(VIDEO_EXTENSIONS)
        ]
        return sorted(files)

    def get_pico_ip(self) -> str:
        return self.pico_ip
