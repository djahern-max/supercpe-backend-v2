from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.cpa import CPA
from app.services.nh_compliance import NHComplianceService, get_cpa_compliance_dashboard
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
        test_cases.append(
            {
                "license_number": "07308",
                "name": your_cpa.full_name,
                "issue_date": your_cpa.license_issue_date,
                "expiration_date": your_cpa.license_expiration_date,
                "period_start": period.start_date,
                "period_end": period.end_date,
                "hours_required": period.hours_required,
                "is_transition": period.is_transition_period,
                "days_remaining": period.days_remaining,
            }
        )

    # Find a CPA with 2025 expiration (old system)
    cpa_2025 = db.query(CPA).filter(CPA.license_expiration_date == "2025-06-30").first()
    if cpa_2025:
        period = service.calculate_compliance_period(cpa_2025)
        test_cases.append(
            {
                "license_number": cpa_2025.license_number,
                "name": cpa_2025.full_name,
                "issue_date": cpa_2025.license_issue_date,
                "expiration_date": cpa_2025.license_expiration_date,
                "period_start": period.start_date,
                "period_end": period.end_date,
                "hours_required": period.hours_required,
                "is_transition": period.is_transition_period,
                "days_remaining": period.days_remaining,
            }
        )

    return {
        "message": "NH Compliance Rules Test",
        "rule_change_date": service.RULE_CHANGE_DATE,
        "test_cases": test_cases,
    }


@router.get("/{license_number}/dashboard")
async def get_enhanced_compliance_dashboard(
    license_number: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive compliance dashboard with personalized explanations
    This endpoint provides everything a CPA needs to understand their renewal requirements
    """

    # Find the CPA
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Get CPE records if available (implement when you add CPE tracking)
    # For now, using empty list - dashboard will explain what's needed
    cpe_records = []
    # TODO: Query actual CPE records when certificate upload is implemented
    # cpe_records = db.query(CPERecord).filter(CPERecord.cpa_license_number == license_number).all()

    # Generate enhanced dashboard
    from app.services.nh_compliance import get_enhanced_cpa_dashboard

    dashboard = get_enhanced_cpa_dashboard(cpa, cpe_records)

    return dashboard


@router.get("/{license_number}/quick-status")
async def get_quick_compliance_status(
    license_number: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get quick compliance status - useful for search results or list views
    """

    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    from app.services.nh_compliance import EnhancedNHComplianceService

    service = EnhancedNHComplianceService()

    period = service.calculate_compliance_period(cpa)

    # Determine status color and message
    if period.days_remaining <= 30:
        status_level = "critical"
        status_message = "Renewal due soon"
    elif period.days_remaining <= 90:
        status_level = "warning"
        status_message = "Renewal approaching"
    else:
        status_level = "good"
        status_message = "On track"

    return {
        "license_number": cpa.license_number,
        "full_name": cpa.full_name,
        "renewal_date": period.end_date,
        "days_remaining": period.days_remaining,
        "status_level": status_level,
        "status_message": status_message,
        "renewal_pattern": period.renewal_pattern,
        "requirements_summary": f"{period.hours_required} hours + {period.ethics_required} ethics over 2 years",
    }


@router.get("/rules/explanation")
async def get_nh_rules_explanation():
    """
    Get detailed explanation of NH CPA renewal rules
    Educational endpoint for understanding the current system
    """

    return {
        "system_overview": {
            "title": "New Hampshire CPA Renewal System (2023 - Present)",
            "summary": "All NH CPAs are now on 2-year renewal cycles with reduced CPE requirements",
            "effective_date": "February 22, 2023",
        },
        "current_requirements": {
            "renewal_cycle": "2 years",
            "total_cpe_hours": 80,
            "ethics_hours": 4,
            "annual_minimum": 20,
            "legal_authority": "RSA 310:8",
        },
        "renewal_dates": {
            "existing_cpas": {
                "description": "CPAs licensed before February 2023",
                "renewal_date": "June 30th (maintained)",
                "pattern": "Every 2 years on June 30th",
            },
            "new_cpas": {
                "description": "CPAs licensed after February 2023",
                "renewal_date": "Anniversary month of license issuance",
                "pattern": "Every 2 years on anniversary month",
            },
        },
        "rule_changes": {
            "what_changed": [
                "Renewal cycle reduced from 3 years to 2 years",
                "Total CPE hours reduced from 120 to 80",
                "New CPAs get anniversary-based renewals",
            ],
            "what_stayed_same": [
                "20 hours minimum per year requirement",
                "4 hours ethics requirement per renewal period",
                "June 30th dates for existing CPAs",
            ],
        },
        "compliance_examples": [
            {
                "scenario": "CPA licensed in 2010, expires June 2027",
                "category": "Existing CPA",
                "renewal_pattern": "June 30th every 2 years",
                "current_period": "July 1, 2025 - June 30, 2027",
                "requirements": "80 total hours, 4 ethics hours, 20 minimum each year",
            },
            {
                "scenario": "CPA licensed in March 2024, expires March 2026",
                "category": "New CPA",
                "renewal_pattern": "March every 2 years",
                "current_period": "March 2024 - March 2026",
                "requirements": "80 total hours, 4 ethics hours, 20 minimum each year",
            },
        ],
        "faqs": [
            {
                "question": "Do I still need 20 hours per year in a 2-year system?",
                "answer": "Yes, the annual 20-hour minimum is still required each year, even within the 2-year cycle.",
            },
            {
                "question": "When do I need to complete ethics hours?",
                "answer": "4 hours of ethics CPE are required once per 2-year renewal period, anytime during that period.",
            },
            {
                "question": "Why did my renewal change from 3 years to 2 years?",
                "answer": "RSA 310:8 standardized all NH professional licenses to 2-year terms. This applies to all CPAs.",
            },
            {
                "question": "Will my June 30th renewal date change?",
                "answer": "No, if you were licensed before February 2023, you keep June 30th renewal dates.",
            },
        ],
    }
