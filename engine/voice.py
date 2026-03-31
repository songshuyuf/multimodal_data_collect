"""
AI 语音引导模块
使用 edge-tts 生成中文语音，通过 Qt 信号在主线程播放
依赖：edge-tts（pip install edge-tts）
未安装时静默降级，不影响系统运行
"""

import asyncio
import logging
import os
import sys
import tempfile
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# 检查 edge-tts 是否可用（兼容 Python 3.8 — aiohttp 版本差异可能抛 TypeError）
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False
    logger.warning("edge-tts 不可用（可能因 Python/aiohttp 版本不兼容），语音引导已禁用")

try:
    from PyQt5.QtCore import QObject, pyqtSignal
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


# ── 实验各阶段的语音提示文本 ──────────────────────────────────

VOICE_SCRIPTS = {
    # 任务开始前引导语
    "rest_start":
        "您好，接下来请您保持放松，自然呼吸。"
        "我们将交替进行睁眼和闭眼的静息测量，请按屏幕提示操作。",

    "dotprobe_start":
        "下面进行注意力图片任务。"
        "屏幕会先出现一个加号注视点，然后左右各出现一张图片。"
        "图片消失后，屏幕某一侧会出现一个圆点。"
        "圆点在左边，请按左方向键；圆点在右边，请按右方向键。"
        "请尽量又快又准。接下来先进行几次练习，熟悉节奏。",

    "dotprobe_practice_done":
        "练习已完成。即将开始正式实验，请集中注意力。",

    "dotprobe_main_start":
        "练习结束，正式实验现在开始，请集中注意力。",

    "dotprobe_end":
        "注意力图片任务已完成，请稍作休息。",

    "painting_start":
        "接下来您将欣赏一系列绘画作品。"
        "请放松心情，自然感受每一幅画带给您的感觉。"
        "整个过程约需四分钟，无需进行任何按键操作，"
        "只需专注欣赏即可。",

    "painting_running":
        "实验开始，请放松欣赏。",

    "painting_end":
        "绘画欣赏任务已完成，感谢您的配合，请稍作休息。",

    "music_start":
        "接下来请聆听几段音乐。请保持放松，戴好耳机，"
        "聆听过程中请尽量保持头部静止。",

    "video_start":
        "接下来是视频欣赏环节。请戴上VR头显，"
        "如有任何不适请立即告知测试人员。",

    "voice_reading_start":
        "接下来是语音朗读任务。"
        "屏幕显示文字后，请以平常的语速和语调，清晰朗读出来。"
        "朗读时请保持自然，不需要特别控制语气，放松即可。",

    "voice_reading_passage":
        "请开始朗读。",

    "voice_reading_rest":
        "这段朗读已完成，请休息一分钟，放松一下，马上继续。",

    "voice_reading_end":
        "语音朗读任务已全部完成，感谢您的配合，请稍作休息。",

    "voice_interview_start":
        "接下来有几个简单的问题，请您用自然的语言回答，"
        "没有标准答案，放松表达即可。",

    "voice_describe_start":
        "接下来请描述您看到的图片内容，"
        "说说图片里有什么，以及您的感受。",

    # 阶段间休息
    "rest_break":
        "这个阶段已经完成，请休息一下，我们马上继续。",

    "rest_break_long":
        "请稍作休息，工作人员将协助您调整设备，请保持舒适坐姿。",

    # 实验开始/结束
    "experiment_start":
        "实验即将开始，全程约四十分钟。"
        "如有任何不适请及时告知测试人员，感谢您的参与。",

    "experiment_end":
        "所有实验任务已完成，非常感谢您的配合！"
        "请稍等，工作人员将协助您摘除设备。",

    # 眼部指令（静息态）
    "eyes_close": "请闭眼，保持放松。",
    "eyes_open":  "请睁眼，注视屏幕中央的注视点。",
}

# 任务名 → 语音脚本键映射
TASK_VOICE_MAP = {
    "rest":           "rest_start",
    "dotprobe":       "dotprobe_start",
    "painting":       "painting_start",
    "music":          "music_start",
    "video":          "video_start",
    "voice_reading":  "voice_reading_start",
    "voice_interview":"voice_interview_start",
    "voice_describe": "voice_describe_start",
}


class VoiceGuidance(QObject if QT_AVAILABLE else object):
    """
    AI 语音引导
    - speak(text)       直接说一段文字
    - speak_for_task(task_name)  播放任务开始前的引导语
    - 生成在后台线程，播放通过 play_signal 信号回到主线程
    """

    if QT_AVAILABLE:
        play_signal = pyqtSignal(str)   # 传递临时音频文件路径

    # 语音配置
    VOICE   = "zh-CN-XiaoxiaoNeural"   # 温柔女声
    RATE    = "+0%"
    VOLUME  = "+0%"

    def __init__(self, parent=None):
        if QT_AVAILABLE:
            super().__init__(parent)
        else:
            super().__init__()

        self._available = EDGE_TTS_AVAILABLE and QT_AVAILABLE
        self._tmp_files: list = []   # 跟踪临时文件，用于清理

        if self._available:
            logger.info("✓ AI 语音引导已就绪  音色：%s", self.VOICE)
        else:
            logger.info("⚠ AI 语音引导不可用（edge-tts 未安装）")

    # ── 对外接口 ──────────────────────────────────────────────

    def speak(self, text: str):
        """播放指定文字的语音（非阻塞）"""
        if not self._available or not text.strip():
            return
        threading.Thread(
            target=self._generate_and_emit,
            args=(text,),
            daemon=True
        ).start()

    def speak_for_task(self, task_name: str):
        """播放对应任务的开场引导语"""
        key = TASK_VOICE_MAP.get(task_name)
        if key:
            text = VOICE_SCRIPTS.get(key, "")
            if text:
                self.speak(text)

    def speak_eyes_close(self):
        self.speak(VOICE_SCRIPTS["eyes_close"])

    def speak_eyes_open(self):
        self.speak(VOICE_SCRIPTS["eyes_open"])

    def speak_experiment_start(self):
        self.speak(VOICE_SCRIPTS["experiment_start"])

    def speak_experiment_end(self):
        self.speak(VOICE_SCRIPTS["experiment_end"])

    def speak_rest_break(self, long: bool = False):
        key = "rest_break_long" if long else "rest_break"
        self.speak(VOICE_SCRIPTS[key])

    # ── 内部实现 ─────────────────────────────────────────────

    def _generate_and_emit(self, text: str):
        """在后台线程生成 TTS 音频，通过信号传给主线程播放"""
        try:
            # Python < 3.12 的 Windows 上，aiohttp 与 ProactorEventLoop 不兼容，
            # 需要强制切换为 SelectorEventLoop。
            # Python 3.12+ 已修复，且 3.14 开始该 API 已 deprecated。
            if sys.platform == "win32" and sys.version_info < (3, 12):
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(self._async_generate(text))
        except Exception as e:
            logger.error("语音生成失败: %s", e)

    async def _async_generate(self, text: str):
        tmp = tempfile.mktemp(suffix=".mp3")
        last_err = None

        # 最多重试 2 次（网络抖动时重试一次）
        for attempt in range(2):
            try:
                # edge-tts 7.x 只传 text + voice，不传 rate/volume 避免格式兼容问题
                communicate = edge_tts.Communicate(text, self.VOICE)

                await asyncio.wait_for(communicate.save(tmp), timeout=10.0)

                if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                    self._tmp_files.append(tmp)
                    self.play_signal.emit(tmp)
                    return
                else:
                    last_err = "生成了空文件"
            except asyncio.TimeoutError:
                last_err = "网络超时（10s）"
                logger.warning("TTS 第%d次尝试超时，%s",
                               attempt + 1, "重试中..." if attempt == 0 else "放弃")
            except Exception as e:
                last_err = str(e)
                logger.warning("TTS 第%d次失败: %s，%s",
                               attempt + 1, e, "重试中..." if attempt == 0 else "放弃")

        logger.error("TTS 最终失败（%s）— 语音引导跳过", last_err)
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass

    def cleanup(self):
        """清理临时音频文件"""
        for f in self._tmp_files:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except Exception:
                pass
        self._tmp_files.clear()

    def __del__(self):
        self.cleanup()


# ── 全局单例（可选）───────────────────────────────────────────

_instance: Optional[VoiceGuidance] = None


def get_voice() -> Optional[VoiceGuidance]:
    """获取全局语音引导单例（需在主线程调用）"""
    global _instance
    if _instance is None and EDGE_TTS_AVAILABLE:
        _instance = VoiceGuidance()
    return _instance
