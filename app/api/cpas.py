from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.cpa import CPA
from pydantic import BaseModel
from datetime import date
from app.models.user import User

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
async def get_all_cpas(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get list of all CPAs"""
    cpas = db.query(CPA).offset(skip).limit(limit).all()
    return cpas


@router.get("/search")
async def search_cpas(q: str, limit: int = 10, db: Session = Depends(get_db)):
    """Search CPAs by name or license number"""

    if not q or len(q.strip()) < 2:
        raise HTTPException(
            status_code=400, detail="Search query must be at least 2 characters"
        )

    search_term = q.strip()

    # Search by license number (exact match first)
    if search_term.isdigit():
        license_match = (
            db.query(CPA)
            .filter(CPA.license_number == search_term, CPA.status == "Active")
            .first()
        )

        if license_match:
            return {
                "results": [license_match],
                "total": 1,
                "search_type": "license_exact",
            }

    # Search by name (case insensitive, partial match)
    name_results = (
        db.query(CPA)
        .filter(CPA.full_name.ilike(f"%{search_term}%"), CPA.status == "Active")
        .limit(limit)
        .all()
    )

    return {"results": name_results, "total": len(name_results), "search_type": "name"}


@router.get("/{license_number}", response_model=CPAResponse)
async def get_cpa_by_license(license_number: str, db: Session = Depends(get_db)):
    """Get specific CPA by license number"""
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="CPA not found"
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
        "free_cpas": active_cpas - premium_cpas,
    }


@router.get("/verify-passcode")
async def verify_passcode(passcode: str, db: Session = Depends(get_db)):
    """Verify passcode and return CPA info for signup"""
    if not passcode or len(passcode) < 6:
        raise HTTPException(status_code=400, detail="Invalid passcode format")

    cpa = db.query(CPA).filter(CPA.passcode == passcode).first()

    if not cpa:
        raise HTTPException(status_code=404, detail="Invalid passcode")

    # Check if already used
    existing_user = (
        db.query(User).filter(User.license_number == cpa.license_number).first()
    )
    if existing_user:
        raise HTTPException(status_code=409, detail="Passcode already used")

    return {
        "success": True,
        "cpa": {
            "license_number": cpa.license_number,
            "full_name": cpa.full_name,
            "status": cpa.status,
            "license_expiration_date": cpa.license_expiration_date,
            "passcode": cpa.passcode,
        },
    }
