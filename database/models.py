"""
数据模型定义
Patient: 患者信息
Session: 采集会话
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Patient:
    """患者信息模型"""
    patient_id: Optional[int] = None
    name: str = ""
    age: Optional[int] = None
    gender: str = ""  # 'M', 'F', 'Other'
    diagnosis: str = ""
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self):
        """转换为字典"""
        return {
            'patient_id': self.patient_id,
            'name': self.name,
            'age': self.age,
            'gender': self.gender,
            'diagnosis': self.diagnosis,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @classmethod
    def from_dict(cls, data):
        """从字典创建对象"""
        return cls(
            patient_id=data.get('patient_id'),
            name=data.get('name', ''),
            age=data.get('age'),
            gender=data.get('gender', ''),
            diagnosis=data.get('diagnosis', ''),
            notes=data.get('notes', ''),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )


@dataclass
class Session:
    """采集会话模型"""
    session_id: Optional[int] = None
    patient_id: int = 0
    session_name: str = ""
    session_date: Optional[datetime] = None
    duration: int = 0  # 秒
    data_path: str = ""

    # 模态状态
    has_shimmer: bool = False
    has_video: bool = False
    has_audio: bool = False

    # 数据质量
    quality_score: Optional[float] = None
    notes: str = ""

    created_at: Optional[datetime] = None

    def to_dict(self):
        """转换为字典"""
        return {
            'session_id': self.session_id,
            'patient_id': self.patient_id,
            'session_name': self.session_name,
            'session_date': self.session_date.isoformat() if self.session_date else None,
            'duration': self.duration,
            'data_path': self.data_path,
            'has_shimmer': self.has_shimmer,
            'has_video': self.has_video,
            'has_audio': self.has_audio,
            'quality_score': self.quality_score,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_dict(cls, data):
        """从字典创建对象"""
        return cls(
            session_id=data.get('session_id'),
            patient_id=data.get('patient_id', 0),
            session_name=data.get('session_name', ''),
            session_date=datetime.fromisoformat(data['session_date']) if data.get('session_date') else None,
            duration=data.get('duration', 0),
            data_path=data.get('data_path', ''),
            has_shimmer=bool(data.get('has_shimmer', False)),
            has_video=bool(data.get('has_video', False)),
            has_audio=bool(data.get('has_audio', False)),
            quality_score=data.get('quality_score'),
            notes=data.get('notes', ''),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None
        )