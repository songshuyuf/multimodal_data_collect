"""
数据上传管理器 — 分块上传 + 断点续传 + CSV压缩 + 多文件并发
=============================================================
在服务端未就绪时，队列会安全持久化到本地 JSON，服务端上线后自动恢复上传。
"""

import os
import json
import gzip
import hashlib
import logging
import time
import shutil
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

CHUNK_SIZE = 4 * 1024 * 1024          # 4 MB
MAX_CONCURRENT = 2
RETRY_DELAYS = [5, 15, 30, 60, 120]   # 指数退避(秒)
QUEUE_PATH = os.path.join("config", "upload_queue.json")
CONFIG_PATH = os.path.join("config", "upload_config.json")
COMPRESSED_DIR = os.path.join("config", ".upload_cache")


class UploadStatus(str, Enum):
    PENDING = "pending"
    COMPRESSING = "compressing"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class UploadTask:
    task_id: str
    file_path: str
    session_name: str
    modality: str
    file_size: int
    compressed_path: str = ""
    upload_id: str = ""
    total_chunks: int = 0
    uploaded_chunks: int = 0
    status: str = UploadStatus.PENDING
    error: str = ""
    retry_count: int = 0
    file_hash: str = ""
    created_at: str = ""
    completed_at: str = ""


class UploadManager(QObject):
    """后台上传管理器：分块 + 断点续传 + 压缩 + 多线程"""

    task_added = pyqtSignal(str)                    # task_id
    task_progress = pyqtSignal(str, int, int)       # task_id, uploaded_chunks, total_chunks
    task_status_changed = pyqtSignal(str, str)      # task_id, new_status
    task_failed = pyqtSignal(str, str)              # task_id, error_msg
    task_completed = pyqtSignal(str)                # task_id
    all_completed = pyqtSignal()
    queue_changed = pyqtSignal()
    connection_status = pyqtSignal(bool, str)       # ok, message
    upload_speed = pyqtSignal(float)                # bytes/sec

    _COMPRESSIBLE = {'.csv', '.txt', '.json', '.tsv', '.log'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: Dict[str, UploadTask] = {}
        self._lock = threading.Lock()
        self._running = False
        self._paused = False
        self._workers: List[threading.Thread] = []
        self._semaphore = threading.Semaphore(MAX_CONCURRENT)

        self.server_url: str = ""
        self.api_key: str = ""
        self.auto_upload: bool = True
        self._token: str = ""
        self._token_expires: float = 0

        os.makedirs("config", exist_ok=True)
        os.makedirs(COMPRESSED_DIR, exist_ok=True)

        self._load_config()
        self._load_queue()

    # ── 配置持久化 ──────────────────────────────────

    def _load_config(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.server_url = cfg.get("server_url", "")
                self.api_key = cfg.get("api_key", "")
                self.auto_upload = cfg.get("auto_upload", True)
        except Exception as e:
            logger.warning("加载上传配置失败: %s", e)

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "server_url": self.server_url,
                    "api_key": self.api_key,
                    "auto_upload": self.auto_upload,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("保存上传配置失败: %s", e)

    # ── 队列持久化 ──────────────────────────────────

    def _load_queue(self):
        try:
            if os.path.exists(QUEUE_PATH):
                with open(QUEUE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for d in data:
                    t = UploadTask(**d)
                    if t.status == UploadStatus.UPLOADING:
                        t.status = UploadStatus.PENDING
                    if t.status == UploadStatus.COMPRESSING:
                        t.status = UploadStatus.PENDING
                    self._tasks[t.task_id] = t
        except Exception as e:
            logger.warning("加载上传队列失败: %s", e)

    def _save_queue(self):
        try:
            with self._lock:
                items = [asdict(t) for t in self._tasks.values()]
            with open(QUEUE_PATH, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("保存上传队列失败: %s", e)

    # ── 会话扫描 ─────────────────────────────────────

    def scan_session(self, session_dir: str) -> List[UploadTask]:
        """扫描会话目录，返回可上传的文件任务列表（不会重复添加）。"""
        tasks = []
        session_name = os.path.basename(session_dir)
        existing_paths = {t.file_path for t in self._tasks.values()}

        for root, _dirs, files in os.walk(session_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                if fpath in existing_paths:
                    continue
                rel = os.path.relpath(root, session_dir)
                modality = rel.split(os.sep)[0] if rel != '.' else 'other'
                try:
                    fsize = os.path.getsize(fpath)
                except OSError:
                    continue
                if fsize == 0:
                    continue
                task = UploadTask(
                    task_id=uuid.uuid4().hex[:12],
                    file_path=fpath,
                    session_name=session_name,
                    modality=modality,
                    file_size=fsize,
                    created_at=datetime.now().isoformat(),
                )
                tasks.append(task)
        return tasks

    def add_session(self, session_dir: str) -> int:
        """扫描并加入队列，返回新增数量。"""
        new_tasks = self.scan_session(session_dir)
        for t in new_tasks:
            self._tasks[t.task_id] = t
            self.task_added.emit(t.task_id)
        if new_tasks:
            self._save_queue()
            self.queue_changed.emit()
        logger.info("从 %s 添加 %d 个上传任务", session_dir, len(new_tasks))
        return len(new_tasks)

    # ── 任务查询 ─────────────────────────────────────

    def get_task(self, task_id: str) -> Optional[UploadTask]:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[UploadTask]:
        with self._lock:
            return list(self._tasks.values())

    def get_pending_count(self) -> int:
        return sum(1 for t in self._tasks.values()
                   if t.status in (UploadStatus.PENDING, UploadStatus.UPLOADING))

    def get_completed_count(self) -> int:
        return sum(1 for t in self._tasks.values()
                   if t.status == UploadStatus.COMPLETED)

    def get_total_progress(self) -> Tuple[int, int]:
        """返回 (已完成字节, 总字节)"""
        done = sum(t.file_size for t in self._tasks.values()
                   if t.status == UploadStatus.COMPLETED)
        total = sum(t.file_size for t in self._tasks.values())
        return done, total

    # ── 上传控制 ─────────────────────────────────────

    def start(self):
        """开始/恢复处理上传队列。"""
        if self._running and not self._paused:
            return
        self._running = True
        self._paused = False
        self._dispatch()

    def pause(self):
        """暂停所有上传（当前分块完成后暂停）。"""
        self._paused = True
        with self._lock:
            for t in self._tasks.values():
                if t.status == UploadStatus.UPLOADING:
                    t.status = UploadStatus.PAUSED
                    self.task_status_changed.emit(t.task_id, t.status)
        self._save_queue()

    def stop(self):
        """停止上传管理器。"""
        self._running = False
        self._paused = True

    def retry_task(self, task_id: str):
        """重试单个失败的任务。"""
        t = self._tasks.get(task_id)
        if t and t.status == UploadStatus.FAILED:
            t.status = UploadStatus.PENDING
            t.error = ""
            t.retry_count = 0
            self.task_status_changed.emit(task_id, t.status)
            self._save_queue()
            if self._running:
                self._dispatch()

    def retry_all_failed(self):
        changed = False
        for t in self._tasks.values():
            if t.status == UploadStatus.FAILED:
                t.status = UploadStatus.PENDING
                t.error = ""
                t.retry_count = 0
                self.task_status_changed.emit(t.task_id, t.status)
                changed = True
        if changed:
            self._save_queue()
            if self._running:
                self._dispatch()

    def remove_task(self, task_id: str):
        t = self._tasks.pop(task_id, None)
        if t:
            if t.compressed_path and os.path.exists(t.compressed_path):
                try:
                    os.remove(t.compressed_path)
                except OSError:
                    pass
            self._save_queue()
            self.queue_changed.emit()

    def clear_completed(self):
        to_remove = [tid for tid, t in self._tasks.items()
                     if t.status == UploadStatus.COMPLETED]
        for tid in to_remove:
            t = self._tasks.pop(tid)
            if t.compressed_path and os.path.exists(t.compressed_path):
                try:
                    os.remove(t.compressed_path)
                except OSError:
                    pass
        if to_remove:
            self._save_queue()
            self.queue_changed.emit()

    # ── 调度 ─────────────────────────────────────────

    def _dispatch(self):
        if not self._running or self._paused:
            return
        with self._lock:
            pending = [t for t in self._tasks.values()
                       if t.status == UploadStatus.PENDING]
        for task in pending:
            if not self._running or self._paused:
                break
            t = threading.Thread(
                target=self._worker_wrapper, args=(task,),
                daemon=True, name=f"upload-{task.task_id}"
            )
            t.start()
            self._workers.append(t)

    def _worker_wrapper(self, task: UploadTask):
        self._semaphore.acquire()
        try:
            self._upload_file(task)
        finally:
            self._semaphore.release()
            self._check_all_done()

    def _check_all_done(self):
        with self._lock:
            active = any(t.status in (UploadStatus.PENDING,
                                       UploadStatus.UPLOADING,
                                       UploadStatus.COMPRESSING)
                         for t in self._tasks.values())
        if not active:
            self.all_completed.emit()

    # ── 单文件上传流程 ──────────────────────────────

    def _upload_file(self, task: UploadTask):
        """单个文件的完整上传流程：压缩 → 初始化 → 分块传输 → 完成确认"""
        try:
            if not self.server_url or not self.api_key:
                self._fail_task(task, "服务器未配置")
                return

            src = task.file_path
            if not os.path.exists(src):
                self._fail_task(task, f"文件不存在: {src}")
                return

            # ─ 阶段1: 压缩(CSV等文本文件) ─
            ext = os.path.splitext(src)[1].lower()
            if ext in self._COMPRESSIBLE and not task.compressed_path:
                task.status = UploadStatus.COMPRESSING
                self.task_status_changed.emit(task.task_id, task.status)
                compressed = self._compress_file(src)
                task.compressed_path = compressed
                self._save_queue()

            upload_path = task.compressed_path if task.compressed_path else src
            upload_size = os.path.getsize(upload_path)
            task.total_chunks = max(1, -(-upload_size // CHUNK_SIZE))

            # ─ 阶段2: 计算文件哈希(用于断点续传校验) ─
            if not task.file_hash:
                task.file_hash = self._md5(upload_path)
                self._save_queue()

            # ─ 阶段3: 服务端初始化上传 ─
            task.status = UploadStatus.UPLOADING
            self.task_status_changed.emit(task.task_id, task.status)

            if not task.upload_id:
                upload_id = self._api_init_upload(task, upload_size)
                if not upload_id:
                    return
                task.upload_id = upload_id
                self._save_queue()

            # ─ 阶段4: 分块传输(带断点续传) ─
            start_chunk = task.uploaded_chunks
            with open(upload_path, "rb") as f:
                f.seek(start_chunk * CHUNK_SIZE)
                for i in range(start_chunk, task.total_chunks):
                    if self._paused or not self._running:
                        task.status = UploadStatus.PAUSED
                        self.task_status_changed.emit(task.task_id, task.status)
                        self._save_queue()
                        return

                    chunk = f.read(CHUNK_SIZE)
                    ok = self._api_upload_chunk(task.upload_id, i, chunk)
                    if not ok:
                        self._fail_task(task, f"分块 {i} 上传失败")
                        return

                    task.uploaded_chunks = i + 1
                    self.task_progress.emit(
                        task.task_id, task.uploaded_chunks, task.total_chunks
                    )
                    self._save_queue()

            # ─ 阶段5: 完成确认 ─
            ok = self._api_complete_upload(task.upload_id)
            if not ok:
                self._fail_task(task, "完成确认失败")
                return

            task.status = UploadStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            self.task_status_changed.emit(task.task_id, task.status)
            self.task_completed.emit(task.task_id)
            self._save_queue()
            logger.info("上传完成: %s", task.file_path)

        except Exception as e:
            self._fail_task(task, str(e))

    def _fail_task(self, task: UploadTask, error: str):
        task.status = UploadStatus.FAILED
        task.error = error
        task.retry_count += 1
        self.task_status_changed.emit(task.task_id, task.status)
        self.task_failed.emit(task.task_id, error)
        self._save_queue()
        logger.warning("上传失败 [%s]: %s", task.task_id, error)

        if task.retry_count <= len(RETRY_DELAYS) and self._running:
            delay = RETRY_DELAYS[min(task.retry_count - 1, len(RETRY_DELAYS) - 1)]
            logger.info("  %ds 后重试 (第%d次)", delay, task.retry_count)
            threading.Timer(delay, self._auto_retry, args=(task.task_id,)).start()

    def _auto_retry(self, task_id: str):
        t = self._tasks.get(task_id)
        if t and t.status == UploadStatus.FAILED and self._running:
            t.status = UploadStatus.PENDING
            self.task_status_changed.emit(task_id, t.status)
            self._dispatch()

    # ── 文件压缩 ─────────────────────────────────────

    @staticmethod
    def _compress_file(file_path: str) -> str:
        gz_path = os.path.join(
            COMPRESSED_DIR,
            os.path.basename(file_path) + ".gz"
        )
        with open(file_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        logger.info("压缩 %s → %s (%.1f%%)",
                     file_path, gz_path,
                     100 * os.path.getsize(gz_path) / max(1, os.path.getsize(file_path)))
        return gz_path

    @staticmethod
    def _md5(file_path: str) -> str:
        h = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # ── 服务端 API 调用(HTTP) ────────────────────────

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/octet-stream",
        }

    def _api_init_upload(self, task: UploadTask, upload_size: int) -> Optional[str]:
        """POST /api/v1/uploads/init → upload_id"""
        try:
            import requests
            resp = requests.post(
                f"{self.server_url.rstrip('/')}/api/v1/uploads/init",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "session_name": task.session_name,
                    "file_name": os.path.basename(task.file_path),
                    "modality": task.modality,
                    "file_size": upload_size,
                    "file_hash": task.file_hash,
                    "total_chunks": task.total_chunks,
                    "compressed": bool(task.compressed_path),
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                resumed = data.get("uploaded_chunks", 0)
                if resumed > 0:
                    task.uploaded_chunks = resumed
                    logger.info("断点续传: 跳过前 %d 个分块", resumed)
                return data["upload_id"]
            else:
                self._fail_task(task, f"初始化失败 HTTP {resp.status_code}: {resp.text[:200]}")
                return None
        except ImportError:
            self._fail_task(task, "缺少 requests 库，请 pip install requests")
            return None
        except Exception as e:
            self._fail_task(task, f"连接服务器失败: {e}")
            return None

    def _api_upload_chunk(self, upload_id: str, chunk_index: int, data: bytes) -> bool:
        """PUT /api/v1/uploads/{upload_id}/chunks/{chunk_index}"""
        try:
            import requests
            resp = requests.put(
                f"{self.server_url.rstrip('/')}/api/v1/uploads/{upload_id}/chunks/{chunk_index}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/octet-stream",
                },
                data=data,
                timeout=60,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _api_complete_upload(self, upload_id: str) -> bool:
        """POST /api/v1/uploads/{upload_id}/complete"""
        try:
            import requests
            resp = requests.post(
                f"{self.server_url.rstrip('/')}/api/v1/uploads/{upload_id}/complete",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def test_connection(self) -> Tuple[bool, str]:
        """测试与服务端的连接。"""
        if not self.server_url:
            return False, "未配置服务器地址"
        if not self.api_key:
            return False, "未配置 API Key"
        try:
            from urllib.request import Request, urlopen
            from urllib.error import URLError, HTTPError
            url = f"{self.server_url.rstrip('/')}/api/v1/health"
            req = Request(url, method="GET")
            req.add_header("Authorization", f"Bearer {self.api_key}")
            resp = urlopen(req, timeout=10)
            if resp.status == 200:
                msg = "连接成功"
                return True, msg
            else:
                msg = f"服务器返回 HTTP {resp.status}"
                return False, msg
        except HTTPError as e:
            msg = f"服务器返回 HTTP {e.code}"
            return False, msg
        except URLError as e:
            msg = f"连接失败: {e.reason}"
            return False, msg
        except Exception as e:
            msg = f"连接失败: {e}"
            return False, msg

    # ── 实用工具 ─────────────────────────────────────

    @staticmethod
    def format_size(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"
