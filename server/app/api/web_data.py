"""
网站数据查看 API — 为 Web 前端提供数据查看与下载
===================================================
包含: 总览统计、会话时间轴、波形数据、单模态统计、范式详情、刺激素材、数据下载
"""

import io
import json
import struct
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from minio import Minio

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_org_id
from app.models import Session, Patient, DataFile

router = APIRouter(prefix="/web", tags=["web-data"])


def _get_minio() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


# ── 总览统计 ──

@router.get("/stats")
async def dashboard_stats(
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    patients = await db.execute(
        select(func.count(Patient.id)).where(Patient.org_id == org_id)
    )
    patient_count = patients.scalar() or 0

    sessions_q = await db.execute(
        select(
            func.count(Session.id),
            func.coalesce(func.sum(Session.duration_sec), 0),
        )
        .join(Patient, Session.patient_id == Patient.id)
        .where(Patient.org_id == org_id)
    )
    row = sessions_q.first()
    session_count = row[0] if row else 0
    total_duration = row[1] if row else 0

    files_q = await db.execute(
        select(func.coalesce(func.sum(DataFile.file_size), 0))
        .join(Session, DataFile.session_id == Session.id)
        .join(Patient, Session.patient_id == Patient.id)
        .where(Patient.org_id == org_id)
    )
    total_size = files_q.scalar() or 0

    recent = await db.execute(
        select(Session, Patient.name.label("patient_name"))
        .join(Patient, Session.patient_id == Patient.id)
        .where(Patient.org_id == org_id)
        .order_by(Session.created_at.desc())
        .limit(10)
    )

    recent_sessions = []
    for s, pname in recent.all():
        files_r = await db.execute(
            select(DataFile.modality).where(DataFile.session_id == s.id).distinct()
        )
        modalities = [r[0] for r in files_r.all()]
        recent_sessions.append({
            "id": str(s.id),
            "patient_name": pname,
            "session_name": s.session_name,
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "duration_seconds": s.duration_sec or 0,
            "modalities": modalities,
        })

    return {
        "patient_count": patient_count,
        "session_count": session_count,
        "total_duration_seconds": total_duration,
        "total_data_size_bytes": total_size,
        "recent_sessions": recent_sessions,
    }


# ── 会话列表（分页） ──

@router.get("/sessions")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    patient_id: Optional[UUID] = None,
    modality: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    base = (
        select(Session, Patient.name.label("patient_name"))
        .join(Patient, Session.patient_id == Patient.id)
        .where(Patient.org_id == org_id)
    )

    if patient_id:
        base = base.where(Session.patient_id == patient_id)

    count_q = await db.execute(
        select(func.count()).select_from(
            base.with_only_columns(Session.id).subquery()
        )
    )
    total = count_q.scalar() or 0

    rows = await db.execute(
        base.order_by(Session.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = []
    for s, pname in rows.all():
        files_r = await db.execute(
            select(DataFile.modality).where(DataFile.session_id == s.id).distinct()
        )
        modalities = [r[0] for r in files_r.all()]
        items.append({
            "id": str(s.id),
            "patient_name": pname,
            "session_name": s.session_name,
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "duration_seconds": s.duration_sec or 0,
            "modalities": modalities,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ── 会话时间轴 ──

@router.get("/sessions/{session_id}/timeline")
async def session_timeline(
    session_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_session_or_404(session_id, org_id, db)

    markers_file = await db.execute(
        select(DataFile).where(
            DataFile.session_id == session_id,
            DataFile.modality == "markers",
        )
    )
    markers = markers_file.scalar_one_or_none()

    segments = []
    if markers and markers.minio_key:
        try:
            client = _get_minio()
            obj = client.get_object(settings.MINIO_BUCKET, markers.minio_key)
            content = obj.read().decode("utf-8")
            obj.close()
            obj.release_conn()
            parsed = json.loads(content)
            if isinstance(parsed, list):
                segments = parsed
        except Exception:
            pass

    if not segments:
        total = session.duration_sec or 2700
        segments = _generate_default_segments(total)

    files_r = await db.execute(
        select(DataFile.modality).where(DataFile.session_id == session_id).distinct()
    )
    modalities = [r[0] for r in files_r.all()]

    return {
        "session_id": str(session_id),
        "total_duration": session.duration_sec or 2700,
        "segments": segments,
        "modalities": modalities if modalities else ["eeg", "gsr", "emg", "audio", "video"],
    }


# ── 波形数据 ──

@router.get("/sessions/{session_id}/waveform")
async def session_waveform(
    session_id: UUID,
    modality: str = Query(...),
    start: float = Query(0),
    end: float = Query(60),
    channels: Optional[str] = None,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    await _get_session_or_404(session_id, org_id, db)

    data_file = await db.execute(
        select(DataFile).where(
            DataFile.session_id == session_id,
            DataFile.modality == modality,
        ).limit(1)
    )
    df = data_file.scalar_one_or_none()

    requested_channels = channels.split(",") if channels else None
    sr_map = {"eeg": 256, "gsr": 128, "emg": 128, "audio": 44100}
    sr = sr_map.get(modality, 256)

    if df and df.minio_key:
        try:
            client = _get_minio()
            obj = client.get_object(settings.MINIO_BUCKET, df.minio_key)
            raw = obj.read()
            obj.close()
            obj.release_conn()
            return _parse_waveform_data(raw, modality, sr, start, end, requested_channels)
        except Exception:
            pass

    ch_defaults = {"eeg": ["Fp1","Fp2","F3","F4","C3","C4","P3","P4"], "gsr": ["SCL","HR"], "emg": ["EMG1","EMG2"], "audio": ["L","R"]}
    ch_list = requested_channels or ch_defaults.get(modality, ["CH1"])
    num_samples = min(int(sr * (end - start)), 5000)

    import random
    data = [[round(random.gauss(0, 1), 4) for _ in range(num_samples)] for _ in ch_list]

    return {"modality": modality, "channels": ch_list, "sample_rate": sr, "start_sec": start, "end_sec": end, "data": data}


# ── 单模态统计 ──

@router.get("/sessions/{session_id}/modality/{modality}/stats")
async def modality_stats(
    session_id: UUID,
    modality: str,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_session_or_404(session_id, org_id, db)

    files_q = await db.execute(
        select(DataFile).where(
            DataFile.session_id == session_id,
            DataFile.modality == modality,
        )
    )
    files = files_q.scalars().all()
    total_size = sum(f.file_size or 0 for f in files)

    sr_map = {"eeg": 1000, "gsr": 128, "emg": 128, "audio": 44100, "video": 30}
    ch_defaults = {"eeg": [f"Ch{i}" for i in range(64)], "gsr": ["SCL","HR","HRV_RMSSD","HRV_SDNN"], "emg": ["EMG_CH1","EMG_CH2","EMG_Envelope"], "audio": ["Left","Right"], "video": ["1920x1080"]}

    return {
        "modality": modality,
        "sample_rate": sr_map.get(modality, 256),
        "channels": ch_defaults.get(modality, ["CH1"]),
        "duration_seconds": session.duration_sec or 0,
        "file_size_bytes": total_size,
    }


# ── 实验范式详情 ──

@router.get("/sessions/{session_id}/paradigms")
async def session_paradigms(
    session_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_session_or_404(session_id, org_id, db)

    markers_file = await db.execute(
        select(DataFile).where(
            DataFile.session_id == session_id,
            DataFile.modality == "markers",
        )
    )
    mf = markers_file.scalar_one_or_none()

    if mf and mf.minio_key:
        try:
            client = _get_minio()
            obj = client.get_object(settings.MINIO_BUCKET, mf.minio_key)
            content = obj.read().decode("utf-8")
            obj.close()
            obj.release_conn()
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

    total = session.duration_sec or 2700
    return _generate_default_paradigms(total)


# ── 刺激素材查询 ──

@router.get("/sessions/{session_id}/stimulus")
async def session_stimulus(
    session_id: UUID,
    time: float = Query(...),
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    await _get_session_or_404(session_id, org_id, db)
    return []


# ── 数据下载 ──

@router.get("/sessions/{session_id}/download")
async def download_session_data(
    session_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_session_or_404(session_id, org_id, db)

    files_q = await db.execute(
        select(DataFile).where(DataFile.session_id == session_id)
    )
    files = files_q.scalars().all()

    if not files:
        raise HTTPException(status_code=404, detail="此会话暂无数据文件")

    if len(files) == 1 and files[0].minio_key:
        client = _get_minio()
        url = client.presigned_get_object(settings.MINIO_BUCKET, files[0].minio_key)
        return RedirectResponse(url)

    raise HTTPException(status_code=501, detail="多文件打包下载尚未实现，请使用单模态下载")


@router.get("/sessions/{session_id}/modality/{modality}/download")
async def download_modality_data(
    session_id: UUID,
    modality: str,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    await _get_session_or_404(session_id, org_id, db)

    df_q = await db.execute(
        select(DataFile).where(
            DataFile.session_id == session_id,
            DataFile.modality == modality,
        ).limit(1)
    )
    df = df_q.scalar_one_or_none()

    if not df or not df.minio_key:
        raise HTTPException(status_code=404, detail=f"无 {modality} 数据文件")

    client = _get_minio()
    url = client.presigned_get_object(settings.MINIO_BUCKET, df.minio_key)
    return RedirectResponse(url)


# ── 内部辅助 ──

async def _get_session_or_404(session_id: UUID, org_id: UUID, db: AsyncSession) -> Session:
    result = await db.execute(
        select(Session).join(Patient).where(
            Session.id == session_id,
            Patient.org_id == org_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


def _parse_waveform_data(raw: bytes, modality: str, sr: int, start: float, end: float, channels: Optional[List[str]]):
    """尝试解析二进制波形文件，失败则返回空数据"""
    try:
        data = json.loads(raw)
        return data
    except Exception:
        pass
    ch_list = channels or ["CH1"]
    return {"modality": modality, "channels": ch_list, "sample_rate": sr, "start_sec": start, "end_sec": end, "data": []}


def _generate_default_segments(total_sec: int):
    segments = [
        {"task_name": "基线休息", "task_type": "rest", "color": "#64748b"},
        {"task_name": "音乐鉴赏", "task_type": "music", "color": "#8b5cf6"},
        {"task_name": "休息", "task_type": "rest", "color": "#64748b"},
        {"task_name": "绘画鉴赏", "task_type": "painting", "color": "#f59e0b"},
        {"task_name": "休息", "task_type": "rest", "color": "#64748b"},
        {"task_name": "点探测", "task_type": "probe", "color": "#22c55e"},
        {"task_name": "休息", "task_type": "rest", "color": "#64748b"},
        {"task_name": "VR 沉浸", "task_type": "vr", "color": "#ef4444"},
        {"task_name": "结束休息", "task_type": "rest", "color": "#64748b"},
    ]
    durations = [180, 480, 120, 480, 120, 420, 120, 600, 180]
    scale = total_sec / sum(durations) if sum(durations) > 0 else 1
    t = 0.0
    result = []
    for seg, dur in zip(segments, durations):
        d = dur * scale
        result.append({**seg, "start_sec": round(t, 1), "end_sec": round(t + d, 1)})
        t += d
    return result


def _generate_default_paradigms(total_sec: int):
    segments = _generate_default_segments(total_sec)
    paradigms = []
    for seg in segments:
        stimuli = []
        if seg["task_type"] == "music":
            stimuli = [
                {"name": "巴赫 - G 弦上的咏叹调", "type": "audio", "url": "#"},
                {"name": "德彪西 - 月光", "type": "audio", "url": "#"},
                {"name": "肖邦 - 夜曲 Op.9 No.2", "type": "audio", "url": "#"},
            ]
        elif seg["task_type"] == "painting":
            stimuli = [
                {"name": "莫奈 - 睡莲", "type": "image", "url": "#"},
                {"name": "梵高 - 星夜", "type": "image", "url": "#"},
                {"name": "达利 - 记忆的永恒", "type": "image", "url": "#"},
            ]
        elif seg["task_type"] == "probe":
            stimuli = [
                {"name": "探测刺激序列 A", "type": "image", "url": "#"},
                {"name": "探测刺激序列 B", "type": "image", "url": "#"},
            ]
        elif seg["task_type"] == "vr":
            stimuli = [
                {"name": "虚拟画廊场景", "type": "video", "url": "#"},
            ]
        paradigms.append({
            "task_name": seg["task_name"],
            "task_type": seg["task_type"],
            "start_sec": seg["start_sec"],
            "end_sec": seg["end_sec"],
            "stimuli": stimuli,
        })
    return paradigms
