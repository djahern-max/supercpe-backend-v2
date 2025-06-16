from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.cpa import CPA
from app.services.time_window_compliance import TimeWindowComplianceService
from typing import Dict, Any, List, Optional
from datetime import date
from pydantic import BaseModel

router = APIRouter(prefix="/api/time-windows", tags=["Time Window Analysis"])

class WindowAnalysisRequest(BaseModel):
    start_date: date
    end_date: date

@router.get("/{license_number}/available")
async def get_available_windows(
    license_number: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all available compliance windows for a CPA
    Shows past, current, and future periods they can analyze
    """
    # Find the CPA
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")
    
    service = TimeWindowComplianceService()
    windows = service.get_available_windows(cpa)
    
    # Convert to JSON-serializable format
    window_data = []
    for window in windows:
        window_data.append({
            "start_date": window.start_date,
            "end_date": window.end_date,
            "period_type": window.period_type,
            "hours_required": window.hours_required,
            "ethics_required": window.ethics_required,
            "annual_minimum": window.annual_minimum,
            "description": window.window_description,
            "is_historical": window.is_historical,
            "is_current": window.is_current,
            "is_future": window.is_future,
            "days_from_today": (window.end_date - date.today()).days
        })
    
    return {
        "cpa_info": {
            "license_number": cpa.license_number,
            "full_name": cpa.full_name,
            "license_issue_date": cpa.license_issue_date,
            "license_expiration_date": cpa.license_expiration_date
        },
        "available_windows": window_data
    }

@router.post("/{license_number}/analyze")
async def analyze_specific_window(
    license_number: str,
    window_request: WindowAnalysisRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyze compliance for a specific time window
    User can select any start/end date for analysis
    """
    # Find the CPA
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")
    
    service = TimeWindowComplianceService()
    
    # Create a custom window from the request
    from app.services.time_window_compliance import TimeWindow
    
    # Determine period type and requirements based on dates
    period_length_years = (window_request.end_date - window_request.start_date).days / 365.25
    
    if period_length_years <= 2.5:
        period_type = "biennial"
        hours_required = 80
    else:
        period_type = "triennial"
        hours_required = 120
    
    custom_window = TimeWindow(
        start_date=window_request.start_date,
        end_date=window_request.end_date,
        period_type=period_type,
        hours_required=hours_required,
        ethics_required=4,
        annual_minimum=20,
        window_description=f"Custom Analysis: {window_request.start_date.strftime('%b %Y')} - {window_request.end_date.strftime('%b %Y')}",
        is_historical=window_request.end_date < date.today(),
        is_current=window_request.start_date <= date.today() <= window_request.end_date,
        is_future=window_request.start_date > date.today()
    )
    
    # For now, no CPE records (we'll add certificate upload next)
    cpe_records = []
    
    # Analyze the window
    result = service.analyze_window(cpa, custom_window, cpe_records)
    
    return {
        "cpa_info": {
            "license_number": cpa.license_number,
            "full_name": cpa.full_name
        },
        "window_analysis": {
            "window": {
                "start_date": result.window.start_date,
                "end_date": result.window.end_date,
                "description": result.window.window_description,
                "period_type": result.window.period_type,
                "hours_required": result.window.hours_required,
                "ethics_required": result.window.ethics_required
            },
            "compliance_status": {
                "is_compliant": result.is_compliant,
                "compliance_percentage": result.compliance_percentage,
                "total_hours_found": result.total_hours_found,
                "ethics_hours_found": result.ethics_hours_found,
                "missing_hours": result.missing_hours,
                "missing_ethics": result.missing_ethics
            },
            "annual_breakdown": result.annual_breakdown,
            "recommendations": result.recommendations,
            "upload_options": {
                "can_upload_documents": result.can_upload_documents,
                "upload_deadline_passed": result.upload_deadline_passed,
                "message": "Upload certificates to analyze compliance" if not result.is_compliant else "Period is compliant"
            }
        }
    }

@router.get("/{license_number}/current-period")
async def get_current_period_analysis(
    license_number: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Quick endpoint to get current period analysis
    """
    # Find the CPA
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")
    
    service = TimeWindowComplianceService()
    windows = service.get_available_windows(cpa)
    
    # Find current window
    current_window = next((w for w in windows if w.is_current), None)
    if not current_window:
        raise HTTPException(status_code=404, detail="No current compliance period found")
    
    # Analyze current window
    cpe_records = []  # Will add certificate records later
    result = service.analyze_window(cpa, current_window, cpe_records)
    
    return {
        "cpa_info": {
            "license_number": cpa.license_number,
            "full_name": cpa.full_name
        },
        "current_period": {
            "start_date": current_window.start_date,
            "end_date": current_window.end_date,
            "days_remaining": (current_window.end_date - date.today()).days,
            "hours_required": current_window.hours_required,
            "compliance_status": {
                "is_compliant": result.is_compliant,
                "total_hours_found": result.total_hours_found,
                "missing_hours": result.missing_hours,
                "recommendations": result.recommendations[:3]  # Top 3 recommendations
            }
        }
    }
