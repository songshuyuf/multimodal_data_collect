"""
文件管理器
管理多模态数据的文件组织和存储
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class FileManager:
    """文件管理器 - 负责会话数据的文件系统管理"""

    def __init__(self, base_path: str = "./data/sessions"):
        """
        初始化文件管理器

        Args:
            base_path: 会话数据的根目录
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

        # 支持的文件扩展名
        self.supported_extensions = {
            'shimmer': ['.csv', '.txt'],
            'video': ['.mp4', '.avi', '.mov'],
            'audio': ['.wav', '.mp3', '.flac']
        }

    def create_session_directory(self, patient_id: int, session_name: str) -> str:
        """
        创建会话目录结构

        Args:
            patient_id: 患者ID
            session_name: 会话名称

        Returns:
            会话目录路径
        """
        try:
            # 生成目录名: P{patient_id}_{session_name}_{timestamp}
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dir_name = f"P{patient_id:04d}_{session_name}_{timestamp}"
            session_path = self.base_path / dir_name

            # 创建主目录和子目录
            session_path.mkdir(parents=True, exist_ok=True)
            (session_path / 'shimmer').mkdir(exist_ok=True)
            (session_path / 'video').mkdir(exist_ok=True)
            (session_path / 'audio').mkdir(exist_ok=True)

            self.logger.info(f"创建会话目录: {session_path}")
            return str(session_path)

        except Exception as e:
            self.logger.error(f"创建会话目录失败: {e}")
            raise

    def get_session_path(self, session_dir: str) -> Path:
        """
        获取会话完整路径

        Args:
            session_dir: 会话目录名

        Returns:
            完整路径对象
        """
        return self.base_path / session_dir

    def get_modality_path(self, session_dir: str, modality: str) -> Path:
        """
        获取模态数据路径

        Args:
            session_dir: 会话目录名
            modality: 模态类型 ('shimmer', 'video', 'audio')

        Returns:
            模态数据目录路径
        """
        return self.base_path / session_dir / modality

    def list_session_files(self, session_dir: str) -> Dict[str, List[str]]:
        """
        列出会话中所有文件

        Args:
            session_dir: 会话目录名

        Returns:
            各模态的文件列表
        """
        files = {
            'shimmer': [],
            'video': [],
            'audio': []
        }

        try:
            session_path = self.get_session_path(session_dir)

            for modality in ['shimmer', 'video', 'audio']:
                modality_path = session_path / modality
                if modality_path.exists():
                    files[modality] = [
                        f.name for f in modality_path.iterdir()
                        if f.is_file() and f.suffix in self.supported_extensions[modality]
                    ]

            return files

        except Exception as e:
            self.logger.error(f"列出会话文件失败: {e}")
            return files

    def check_modality_exists(self, session_dir: str, modality: str) -> bool:
        """
        检查某个模态是否有数据

        Args:
            session_dir: 会话目录名
            modality: 模态类型

        Returns:
            是否存在数据文件
        """
        try:
            modality_path = self.get_modality_path(session_dir, modality)
            if not modality_path.exists():
                return False

            # 检查是否有支持的文件
            for file in modality_path.iterdir():
                if file.is_file() and file.suffix in self.supported_extensions[modality]:
                    return True

            return False

        except Exception as e:
            self.logger.error(f"检查模态数据失败: {e}")
            return False

    def get_session_size(self, session_dir: str) -> Dict[str, int]:
        """
        计算会话数据大小

        Args:
            session_dir: 会话目录名

        Returns:
            各模态和总大小（字节）
        """
        sizes = {
            'shimmer': 0,
            'video': 0,
            'audio': 0,
            'total': 0
        }

        try:
            session_path = self.get_session_path(session_dir)

            for modality in ['shimmer', 'video', 'audio']:
                modality_path = session_path / modality
                if modality_path.exists():
                    sizes[modality] = sum(
                        f.stat().st_size for f in modality_path.rglob('*') if f.is_file()
                    )

            sizes['total'] = sum(sizes[m] for m in ['shimmer', 'video', 'audio'])

            return sizes

        except Exception as e:
            self.logger.error(f"计算会话大小失败: {e}")
            return sizes

    def delete_session_directory(self, session_dir: str) -> bool:
        """
        删除会话目录及其所有内容

        Args:
            session_dir: 会话目录名

        Returns:
            是否成功
        """
        try:
            session_path = self.get_session_path(session_dir)
            if session_path.exists():
                shutil.rmtree(session_path)
                self.logger.info(f"删除会话目录: {session_path}")
                return True
            else:
                self.logger.warning(f"会话目录不存在: {session_path}")
                return False

        except Exception as e:
            self.logger.error(f"删除会话目录失败: {e}")
            return False

    def move_file(self, source: str, session_dir: str, modality: str,
                  new_name: Optional[str] = None) -> Optional[str]:
        """
        移动文件到会话目录

        Args:
            source: 源文件路径
            session_dir: 目标会话目录
            modality: 模态类型
            new_name: 新文件名（可选）

        Returns:
            目标文件路径，失败返回None
        """
        try:
            source_path = Path(source)
            if not source_path.exists():
                self.logger.error(f"源文件不存在: {source}")
                return None

            # 确定目标文件名
            if new_name:
                target_name = new_name
            else:
                target_name = source_path.name

            # 目标路径
            target_path = self.get_modality_path(session_dir, modality) / target_name

            # 移动文件
            shutil.move(str(source_path), str(target_path))
            self.logger.info(f"移动文件: {source} -> {target_path}")

            return str(target_path)

        except Exception as e:
            self.logger.error(f"移动文件失败: {e}")
            return None

    def copy_file(self, source: str, session_dir: str, modality: str,
                  new_name: Optional[str] = None) -> Optional[str]:
        """
        复制文件到会话目录

        Args:
            source: 源文件路径
            session_dir: 目标会话目录
            modality: 模态类型
            new_name: 新文件名（可选）

        Returns:
            目标文件路径，失败返回None
        """
        try:
            source_path = Path(source)
            if not source_path.exists():
                self.logger.error(f"源文件不存在: {source}")
                return None

            # 确定目标文件名
            if new_name:
                target_name = new_name
            else:
                target_name = source_path.name

            # 目标路径
            target_path = self.get_modality_path(session_dir, modality) / target_name

            # 复制文件
            shutil.copy2(str(source_path), str(target_path))
            self.logger.info(f"复制文件: {source} -> {target_path}")

            return str(target_path)

        except Exception as e:
            self.logger.error(f"复制文件失败: {e}")
            return None

    def list_all_sessions(self) -> List[str]:
        """
        列出所有会话目录

        Returns:
            会话目录名列表
        """
        try:
            sessions = [
                d.name for d in self.base_path.iterdir()
                if d.is_dir() and d.name.startswith('P')
            ]
            return sorted(sessions)

        except Exception as e:
            self.logger.error(f"列出会话目录失败: {e}")
            return []

    def cleanup_empty_directories(self, session_dir: str) -> None:
        """
        清理空的模态目录

        Args:
            session_dir: 会话目录名
        """
        try:
            session_path = self.get_session_path(session_dir)

            for modality in ['shimmer', 'video', 'audio']:
                modality_path = session_path / modality
                if modality_path.exists() and not any(modality_path.iterdir()):
                    modality_path.rmdir()
                    self.logger.info(f"删除空目录: {modality_path}")

        except Exception as e:
            self.logger.error(f"清理空目录失败: {e}")

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """
        格式化文件大小

        Args:
            size_bytes: 字节数

        Returns:
            格式化的大小字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"