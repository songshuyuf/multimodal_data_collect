"""
实验会话 CRUD + 关联文件列表
"""

from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.deps import get_org_id
from app.models import Session, Patient, DataFile
from app.schemas.schemas import SessionCreate, SessionResponse, DataFileResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/", response_model=List[SessionResponse])
async def list_sessions(
    patient_id: UUID = None,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            Session,
            func.count(DataFile.id).label("file_count"),
        )
        .join(Patient, Session.patient_id == Patient.id)
        .outerjoin(DataFile, DataFile.session_id == Session.id)
        .where(Patient.org_id == org_id)
        .group_by(Session.id)
        .order_by(Session.created_at.desc())
    )
    if patient_id:
        query = query.where(Session.patient_id == patient_id)

    result = await db.execute(query)
    rows = result.all()
    return [
        SessionResponse(
            **{c.key: getattr(s, c.key) for c in Session.__table__.columns},
            file_count=fc,
        )
        for s, fc in rows
    ]


@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreate,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    patient = await db.get(Patient, body.patient_id)
    if not patient or patient.org_id != org_id:
        raise HTTPException(status_code=404, detail="患者不存在")

    session = Session(**body.model_dump())
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse(
        **{c.key: getattr(session, c.key) for c in Session.__table__.columns},
        file_count=0,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session, func.count(DataFile.id).label("fc"))
        .join(Patient)
        .outerjoin(DataFile, DataFile.session_id == Session.id)
        .where(Session.id == session_id, Patient.org_id == org_id)
        .group_by(Session.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    s, fc = row
    return SessionResponse(
        **{c.key: getattr(s, c.key) for c in Session.__table__.columns},
        file_count=fc,
    )


@router.get("/{session_id}/files", response_model=List[DataFileResponse])
async def list_session_files(
    session_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    session = await db.execute(
        select(Session).join(Patient).where(
            Session.id == session_id, Patient.org_id == org_id,
        )
    )
    if not session.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="会话不存在")

    result = await db.execute(
        select(DataFile).where(DataFile.session_id == session_id)
    )
    return [DataFileResponse.model_validate(f) for f in result.scalars()]


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).join(Patient).where(
            Session.id == session_id, Patient.org_id == org_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.delete(session)
    await db.commit()
