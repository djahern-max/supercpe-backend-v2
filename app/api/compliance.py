from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.cpa import CPA
from app.services.time_window_compliance import TimeWindowComplianceService
from typing import Dict, Any

router = APIRouter(prefix="/api/compliance", tags=["Compliance"])


@router.get("/{license_number}")
async def get_cpa_compliance(
    license_number: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get detailed compliance status for a specific CPA"""

    # Find the CPA
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Use the time window compliance service
    service = TimeWindowComplianceService()
    windows = service.get_available_windows(cpa)

    # Get current window
    current_window = None
    for window in windows:
        if window.is_current:
            current_window = window
            break

    if not current_window:
        return {"error": "No current compliance period found"}

    return {
        "license_number": cpa.license_number,
        "full_name": cpa.full_name,
        "current_period": {
            "start_date": current_window.start_date.isoformat(),
            "end_date": current_window.end_date.isoformat(),
            "hours_required": current_window.hours_required,
            "ethics_required": current_window.ethics_required,
            "description": current_window.window_description,
        },
        "status": "Active" if cpa.status == "Active" else "Inactive",
    }


@router.get("/test/rules")
async def test_compliance_rules(db: Session = Depends(get_db)):
    """Test endpoint to verify compliance rules work correctly"""

    service = TimeWindowComplianceService()

    # Get a test CPA
    test_cpa = db.query(CPA).first()
    if not test_cpa:
        return {"message": "No CPAs found in database"}

    windows = service.get_available_windows(test_cpa)

    return {
        "message": "Compliance Rules Test",
        "test_cpa": {
            "license_number": test_cpa.license_number,
            "name": test_cpa.full_name,
            "available_windows": len(windows),
        },
    }
