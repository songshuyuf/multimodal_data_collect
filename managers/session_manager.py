"""
会话管理器
协调数据库和文件系统，管理采集会话的生命周期
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path

from database.database_manager import DatabaseManager
from database.models import Session
from .file_manager import FileManager


class SessionManager:
    """会话管理器 - 管理采集会话的完整生命周期"""

    def __init__(self, db_manager: DatabaseManager, file_manager: FileManager):
        """
        初始化会话管理器

        Args:
            db_manager: 数据库管理器实例
            file_manager: 文件管理器实例
        """
        self.db = db_manager
        self.fm = file_manager
        self.logger = logging.getLogger(__name__)

        # 当前活动会话
        self.current_session_id: Optional[int] = None
        self.current_session_dir: Optional[str] = None

    def create_session(self, patient_id: int, session_name: str,
                       notes: str = "") -> Optional[Session]:
        """
        创建新会话

        Args:
            patient_id: 患者ID
            session_name: 会话名称
            notes: 备注

        Returns:
            创建的会话对象，失败返回None
        """
        try:
            # 1. 创建文件目录
            session_dir = self.fm.create_session_directory(patient_id, session_name)

            # 2. 创建数据库记录
            session = Session(
                patient_id=patient_id,
                session_name=session_name,
                session_date=datetime.now(),
                data_path=Path(session_dir).name,  # 只保存目录名
                notes=notes
            )

            session_id = self.db.add_session(session)
            session.session_id = session_id

            self.logger.info(f"创建会话成功: {session_name} (ID: {session_id})")
            return session

        except Exception as e:
            self.logger.error(f"创建会话失败: {e}")
            # 清理已创建的目录
            if session_dir:
                self.fm.delete_session_directory(Path(session_dir).name)
            return None

    def start_session(self, session_id: int) -> bool:
        """
        启动会话（开始采集前调用）

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        try:
            # 获取会话信息
            session = self.db.get_session(session_id)
            if not session:
                self.logger.error(f"会话不存在: {session_id}")
                return False

            # 设置为当前活动会话
            self.current_session_id = session_id
            self.current_session_dir = session.data_path

            # 更新会话开始时间
            session.session_date = datetime.now()
            self.db.update_session(session)

            self.logger.info(f"启动会话: {session.session_name} (ID: {session_id})")
            return True

        except Exception as e:
            self.logger.error(f"启动会话失败: {e}")
            return False

    def end_session(self, duration: int = 0, quality_score: Optional[float] = None) -> bool:
        """
        结束会话（采集完成后调用）

        Args:
            duration: 会话持续时间（秒）
            quality_score: 数据质量评分 (0-1)

        Returns:
            是否成功
        """
        try:
            if not self.current_session_id:
                self.logger.warning("没有活动会话")
                return False

            # 获取会话信息
            session = self.db.get_session(self.current_session_id)
            if not session:
                return False

            # 更新会话信息
            session.duration = duration
            session.quality_score = quality_score

            # 检查各模态数据
            session.has_shimmer = self.fm.check_modality_exists(
                self.current_session_dir, 'shimmer'
            )
            session.has_video = self.fm.check_modality_exists(
                self.current_session_dir, 'video'
            )
            session.has_audio = self.fm.check_modality_exists(
                self.current_session_dir, 'audio'
            )

            # 保存到数据库
            self.db.update_session(session)

            # 清理空目录
            self.fm.cleanup_empty_directories(self.current_session_dir)

            self.logger.info(f"结束会话: {session.session_name} (时长: {duration}秒)")

            # 清除当前会话
            self.current_session_id = None
            self.current_session_dir = None

            return True

        except Exception as e:
            self.logger.error(f"结束会话失败: {e}")
            return False

    def get_current_session_paths(self) -> Optional[Dict[str, str]]:
        """
        获取当前会话的数据路径

        Returns:
            各模态的数据路径字典，无活动会话返回None
        """
        if not self.current_session_dir:
            return None

        return {
            'shimmer': str(self.fm.get_modality_path(self.current_session_dir, 'shimmer')),
            'video': str(self.fm.get_modality_path(self.current_session_dir, 'video')),
            'audio': str(self.fm.get_modality_path(self.current_session_dir, 'audio'))
        }

    def get_session_info(self, session_id: int) -> Optional[Dict]:
        """
        获取会话的完整信息

        Args:
            session_id: 会话ID

        Returns:
            会话信息字典
        """
        try:
            # 从数据库获取会话
            session = self.db.get_session(session_id)
            if not session:
                return None

            # 从数据库获取患者信息
            patient = self.db.get_patient(session.patient_id)

            # 从文件系统获取数据大小
            sizes = self.fm.get_session_size(session.data_path)

            # 获取文件列表
            files = self.fm.list_session_files(session.data_path)

            return {
                'session': session.to_dict(),
                'patient': patient.to_dict() if patient else None,
                'sizes': sizes,
                'files': files
            }

        except Exception as e:
            self.logger.error(f"获取会话信息失败: {e}")
            return None

    def delete_session(self, session_id: int) -> bool:
        """
        删除会话（包括数据库记录和文件）

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        try:
            # 获取会话信息
            session = self.db.get_session(session_id)
            if not session:
                self.logger.warning(f"会话不存在: {session_id}")
                return False

            # 删除文件目录
            self.fm.delete_session_directory(session.data_path)

            # 删除数据库记录
            self.db.delete_session(session_id)

            self.logger.info(f"删除会话成功 (ID: {session_id})")
            return True

        except Exception as e:
            self.logger.error(f"删除会话失败: {e}")
            return False

    def validate_session_data(self, session_id: int) -> Dict[str, bool]:
        """
        验证会话数据的完整性

        Args:
            session_id: 会话ID

        Returns:
            验证结果字典
        """
        result = {
            'valid': False,
            'has_shimmer': False,
            'has_video': False,
            'has_audio': False,
            'errors': []
        }

        try:
            session = self.db.get_session(session_id)
            if not session:
                result['errors'].append("会话不存在")
                return result

            # 检查目录是否存在
            session_path = self.fm.get_session_path(session.data_path)
            if not session_path.exists():
                result['errors'].append("会话目录不存在")
                return result

            # 验证各模态数据
            result['has_shimmer'] = self.fm.check_modality_exists(
                session.data_path, 'shimmer'
            )
            result['has_video'] = self.fm.check_modality_exists(
                session.data_path, 'video'
            )
            result['has_audio'] = self.fm.check_modality_exists(
                session.data_path, 'audio'
            )

            # 至少有一个模态有数据才算有效
            if any([result['has_shimmer'], result['has_video'], result['has_audio']]):
                result['valid'] = True
            else:
                result['errors'].append("没有任何模态数据")

            return result

        except Exception as e:
            result['errors'].append(str(e))
            return result

    def export_session_data(self, session_id: int, export_path: str) -> bool:
        """
        导出会话数据到指定路径

        Args:
            session_id: 会话ID
            export_path: 导出目标路径

        Returns:
            是否成功
        """
        try:
            import shutil

            session = self.db.get_session(session_id)
            if not session:
                self.logger.error(f"会话不存在: {session_id}")
                return False

            # 源路径
            source_path = self.fm.get_session_path(session.data_path)
            if not source_path.exists():
                self.logger.error(f"会话数据不存在: {source_path}")
                return False

            # 目标路径
            target_path = Path(export_path) / session.data_path

            # 复制整个目录
            shutil.copytree(source_path, target_path)

            self.logger.info(f"导出会话成功: {source_path} -> {target_path}")
            return True

        except Exception as e:
            self.logger.error(f"导出会话失败: {e}")
            return False

    def get_patient_sessions(self, patient_id: int) -> List[Session]:
        """
        获取患者的所有会话

        Args:
            patient_id: 患者ID

        Returns:
            会话列表
        """
        return self.db.get_patient_sessions(patient_id)

    def search_sessions(self, keyword: str) -> List[Session]:
        """
        搜索会话

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的会话列表
        """
        # 这里可以实现更复杂的搜索逻辑
        # 暂时返回空列表，待扩展
        return []