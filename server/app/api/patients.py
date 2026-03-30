"""
患者 CRUD API
"""

from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_org_id
from app.models import Patient
from app.schemas.schemas import PatientCreate, PatientUpdate, PatientResponse

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/", response_model=List[PatientResponse])
async def list_patients(
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(Patient.org_id == org_id).order_by(Patient.created_at.desc())
    )
    return [PatientResponse.model_validate(p) for p in result.scalars()]


@router.post("/", response_model=PatientResponse, status_code=201)
async def create_patient(
    body: PatientCreate,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    patient = Patient(org_id=org_id, **body.model_dump())
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return PatientResponse.model_validate(patient)


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    patient = await db.get(Patient, patient_id)
    if not patient or patient.org_id != org_id:
        raise HTTPException(status_code=404, detail="患者不存在")
    return PatientResponse.model_validate(patient)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    body: PatientUpdate,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    patient = await db.get(Patient, patient_id)
    if not patient or patient.org_id != org_id:
        raise HTTPException(status_code=404, detail="患者不存在")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)

    await db.commit()
    await db.refresh(patient)
    return PatientResponse.model_validate(patient)


@router.delete("/{patient_id}", status_code=204)
async def delete_patient(
    patient_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    patient = await db.get(Patient, patient_id)
    if not patient or patient.org_id != org_id:
        raise HTTPException(status_code=404, detail="患者不存在")
    await db.delete(patient)
    await db.commit()
