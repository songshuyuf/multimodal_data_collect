"""
数据库管理器
使用SQLite管理患者信息和采集会话
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .models import Patient, Session


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_path: str = "./data/database/patients.db"):
        """
        初始化数据库管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.conn = None
        self._initialize_database()

    def _initialize_database(self):
        """初始化数据库表"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.cursor()

            # 创建患者表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patients (
                    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    age INTEGER,
                    gender TEXT,
                    diagnosis TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建会话表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    session_name TEXT NOT NULL,
                    session_date TIMESTAMP,
                    duration INTEGER DEFAULT 0,
                    data_path TEXT,
                    has_shimmer BOOLEAN DEFAULT 0,
                    has_video BOOLEAN DEFAULT 0,
                    has_audio BOOLEAN DEFAULT 0,
                    quality_score REAL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
                )
            ''')

            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_patient_name ON patients(name)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_session_patient ON sessions(patient_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_session_date ON sessions(session_date)
            ''')

            self.conn.commit()
            self.logger.info(f"数据库初始化成功: {self.db_path}")

        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            raise

    # ==================== 患者管理 ====================

    def add_patient(self, patient: Patient) -> int:
        """
        添加患者

        Args:
            patient: 患者对象

        Returns:
            新患者的ID
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO patients (name, age, gender, diagnosis, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (patient.name, patient.age, patient.gender, patient.diagnosis, patient.notes))

            self.conn.commit()
            patient_id = cursor.lastrowid
            self.logger.info(f"添加患者成功: {patient.name} (ID: {patient_id})")
            return patient_id

        except Exception as e:
            self.logger.error(f"添加患者失败: {e}")
            self.conn.rollback()
            raise

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        """
        获取患者信息

        Args:
            patient_id: 患者ID

        Returns:
            患者对象，如果不存在返回None
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM patients WHERE patient_id = ?', (patient_id,))
            row = cursor.fetchone()

            if row:
                return Patient(
                    patient_id=row['patient_id'],
                    name=row['name'],
                    age=row['age'],
                    gender=row['gender'],
                    diagnosis=row['diagnosis'],
                    notes=row['notes'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
            return None

        except Exception as e:
            self.logger.error(f"获取患者失败: {e}")
            return None

    def get_all_patients(self, limit: int = 100, offset: int = 0) -> List[Patient]:
        """
        获取所有患者

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            患者列表
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM patients 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))

            patients = []
            for row in cursor.fetchall():
                patients.append(Patient(
                    patient_id=row['patient_id'],
                    name=row['name'],
                    age=row['age'],
                    gender=row['gender'],
                    diagnosis=row['diagnosis'],
                    notes=row['notes'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                ))

            return patients

        except Exception as e:
            self.logger.error(f"获取患者列表失败: {e}")
            return []

    def update_patient(self, patient: Patient) -> bool:
        """
        更新患者信息

        Args:
            patient: 患者对象

        Returns:
            是否成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE patients 
                SET name = ?, age = ?, gender = ?, diagnosis = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE patient_id = ?
            ''', (patient.name, patient.age, patient.gender, patient.diagnosis,
                  patient.notes, patient.patient_id))

            self.conn.commit()
            self.logger.info(f"更新患者成功: {patient.name} (ID: {patient.patient_id})")
            return True

        except Exception as e:
            self.logger.error(f"更新患者失败: {e}")
            self.conn.rollback()
            return False

    def delete_patient(self, patient_id: int) -> bool:
        """
        删除患者（级联删除相关会话）

        Args:
            patient_id: 患者ID

        Returns:
            是否成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM patients WHERE patient_id = ?', (patient_id,))
            self.conn.commit()
            self.logger.info(f"删除患者成功 (ID: {patient_id})")
            return True

        except Exception as e:
            self.logger.error(f"删除患者失败: {e}")
            self.conn.rollback()
            return False

    def search_patients(self, keyword: str) -> List[Patient]:
        """
        搜索患者

        Args:
            keyword: 搜索关键词（姓名或诊断）

        Returns:
            匹配的患者列表
        """
        try:
            cursor = self.conn.cursor()
            keyword_pattern = f'%{keyword}%'
            cursor.execute('''
                SELECT * FROM patients 
                WHERE name LIKE ? OR diagnosis LIKE ?
                ORDER BY created_at DESC
            ''', (keyword_pattern, keyword_pattern))

            patients = []
            for row in cursor.fetchall():
                patients.append(Patient(
                    patient_id=row['patient_id'],
                    name=row['name'],
                    age=row['age'],
                    gender=row['gender'],
                    diagnosis=row['diagnosis'],
                    notes=row['notes'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                ))

            return patients

        except Exception as e:
            self.logger.error(f"搜索患者失败: {e}")
            return []

    # ==================== 会话管理 ====================

    def add_session(self, session: Session) -> int:
        """
        添加会话

        Args:
            session: 会话对象

        Returns:
            新会话的ID
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO sessions 
                (patient_id, session_name, session_date, duration, data_path,
                 has_shimmer, has_video, has_audio, quality_score, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session.patient_id, session.session_name, session.session_date,
                  session.duration, session.data_path, session.has_shimmer,
                  session.has_video, session.has_audio, session.quality_score,
                  session.notes))

            self.conn.commit()
            session_id = cursor.lastrowid
            self.logger.info(f"添加会话成功: {session.session_name} (ID: {session_id})")
            return session_id

        except Exception as e:
            self.logger.error(f"添加会话失败: {e}")
            self.conn.rollback()
            raise

    def get_session(self, session_id: int) -> Optional[Session]:
        """
        获取会话信息

        Args:
            session_id: 会话ID

        Returns:
            会话对象
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
            row = cursor.fetchone()

            if row:
                return Session(
                    session_id=row['session_id'],
                    patient_id=row['patient_id'],
                    session_name=row['session_name'],
                    session_date=datetime.fromisoformat(row['session_date']) if row['session_date'] else None,
                    duration=row['duration'],
                    data_path=row['data_path'],
                    has_shimmer=bool(row['has_shimmer']),
                    has_video=bool(row['has_video']),
                    has_audio=bool(row['has_audio']),
                    quality_score=row['quality_score'],
                    notes=row['notes'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
                )
            return None

        except Exception as e:
            self.logger.error(f"获取会话失败: {e}")
            return None

    def get_patient_sessions(self, patient_id: int) -> List[Session]:
        """
        获取患者的所有会话

        Args:
            patient_id: 患者ID

        Returns:
            会话列表
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM sessions 
                WHERE patient_id = ? 
                ORDER BY session_date DESC
            ''', (patient_id,))

            sessions = []
            for row in cursor.fetchall():
                sessions.append(Session(
                    session_id=row['session_id'],
                    patient_id=row['patient_id'],
                    session_name=row['session_name'],
                    session_date=datetime.fromisoformat(row['session_date']) if row['session_date'] else None,
                    duration=row['duration'],
                    data_path=row['data_path'],
                    has_shimmer=bool(row['has_shimmer']),
                    has_video=bool(row['has_video']),
                    has_audio=bool(row['has_audio']),
                    quality_score=row['quality_score'],
                    notes=row['notes'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
                ))

            return sessions

        except Exception as e:
            self.logger.error(f"获取患者会话失败: {e}")
            return []

    def update_session(self, session: Session) -> bool:
        """
        更新会话信息

        Args:
            session: 会话对象

        Returns:
            是否成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE sessions 
                SET session_name = ?, session_date = ?, duration = ?, 
                    data_path = ?, has_shimmer = ?, has_video = ?, has_audio = ?,
                    quality_score = ?, notes = ?
                WHERE session_id = ?
            ''', (session.session_name, session.session_date, session.duration,
                  session.data_path, session.has_shimmer, session.has_video,
                  session.has_audio, session.quality_score, session.notes,
                  session.session_id))

            self.conn.commit()
            self.logger.info(f"更新会话成功 (ID: {session.session_id})")
            return True

        except Exception as e:
            self.logger.error(f"更新会话失败: {e}")
            self.conn.rollback()
            return False

    def delete_session(self, session_id: int) -> bool:
        """
        删除会话

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
            self.conn.commit()
            self.logger.info(f"删除会话成功 (ID: {session_id})")
            return True

        except Exception as e:
            self.logger.error(f"删除会话失败: {e}")
            self.conn.rollback()
            return False

    # ==================== 统计信息 ====================

    def get_patient_stats(self, patient_id: int) -> dict:
        """
        获取患者的统计信息

        Args:
            patient_id: 患者ID

        Returns:
            统计信息字典
        """
        try:
            cursor = self.conn.cursor()

            # 总会话数
            cursor.execute('''
                SELECT COUNT(*) as total FROM sessions WHERE patient_id = ?
            ''', (patient_id,))
            total_sessions = cursor.fetchone()['total']

            # 总时长
            cursor.execute('''
                SELECT SUM(duration) as total_duration FROM sessions WHERE patient_id = ?
            ''', (patient_id,))
            total_duration = cursor.fetchone()['total_duration'] or 0

            # 各模态数据数量
            cursor.execute('''
                SELECT 
                    SUM(has_shimmer) as shimmer_count,
                    SUM(has_video) as video_count,
                    SUM(has_audio) as audio_count
                FROM sessions WHERE patient_id = ?
            ''', (patient_id,))
            row = cursor.fetchone()

            return {
                'total_sessions': total_sessions,
                'total_duration': total_duration,
                'shimmer_sessions': row['shimmer_count'] or 0,
                'video_sessions': row['video_count'] or 0,
                'audio_sessions': row['audio_count'] or 0
            }

        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {}

    def get_database_stats(self) -> dict:
        """
        获取数据库统计信息

        Returns:
            统计信息字典
        """
        try:
            cursor = self.conn.cursor()

            # 患者总数
            cursor.execute('SELECT COUNT(*) as total FROM patients')
            total_patients = cursor.fetchone()['total']

            # 会话总数
            cursor.execute('SELECT COUNT(*) as total FROM sessions')
            total_sessions = cursor.fetchone()['total']

            return {
                'total_patients': total_patients,
                'total_sessions': total_sessions
            }

        except Exception as e:
            self.logger.error(f"获取数据库统计失败: {e}")
            return {}

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.logger.info("数据库连接已关闭")