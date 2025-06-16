from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.cpa import CPA
from app.services.nh_compliance import NHComplianceService, get_cpa_compliance_dashboard
from typing import Dict, Any

router = APIRouter(prefix="/api/compliance", tags=["Compliance"])

@router.get("/{license_number}")
async def get_cpa_compliance(
    license_number: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get detailed compliance status for a specific CPA"""
    
    # Find the CPA
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")
    
    # For now, no CPE records (we'll add certificate upload later)
    cpe_records = []
    
    # Generate compliance dashboard
    dashboard = get_cpa_compliance_dashboard(cpa, cpe_records)
    
    return dashboard

@router.get("/test/rules")
async def test_compliance_rules(db: Session = Depends(get_db)):
    """Test endpoint to verify compliance rules work correctly"""
    
    service = NHComplianceService()
    
    # Get a few test CPAs with different scenarios
    test_cases = []
    
    # Your CPA (existing, 2027 expiration)
    your_cpa = db.query(CPA).filter(CPA.license_number == "07308").first()
    if your_cpa:
        period = service.calculate_compliance_period(your_cpa)
        test_cases.append({
            "license_number": "07308",
            "name": your_cpa.full_name,
            "issue_date": your_cpa.license_issue_date,
            "expiration_date": your_cpa.license_expiration_date,
            "period_start": period.start_date,
            "period_end": period.end_date,
            "hours_required": period.hours_required,
            "is_transition": period.is_transition_period,
            "days_remaining": period.days_remaining
        })
    
    # Find a CPA with 2025 expiration (old system)
    cpa_2025 = db.query(CPA).filter(CPA.license_expiration_date == "2025-06-30").first()
    if cpa_2025:
        period = service.calculate_compliance_period(cpa_2025)
        test_cases.append({
            "license_number": cpa_2025.license_number,
            "name": cpa_2025.full_name,
            "issue_date": cpa_2025.license_issue_date,
            "expiration_date": cpa_2025.license_expiration_date,
            "period_start": period.start_date,
            "period_end": period.end_date,
            "hours_required": period.hours_required,
            "is_transition": period.is_transition_period,
            "days_remaining": period.days_remaining
        })
    
    return {
        "message": "NH Compliance Rules Test",
        "rule_change_date": service.RULE_CHANGE_DATE,
        "test_cases": test_cases
    }
