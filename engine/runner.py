"""
ExperimentRunner — 主线程状态机
================================
读取 experiment_config.json，构建 tasks + breaks 交织队列，
依次创建范式 Widget 并通过 finished 信号链式推进。
完全在主线程运行，无后台线程。
"""

import csv
import json
import os
import random
import time
from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from engine.dataset import DatasetManager
from engine.markers import MarkerManager, task_start_marker, task_end_marker


# ── 辅助：Dot-probe 试次生成 ────────────────────────────────────

def _make_dotprobe_trials(neutrals: list, stims: list, n: int) -> list:
    if not neutrals or not stims:
        return []
    neu_pool = (neutrals * (n // max(len(neutrals), 1) + 2))[:n]
    stim_pool = (stims * (n // max(len(stims), 1) + 2))[:n]
    random.shuffle(neu_pool)
    random.shuffle(stim_pool)
    trials = []
    for i in range(n):
        side = random.choice(["left", "right"])
        sp, np_ = stim_pool[i], neu_pool[i]
        trials.append({
            "neutral_path": np_,
            "stim_path": sp,
            "stim_side": side,
            "left_path": sp if side == "left" else np_,
            "right_path": np_ if side == "left" else sp,
        })
    return trials


# ── ParadigmFactory ─────────────────────────────────────────────

class ParadigmFactory:
    """根据 task_config 创建对应范式 Widget 实例。"""

    _REGISTRY = {
        "rest":            ("engine.paradigms.rest",            "RestParadigm"),
        "break":           ("engine.paradigms.rest_break",      "RestBreakParadigm"),
        "dotprobe":        ("engine.paradigms.dotprobe",        "DotProbeTask"),
        "painting":        ("engine.paradigms.painting",        "PaintingTask"),
        "music":           ("engine.paradigms.music",           "MusicTask"),
        "video":           ("engine.paradigms.vr",              "VRTask"),
        "voice_reading":   ("engine.paradigms.voice_reading",   "VoiceReadingTask"),
        "voice_interview": ("engine.paradigms.voice_interview", "VoiceInterviewTask"),
        "voice_describe":  ("engine.paradigms.image_describe",  "ImageDescribeTask"),
    }

    @classmethod
    def create(cls, task_config: dict, **kwargs):
        """
        task_config 必须含 'name' 键。
        kwargs 由 Runner 传入范式专属参数。
        """
        import importlib
        name = task_config["name"]
        entry = cls._REGISTRY.get(name)
        if entry is None:
            raise ValueError(f"未知范式类型: {name}")
        module_path, class_name = entry
        mod = importlib.import_module(module_path)
        klass = getattr(mod, class_name)
        return klass(**kwargs)


# ── ExperimentRunner ────────────────────────────────────────────

class ExperimentRunner(QObject):
    """
    主线程状态机，编排所有范式。

    调用方式：
        runner = ExperimentRunner(config_path, dataset_root, session_dir, voice)
        runner.start()
    """

    task_started = pyqtSignal(str, int)           # display_name, task_id
    task_progress = pyqtSignal(int, int)           # current, total
    experiment_finished = pyqtSignal()
    status_message = pyqtSignal(str)

    def __init__(self, config_path: str = "./experiment_config.json",
                 dataset_root: str = "./dataset",
                 session_dir: str = "./data/sessions/default",
                 voice=None, parent=None):
        super().__init__(parent)

        self._config_path = config_path
        self._dataset_root = dataset_root
        self._session_dir = session_dir
        self._voice = voice

        with open(config_path, "r", encoding="utf-8") as f:
            self._config: dict = json.load(f)

        self._dataset = DatasetManager(dataset_root)
        self._marker = MarkerManager()

        self._queue: List[dict] = []       # 交织后的任务/休息队列
        self._queue_idx = 0
        self._current_widget = None
        self._running = False
        self._sampled: Dict[str, object] = {}

    # ── 公开接口 ────────────────────────────────────────────────

    @property
    def marker_manager(self) -> MarkerManager:
        return self._marker

    def start(self):
        if self._running:
            return
        self._running = True
        os.makedirs(self._session_dir, exist_ok=True)

        self._marker.set_session_dir(self._session_dir)
        self._marker.send_marker("EXPERIMENT_START")

        self.status_message.emit("正在采样刺激材料…")
        self._sample_all_stimuli()

        self.status_message.emit("构建任务队列…")
        self._build_queue()

        self._queue_idx = 0
        self.status_message.emit("实验开始")
        self._show_opening()

    def _show_opening(self):
        """实验开场白：配音+界面，说完自动进入第一个任务"""
        try:
            from engine.paradigms.rest_break import RestBreakParadigm
            exp_name = self._config.get("experiment_name", "AI艺术诊疗多模态实验")
            total_min = self._config.get("total_duration", 2400) // 60
            n_tasks = sum(1 for q in self._queue if q["kind"] == "task")

            opening = RestBreakParadigm(
                message=(
                    f"欢迎参加\n{exp_name}\n\n"
                    f"本次实验共 {n_tasks} 个环节\n"
                    f"全程约 {total_min} 分钟\n\n"
                    "如有任何不适请随时告知工作人员"
                ),
                voice_text=(
                    f"您好，欢迎参加{exp_name}。"
                    f"本次实验共有{n_tasks}个环节，全程约{total_min}分钟。"
                    "实验过程中请保持放松，按照屏幕和语音提示操作即可。"
                    "如有任何不适请随时告知工作人员。"
                    "我们即将开始，请做好准备。"
                ),
                duration=20,
                output_path="",
                voice=self._voice,
            )
            self._current_widget = opening
            opening.finished.connect(self._on_opening_done)
            opening.start()
        except Exception:
            self._advance()

    def _on_opening_done(self, _path: str):
        if self._current_widget is not None:
            self._current_widget.finished.disconnect(self._on_opening_done)
            self._current_widget.deleteLater()
            self._current_widget = None
        self._advance()

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._marker.send_marker("EXPERIMENT_END")
        self._marker.close_csv()
        if self._current_widget is not None:
            self._current_widget._force_finish()

    # ── 队列构建 ────────────────────────────────────────────────

    def _build_queue(self):
        """将 tasks 和 rest_breaks 交织为统一队列。"""
        tasks = self._config.get("tasks", [])

        # Build breaks_map safely - after_task must be hashable (int/str)
        breaks_map: dict = {}
        for rb in self._config.get("rest_breaks", []):
            key = rb.get("after_task")
            if key is None:
                continue
            # If after_task is a list, register the break for each task id in the list
            if isinstance(key, list):
                for k in key:
                    try:
                        breaks_map[k] = rb
                    except TypeError:
                        pass
            else:
                try:
                    breaks_map[key] = rb
                except TypeError:
                    pass

        self._queue = []
        for task in tasks:
            self._queue.append({"kind": "task", "config": task})
            tid = task.get("id")
            if tid is not None and tid in breaks_map:
                rb = breaks_map[tid]
                self._queue.append({
                    "kind": "break",
                    "config": {
                        "name": "break",
                        "display_name": "休息",
                        "id": tid * 100,
                        "message": rb.get("message", "请稍作休息"),
                        "duration": rb.get("duration", 10),
                    },
                })

        print(f"[Runner] 队列共 {len(self._queue)} 项 "
              f"({sum(1 for q in self._queue if q['kind']=='task')} 任务 + "
              f"{sum(1 for q in self._queue if q['kind']=='break')} 休息)")

    # ── 推进 ───────────────────────────────────────────────────

    def _advance(self):
        if not self._running:
            return
        if self._queue_idx >= len(self._queue):
            self._finish_experiment()
            return

        item = self._queue[self._queue_idx]
        cfg = item["config"]

        display = cfg.get("display_name", cfg.get("name", ""))
        tid = cfg.get("id", 0)
        self.task_started.emit(display, tid)
        self.status_message.emit(f"▶ {display}")

        task_name = cfg.get("name", "")
        self._marker.send_marker(task_start_marker(task_name), task_id=tid)

        try:
            widget = self._create_paradigm(item)
        except Exception as e:
            print(f"[Runner] 范式创建失败 ({cfg.get('name')}): {e}")
            import traceback; traceback.print_exc()
            self.status_message.emit(f"跳过 {display}（创建失败）")
            self._marker.send_marker(task_end_marker(task_name), task_id=tid)
            self._queue_idx += 1
            QTimer.singleShot(200, self._advance)
            return

        if hasattr(widget, 'set_marker_manager'):
            widget.set_marker_manager(self._marker)

        self._current_widget = widget
        widget.finished.connect(self._on_paradigm_done)
        widget.start()

    def _on_paradigm_done(self, result_path: str):
        if self._queue_idx < len(self._queue):
            cfg = self._queue[self._queue_idx]["config"]
            task_name = cfg.get("name", "")
            tid = cfg.get("id", 0)
            self._marker.send_marker(task_end_marker(task_name), task_id=tid)

        if self._current_widget is not None:
            self._current_widget.finished.disconnect(self._on_paradigm_done)
            self._current_widget.deleteLater()
            self._current_widget = None

        if result_path:
            print(f"[Runner] 范式完成，结果: {result_path}")

        self._queue_idx += 1
        QTimer.singleShot(200, self._advance)

    def _finish_experiment(self):
        self._running = False
        self._marker.send_marker("EXPERIMENT_END")
        self._marker.close_csv()
        self.status_message.emit("实验已完成")
        stats = self._marker.get_statistics()
        print(f"[Runner] 全部范式执行完毕，共记录 {stats['total_markers']} 个 Marker")

        self._show_ending()

    def _show_ending(self):
        """显示实验结束语并播放语音"""
        try:
            from engine.paradigms.rest_break import RestBreakParadigm
            ending = RestBreakParadigm(
                message=(
                    "本次实验已全部完成\n\n"
                    "非常感谢您的耐心参与和配合\n\n"
                    "请稍等，工作人员将为您取下设备"
                ),
                voice_text=(
                    "本次实验已全部完成，非常感谢您的耐心参与和配合。"
                    "请稍等，工作人员将为您取下设备。祝您生活愉快！"
                ),
                duration=15,
                output_path="",
                voice=self._voice,
            )
            self._current_widget = ending
            ending.finished.connect(self._on_ending_done)
            ending.start()
        except Exception:
            self.experiment_finished.emit()

    def _on_ending_done(self, _path: str):
        if self._current_widget is not None:
            self._current_widget.finished.disconnect(self._on_ending_done)
            self._current_widget.deleteLater()
            self._current_widget = None
        self.experiment_finished.emit()

    # ── 范式创建 ────────────────────────────────────────────────

    def _create_paradigm(self, item: dict):
        cfg = item["config"]
        name = cfg["name"]
        params = cfg.get("params", {})
        ts = time.strftime("%Y%m%d_%H%M%S")

        if name == "rest":
            return ParadigmFactory.create(cfg,
                params=params,
                output_path=os.path.join(self._session_dir, f"rest_{ts}.csv"),
                voice=self._voice,
            )

        if name == "break":
            return ParadigmFactory.create(cfg,
                message=cfg.get("message", "请稍作休息"),
                duration=cfg.get("duration", 10),
                output_path="",
                voice=self._voice,
            )

        if name == "dotprobe":
            trials = self._sampled.get("dotprobe_trials", [])
            practice = self._sampled.get("dotprobe_practice", [])
            return ParadigmFactory.create(cfg,
                trials=trials,
                practice_trials=practice,
                output_path=os.path.join(self._session_dir, f"dotprobe_{ts}.csv"),
                voice=self._voice,
            )

        if name == "painting":
            paintings = self._sampled.get("paintings", [])
            return ParadigmFactory.create(cfg,
                paintings=paintings,
                params=params,
                output_path=os.path.join(self._session_dir, f"painting_{ts}.csv"),
                voice=self._voice,
            )

        if name == "music":
            music_list = self._sampled.get("music", [])
            return ParadigmFactory.create(cfg,
                music_list=music_list,
                params=params,
                output_path=os.path.join(self._session_dir, f"music_{ts}.csv"),
                voice=self._voice,
            )

        if name == "video":
            vr_params = dict(params)
            pc_path = vr_params.get("pc_video_path", "")
            if not pc_path:
                project_root = os.path.dirname(os.path.dirname(__file__))
                vr_params["pc_video_path"] = os.path.join(
                    project_root, "vr", "video", "fengjing.mp4"
                )
            return ParadigmFactory.create(cfg,
                params=vr_params,
                output_path=os.path.join(self._session_dir, f"vr_{ts}.csv"),
                voice=self._voice,
            )

        if name == "voice_reading":
            text = self._sampled.get("reading_text", "")
            return ParadigmFactory.create(cfg,
                text=text,
                params=params,
                output_path=os.path.join(self._session_dir, f"voice_reading_{ts}.csv"),
                voice=self._voice,
            )

        if name == "voice_interview":
            questions = self._sampled.get("interview_questions", [])
            return ParadigmFactory.create(cfg,
                questions=questions,
                params=params,
                output_path=os.path.join(self._session_dir, f"voice_interview_{ts}.csv"),
                voice=self._voice,
            )

        if name == "voice_describe":
            images = self._sampled.get("describe_images", [])
            return ParadigmFactory.create(cfg,
                images=images,
                params=params,
                output_path=os.path.join(self._session_dir, f"image_describe_{ts}.csv"),
                voice=self._voice,
            )

        raise ValueError(f"未知任务类型: {name}")

    # ── 刺激材料采样 ───────────────────────────────────────────

    def _sample_all_stimuli(self):
        print("\n" + "=" * 60)
        print("正在采样刺激材料...")
        print("=" * 60)

        for task in self._config.get("tasks", []):
            name = task["name"]
            params = task.get("params", {})

            if name == "dotprobe":
                self._sample_dotprobe(params)

            elif name == "painting":
                n = params.get("n_images", 30)
                self._sampled["paintings"] = self._dataset.sample_paintings(n)
                print(f"✓ 绘画作品: {len(self._sampled['paintings'])} 张")

            elif name == "music":
                n = params.get("n_clips", 9)
                self._sampled["music"] = self._dataset.sample_music(n)
                print(f"✓ 音乐片段: {len(self._sampled['music'])} 首")

            elif name == "voice_reading":
                self._sampled["reading_text"] = self._load_reading_text(
                    params.get("text_file", "")
                )
                print(f"✓ 朗读文本: {len(self._sampled['reading_text'])} 字")

            elif name == "voice_interview":
                n = params.get("n_questions", 3)
                self._sampled["interview_questions"] = self._load_interview_questions(
                    params.get("questions_file", ""), n
                )
                print(f"✓ 访谈问题: {len(self._sampled['interview_questions'])} 题")

            elif name == "voice_describe":
                self._sampled["describe_images"] = self._scan_describe_images(
                    params.get("images_dir", "dataset/picture/description"),
                    params.get("n_images", 4),
                )
                print(f"✓ 描述图片: {len(self._sampled['describe_images'])} 张")

        print("=" * 60)
        print("✓ 刺激材料采样完成")
        print("=" * 60 + "\n")

    # ── Dot-probe 专用采样 ──────────────────────────────────────

    def _sample_dotprobe(self, params: dict):
        n_trials = params.get("n_trials", 200)
        n_practice = params.get("n_practice", 5)

        neutrals = self._dataset.load_classified_images("neutral")
        stims = (self._dataset.load_classified_images("stimulus_neg") +
                 self._dataset.load_classified_images("stimulus_pos"))

        if neutrals and stims:
            self._sampled["dotprobe_trials"] = _make_dotprobe_trials(
                neutrals, stims, n_trials
            )
            self._sampled["dotprobe_practice"] = _make_dotprobe_trials(
                neutrals, stims, n_practice
            )
            print(f"✓ Dot-probe: {n_trials} 正式试次 + {n_practice} 练习试次")
        else:
            self._sampled["dotprobe_trials"] = []
            self._sampled["dotprobe_practice"] = []
            print("⚠ Dot-probe: 分类图片目录为空")

    # ── 语音任务辅助 ────────────────────────────────────────────

    @staticmethod
    def _load_reading_text(text_file: str) -> str:
        if text_file and os.path.isfile(text_file):
            try:
                with open(text_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return (
            "春天来了，万物复苏。公园里的花朵竞相开放，\n"
            "粉红色的樱花、洁白的玉兰、金黄的迎春花，\n"
            "把整个城市装点得分外美丽。\n\n"
            "小朋友们在草地上追逐嬉戏，老人们坐在长椅上\n"
            "享受着温暖的阳光。微风轻轻吹过，带来阵阵花香，\n"
            "让人心情格外舒畅。\n\n"
            "生活中有许多美好的事物值得我们去发现，\n"
            "只要保持一颗平静而开放的心，\n"
            "幸福便会悄然而至。"
        )

    @staticmethod
    def _load_interview_questions(questions_file: str, n: int) -> list:
        if questions_file and os.path.isfile(questions_file):
            try:
                with open(questions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    qs = data if isinstance(data, list) else data.get("questions", [])
                    return [str(q) for q in qs[:n]]
            except Exception:
                pass
        defaults = [
            "最近这段时间，您的心情总体上是怎么样的？有什么让您感到开心或者烦恼的事情吗？",
            "在日常生活中，您最喜欢做什么活动？这些活动能让您感到快乐吗？",
            "当您遇到压力或困难的时候，通常会怎么做来调节自己的状态？",
        ]
        return defaults[:n]

    @staticmethod
    def _scan_describe_images(images_dir: str, n: int) -> list:
        """扫描图像描述任务的图片列表。"""
        img_exts = {".jpg", ".jpeg", ".png", ".bmp"}
        images: list = []

        if not os.path.isdir(images_dir):
            project_root = os.path.dirname(os.path.dirname(__file__))
            alt = os.path.join(project_root, images_dir)
            if os.path.isdir(alt):
                images_dir = alt
            else:
                print(f"  [Runner] 图片目录不存在: {images_dir}")
                return images

        csv_path = os.path.join(images_dir, "selected_4.csv")
        if os.path.isfile(csv_path):
            try:
                with open(csv_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        path = row.get("path", "")
                        if path and os.path.isfile(path):
                            images.append({
                                "path": path,
                                "filename": os.path.basename(path),
                                "valence": row.get("valence", ""),
                                "arousal": row.get("arousal", ""),
                            })
            except Exception:
                pass

        if not images:
            for fname in sorted(os.listdir(images_dir)):
                if os.path.splitext(fname.lower())[1] in img_exts:
                    images.append({
                        "path": os.path.join(images_dir, fname),
                        "filename": fname,
                        "valence": "",
                        "arousal": "",
                    })

        if len(images) > n:
            images = random.sample(images, n)

        return images
