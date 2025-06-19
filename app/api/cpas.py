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


@router.get("/lookup-passcode/{passcode}")
async def lookup_passcode(passcode: str, db: Session = Depends(get_db)):
    """Simple passcode lookup - just find the CPA"""
    try:
        # Direct database lookup
        cpa = db.query(CPA).filter(CPA.passcode == passcode).first()

        if not cpa:
            return {"found": False, "message": "No CPA found with that passcode"}

        # Check if user exists
        user = db.query(User).filter(User.license_number == cpa.license_number).first()

        return {
            "found": True,
            "cpa": {
                "license_number": cpa.license_number,
                "full_name": cpa.full_name,
                "status": cpa.status,
                "passcode": cpa.passcode,
            },
            "user_exists": user is not None,
            "ready_for_signup": user is None,
        }
    except Exception as e:
        return {"error": str(e), "found": False}


@router.get("/verify-passcode")
async def verify_passcode(passcode: str, db: Session = Depends(get_db)):
    """Verify passcode and return CPA info for frontend compatibility"""
    try:
        # Use the exact same query as lookup-passcode (which works)
        cpa = db.query(CPA).filter(CPA.passcode == passcode).first()

        if not cpa:
            raise HTTPException(status_code=404, detail="Invalid passcode")

        # Check if user already exists with this license
        existing_user = (
            db.query(User).filter(User.license_number == cpa.license_number).first()
        )

        if existing_user:
            # Passcode already used
            raise HTTPException(
                status_code=409, detail="This passcode has already been used"
            )

        # Return success response matching frontend expectations
        return {
            "success": True,
            "cpa": {
                "license_number": cpa.license_number,
                "full_name": cpa.full_name,
                "status": cpa.status,
                "passcode": cpa.passcode,
            },
            "message": "Passcode verified successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in verify-passcode: {str(e)}")  # Add debugging
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.get("/debug-passcode")  # Temporary debugging endpoint
async def debug_passcode(passcode: str, db: Session = Depends(get_db)):
    """Debug passcode lookup"""
    try:
        print(f"Looking for passcode: '{passcode}'")

        # Check all passcodes in database
        all_passcodes = db.query(CPA.passcode).filter(CPA.passcode.isnot(None)).all()
        print(f"All passcodes in DB: {[p[0] for p in all_passcodes]}")

        # Try the exact query
        cpa = db.query(CPA).filter(CPA.passcode == passcode).first()
        print(f"Found CPA: {cpa}")

        return {
            "passcode_searched": passcode,
            "found_cpa": cpa is not None,
            "all_passcodes": [p[0] for p in all_passcodes],
        }

    except Exception as e:
        return {"error": str(e)}


@router.get("/diagnose-passcode")
async def diagnose_passcode(passcode: str, db: Session = Depends(get_db)):
    """Diagnose passcode lookup issues"""
    try:
        # Multiple ways to find the CPA
        result = {}

        # Method 1: Exact same as lookup-passcode
        cpa1 = db.query(CPA).filter(CPA.passcode == passcode).first()
        result["method1_direct"] = cpa1 is not None

        # Method 2: Case sensitive check
        cpa2 = db.query(CPA).filter(CPA.passcode.ilike(passcode)).first()
        result["method2_case_insensitive"] = cpa2 is not None

        # Method 3: Find by license and check passcode
        cpa3 = db.query(CPA).filter(CPA.license_number == "07308").first()
        result["method3_by_license"] = {
            "found": cpa3 is not None,
            "passcode_in_db": cpa3.passcode if cpa3 else None,
            "passcode_matches": cpa3.passcode == passcode if cpa3 else False,
        }

        # Method 4: Raw SQL
        raw_result = db.execute(
            "SELECT license_number, passcode FROM cpas WHERE passcode = :passcode",
            {"passcode": passcode},
        ).fetchone()
        result["method4_raw_sql"] = raw_result is not None

        return result

    except Exception as e:
        return {"error": str(e)}
