"""
会话管理器 - 完全修复版
直接创建目录，不依赖 file_manager 的 create_session_directory
"""
import logging
from typing import Optional, List
from datetime import datetime
import os

from .database import DatabaseManager
from .files import FileManager
from .models import Session


class SessionManager:
    """会话管理器"""

    def __init__(self, db_manager: DatabaseManager, file_manager: FileManager):
        """
        初始化会话管理器

        Args:
            db_manager: 数据库管理器
            file_manager: 文件管理器
        """
        self.db = db_manager
        self.fm = file_manager
        self.logger = logging.getLogger(__name__)

        self.current_session: Optional[Session] = None

    def create_session(self, patient_id: str, session_number: int, notes: str = "") -> Optional[Session]:
        """
        创建新会话

        Args:
            patient_id: 患者ID (例如: "2")
            session_number: 会话序号
            notes: 备注信息

        Returns:
            Session对象 或 None
        """
        try:
            self.logger.info(f"开始创建会话，患者ID: {patient_id}")

            # ========== 获取患者信息 ==========
            patient = self.db.get_patient_by_id(patient_id)

            if patient and patient.name:
                patient_name = patient.name
                self.logger.info(f"找到患者: {patient_name}")
            else:
                # 如果找不到患者或没有名字，使用ID
                patient_name = f"P{patient_id}"
                self.logger.warning(f"未找到患者或无名字，使用: {patient_name}")

            print(f"[会话创建] 患者: {patient_name} (ID: {patient_id})")
            # =================================

            # 获取基础路径
            base_path = self.fm.base_path if hasattr(self.fm, 'base_path') else './data/sessions'

            # 格式: 姓名_YYYYMMDD 或 姓名_YYYYMMDD_02
            date_str = datetime.now().strftime("%Y%m%d")
            base_dir_name = f"{patient_name}_{date_str}"

            # 检查是否已存在
            session_dir = os.path.join(base_path, base_dir_name)

            if os.path.exists(session_dir):
                # 添加序号
                counter = 2
                while True:
                    dir_name = f"{base_dir_name}_{counter:02d}"
                    session_dir = os.path.join(base_path, dir_name)
                    if not os.path.exists(session_dir):
                        break
                    counter += 1

                self.logger.info(f"目录已存在，使用: {dir_name}")
            else:
                dir_name = base_dir_name

            # 创建目录
            os.makedirs(session_dir, exist_ok=True)
            self.logger.info(f"创建会话目录: {session_dir}")
            print(f"[会话创建] 目录: {session_dir}")

            # 创建子目录
            subdirs = ['heeg', 'shimmer', 'video', 'audio', 'markers']
            for subdir in subdirs:
                subdir_path = os.path.join(session_dir, subdir)
                os.makedirs(subdir_path, exist_ok=True)

            self.logger.info(f"子目录创建完成")

            # 创建数据库记录
            session = Session(
                session_id=None,
                patient_id=patient_id,
                session_name=str(session_number),
                session_date=datetime.now(),
                duration=0,
                data_path=dir_name,  # 只保存目录名
                has_shimmer=False,
                has_video=False,
                has_audio=False,
                quality_score=None,
                notes=notes,
                created_at=None
            )

            # 保存到数据库
            session_id = self.db.add_session(session)

            if session_id:
                session.session_id = session_id
                self.logger.info(f"创建会话成功: {session_number} (ID: {session_id})")
                print(f"[会话创建] 成功，ID: {session_id}")
                return session
            else:
                self.logger.error("会话数据库记录创建失败")
                return None

        except Exception as e:
            self.logger.error(f"创建会话失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def start_session(self, session_id: int) -> bool:
        """
        启动会话

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        try:
            session = self.db.get_session_by_id(session_id)
            if session:
                self.current_session = session

                # 更新会话开始时间
                self.db.update_session(session_id, session_date=datetime.now())

                self.logger.info(f"启动会话: {session.session_name} (ID: {session_id})")
                return True
            else:
                self.logger.error(f"找不到会话: {session_id}")
                return False

        except Exception as e:
            self.logger.error(f"启动会话失败: {e}")
            return False

    def end_session(self, session_id: int, duration: float) -> bool:
        """
        结束会话

        Args:
            session_id: 会话ID
            duration: 持续时间（秒）

        Returns:
            是否成功
        """
        try:
            # 更新会话时长
            self.db.update_session(session_id, duration=int(duration))

            self.current_session = None
            self.logger.info(f"结束会话 (ID: {session_id}), 时长: {duration:.1f}秒")
            return True

        except Exception as e:
            self.logger.error(f"结束会话失败: {e}")
            return False

    def get_current_session(self) -> Optional[Session]:
        """获取当前会话"""
        return self.current_session

    def get_current_session_paths(self) -> dict:
        """
        获取当前会话的数据路径

        Returns:
            路径字典 {'shimmer': path, 'heeg': path, 'video': path, 'audio': path}
        """
        if not self.current_session:
            return {}

        base_path = self.fm.base_path if hasattr(self.fm, 'base_path') else './data/sessions'
        session_dir = os.path.join(base_path, self.current_session.data_path)

        return {
            'shimmer': os.path.join(session_dir, 'shimmer', 'shimmer.csv'),
            'heeg': os.path.join(session_dir, 'heeg', 'heeg.csv'),
            'video': os.path.join(session_dir, 'video', 'video.avi'),
            'audio': os.path.join(session_dir, 'audio', 'audio.wav')
        }

    def get_patient_sessions(self, patient_id: str) -> List[Session]:
        """
        获取患者的所有会话

        Args:
            patient_id: 患者ID

        Returns:
            会话列表
        """
        return self.db.get_patient_sessions(patient_id)

    def update_session_stats(self, session_id: int, **kwargs) -> bool:
        """
        更新会话统计信息

        Args:
            session_id: 会话ID
            **kwargs: 要更新的字段

        Returns:
            是否成功
        """
        try:
            self.db.update_session(session_id, **kwargs)
            self.logger.info(f"更新会话统计 (ID: {session_id})")
            return True

        except Exception as e:
            self.logger.error(f"更新会话统计失败: {e}")
            return False
