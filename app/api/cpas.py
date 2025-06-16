from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.cpa import CPA
from pydantic import BaseModel
from datetime import date

router = APIRouter(prefix="/api/cpas", tags=["CPAs"])

class CPAResponse(BaseModel):
    id: int
    license_number: str
    full_name: str
    license_issue_date: date
    license_expiration_date: date
    status: str
    is_premium: bool
    total_cpe_hours: int
    ethics_hours: int
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[CPAResponse])
async def get_all_cpas(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """Get list of all CPAs"""
    cpas = db.query(CPA).offset(skip).limit(limit).all()
    return cpas

@router.get("/{license_number}", response_model=CPAResponse)
async def get_cpa_by_license(
    license_number: str, 
    db: Session = Depends(get_db)
):
    """Get specific CPA by license number"""
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CPA not found"
        )
    return cpa

@router.get("/stats/summary")
async def get_cpa_stats(db: Session = Depends(get_db)):
    """Get summary statistics"""
    total_cpas = db.query(CPA).count()
    active_cpas = db.query(CPA).filter(CPA.status == "Active").count()
    premium_cpas = db.query(CPA).filter(CPA.is_premium == True).count()
    
    return {
        "total_cpas": total_cpas,
        "active_cpas": active_cpas,
        "premium_cpas": premium_cpas,
        "free_cpas": active_cpas - premium_cpas
    }
