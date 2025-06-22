# app/api/ce_broker.py - New API endpoints for CE Broker integration

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
import csv
import io

from app.core.database import get_db
from app.services.jwt_service import get_current_user
from app.models.user import User
from app.models.cpe_record import CPERecord
from app.models.cpa import CPA
from pydantic import BaseModel
from typing import Dict

router = APIRouter(prefix="/api/ce-broker", tags=["CE Broker"])


# Add these Pydantic models at the top of your file
class CEBrokerUpdate(BaseModel):
    course_type: Optional[str] = None
    delivery_method: Optional[str] = None
    subject_areas: Optional[List[str]] = None
    ce_category: Optional[str] = None
    instructional_method: Optional[str] = None
    nasba_sponsor_number: Optional[str] = None
    course_code: Optional[str] = None
    program_level: Optional[str] = None


# Add this new endpoint to your existing router
@router.get("/options")
async def get_ce_broker_options():
    """Get available options for CE Broker form fields"""
    return {
        "course_types": [
            {
                "value": "live",
                "label": "Live (involves live interaction with presenter/host)",
            },
            {
                "value": "anytime",
                "label": "Anytime (is not date, time or location specific)",
            },
        ],
        "delivery_methods": [
            "Computer-Based Training (ie: online courses)",
            "Prerecorded Broadcast",
            "Correspondence",
        ],
        "subject_areas": [
            "Public accounting",
            "Governmental accounting",
            "Public auditing",
            "Governmental auditing",
            "Administrative practices",
            "Social environment of business",
            "Business law",
            "Business management and organization",
            "Finance",
            "Management advisory services",
            "Marketing",
            "Communications",
            "Personal development",
            "Personnel and human resources",
            "Computer science",
            "Economics",
            "Mathematics",
            "Production",
            "Specialized knowledge and its application",
            "Statistics",
            "Taxes",
        ],
        "ce_categories": [
            "General CPE",
            "Professional Ethics CPE",
            "University or college courses",
            "Authoring articles, books, or other publications",
            "Presenting, lecturing, or instructing",
        ],
        "program_levels": ["Basic", "Intermediate", "Advanced"],
    }


# Replace your update_ce_broker_fields function with this enhanced version
@router.post("/update-record/{record_id}")
async def update_ce_broker_fields(
    record_id: int,
    update_data: CEBrokerUpdate,  # Use Pydantic model for type safety
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update CE Broker fields for a specific record"""

    # Get record
    record = (
        db.query(CPERecord)
        .filter(CPERecord.id == record_id, CPERecord.user_id == current_user.id)
        .first()
    )

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # Update fields using Pydantic model
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        if hasattr(record, field):
            setattr(record, field, value)

    # Update readiness status (fix the method name)
    if hasattr(record, "update_ce_broker_readiness"):
        record.update_ce_broker_readiness()
    else:
        # Fallback if method doesn't exist
        record.ce_broker_ready = len(get_missing_fields(record)) == 0

    record.updated_at = datetime.now()

    db.commit()
    db.refresh(record)

    return {
        "success": True,
        "record": record.to_ce_broker_format(),
        "ce_broker_ready": record.ce_broker_ready,
        "missing_fields": get_missing_fields(record),
        "message": "Record updated successfully",
    }


# Enhanced clipboard format function (replace your existing one)
def generate_clipboard_format(ce_broker_data: List[dict]) -> dict:
    """Generate clipboard-friendly format matching the CE Broker 10-step workflow"""

    if not ce_broker_data:
        return {
            "clipboard_text": "No records available for export",
            "total_records": 0,
            "instructions": [],
        }

    clipboard_text = "=== CE BROKER SUBMISSION GUIDE ===\n"
    clipboard_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    clipboard_text += f"Total Records: {len(ce_broker_data)}\n"
    clipboard_text += f"License: New Hampshire CPA\n\n"

    for i, record in enumerate(ce_broker_data, 1):
        clipboard_text += (
            f"📋 COURSE #{i}: {record.get('course_name', 'Untitled Course')}\n"
        )
        clipboard_text += "=" * 60 + "\n\n"

        # Step 4: Course Details
        clipboard_text += "STEP 4 - Course Detail:\n"
        clipboard_text += (
            f"  Course Name: {record.get('course_name', '[NEEDS REVIEW]')}\n"
        )
        clipboard_text += (
            f"  Date Completed: {record.get('completion_date', '[NEEDS REVIEW]')}\n"
        )
        clipboard_text += (
            f"  Course Type: {record.get('course_type', '[NEEDS REVIEW]')}\n"
        )

        # Show delivery method dropdown selection
        delivery = record.get("delivery_method", "[NEEDS REVIEW]")
        clipboard_text += f"  Delivery Method: {delivery}\n"
        clipboard_text += f"  Hours: {record.get('cpe_credits', 0)}\n\n"

        # Step 7: Provider Information
        clipboard_text += "STEP 7 - Provider Information:\n"
        clipboard_text += (
            f"  Provider Name: {record.get('provider_name', '[NEEDS REVIEW]')}\n\n"
        )

        # Step 8: Subject Areas
        clipboard_text += "STEP 8 - Subject Areas (select applicable):\n"
        subject_areas = record.get("subject_areas", [])
        if subject_areas:
            for area in subject_areas:
                clipboard_text += f"  ✓ {area}\n"
        else:
            clipboard_text += "  [NEEDS REVIEW - Select subject areas]\n"
        clipboard_text += "\n"

        # Additional Information
        clipboard_text += "ADDITIONAL INFO:\n"
        clipboard_text += f"  CE Category: {record.get('ce_category', 'General CPE')}\n"
        clipboard_text += (
            f"  Certificate Number: {record.get('certificate_number', 'N/A')}\n"
        )
        clipboard_text += (
            f"  NASBA Sponsor: {record.get('nasba_sponsor_number', 'N/A')}\n"
        )
        clipboard_text += f"  Course Code: {record.get('course_code', 'N/A')}\n"
        clipboard_text += f"  Ethics Hours: {record.get('ethics_credits', 0)}\n"
        clipboard_text += "\n" + "-" * 60 + "\n\n"

    # Summary
    total_cpe = sum(float(r.get("cpe_credits", 0)) for r in ce_broker_data)
    total_ethics = sum(float(r.get("ethics_credits", 0)) for r in ce_broker_data)

    clipboard_text += "📊 SUMMARY:\n"
    clipboard_text += f"Total CPE Hours: {total_cpe}\n"
    clipboard_text += f"Total Ethics Hours: {total_ethics}\n"
    clipboard_text += f"Combined Total: {total_cpe + total_ethics}\n"

    return {
        "clipboard_text": clipboard_text,
        "total_records": len(ce_broker_data),
        "total_cpe_hours": total_cpe,
        "total_ethics_hours": total_ethics,
        "instructions": [
            "1. Copy the course information above",
            "2. Navigate to CE Broker at cebroker.com",
            "3. Click 'Report CE' for your NH CPA license",
            "4. Select 'General CPE' category",
            "5. Paste the course details into each form field",
            "6. Upload certificate PDF if required",
            "7. Submit each course individually",
            "8. Mark as exported when complete",
        ],
    }


@router.get("/export/{license_number}")
async def get_ce_broker_export(
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    format: str = Query("json", description="Export format: json, csv, or clipboard"),
    date_from: Optional[date] = Query(None, description="Filter from date"),
    date_to: Optional[date] = Query(None, description="Filter to date"),
    ready_only: bool = Query(True, description="Only include CE Broker ready records"),
):
    """Export CPE records in CE Broker format"""

    # Verify user owns this license
    if current_user.license_number != license_number:
        raise HTTPException(
            status_code=403,
            detail="You can only export data for your own license number",
        )

    # Build query
    query = db.query(CPERecord).filter(
        CPERecord.cpa_license_number == license_number,
        CPERecord.user_id == current_user.id,
    )

    # Apply filters
    if date_from:
        query = query.filter(CPERecord.completion_date >= date_from)
    if date_to:
        query = query.filter(CPERecord.completion_date <= date_to)
    if ready_only:
        query = query.filter(CPERecord.ce_broker_ready == True)

    # Get records
    records = query.order_by(CPERecord.completion_date.desc()).all()

    if not records:
        raise HTTPException(status_code=404, detail="No CPE records found for export")

    # Convert to CE Broker format
    ce_broker_data = [record.to_ce_broker_format() for record in records]

    # Return based on requested format
    if format == "csv":
        return generate_csv_export(ce_broker_data)
    elif format == "clipboard":
        return generate_clipboard_format(ce_broker_data)
    else:
        return {
            "export_date": datetime.now().isoformat(),
            "license_number": license_number,
            "total_records": len(records),
            "total_cpe_hours": sum(r.cpe_credits or 0 for r in records),
            "total_ethics_hours": sum(r.ethics_credits or 0 for r in records),
            "records": ce_broker_data,
            "export_instructions": {
                "step_1": "Copy the data from each record below",
                "step_2": "Paste into corresponding CE Broker form fields",
                "step_3": "Submit each course individually in CE Broker",
            },
        }


@router.get("/dashboard/{license_number}")
async def get_ce_broker_dashboard(
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get CE Broker readiness dashboard"""

    # Verify user owns this license
    if current_user.license_number != license_number:
        raise HTTPException(
            status_code=403,
            detail="You can only view dashboard for your own license number",
        )

    # Get CPA info
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Get all records
    all_records = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number,
            CPERecord.user_id == current_user.id,
        )
        .all()
    )

    # Categorize records
    ready_records = [r for r in all_records if r.ce_broker_ready]
    needs_review = [r for r in all_records if not r.ce_broker_ready]

    # Calculate totals
    total_cpe = sum(r.cpe_credits or 0 for r in all_records)
    total_ethics = sum(r.ethics_credits or 0 for r in all_records)
    ready_cpe = sum(r.cpe_credits or 0 for r in ready_records)
    ready_ethics = sum(r.ethics_credits or 0 for r in ready_records)

    # Analyze missing fields
    missing_fields_analysis = analyze_missing_fields(needs_review)

    return {
        "cpa": {
            "license_number": license_number,
            "name": cpa.full_name,
            "expiration_date": cpa.license_expiration_date,
        },
        "summary": {
            "total_certificates": len(all_records),
            "ready_for_export": len(ready_records),
            "needs_review": len(needs_review),
            "total_cpe_hours": total_cpe,
            "total_ethics_hours": total_ethics,
            "ready_cpe_hours": ready_cpe,
            "ready_ethics_hours": ready_ethics,
            "completion_percentage": (
                (len(ready_records) / len(all_records) * 100) if all_records else 0
            ),
        },
        "ready_records": [r.to_ce_broker_format() for r in ready_records],
        "needs_review": [
            {**r.to_ce_broker_format(), "missing_fields": get_missing_fields(r)}
            for r in needs_review
        ],
        "missing_fields_analysis": missing_fields_analysis,
        "export_available": len(ready_records) > 0,
    }


@router.post("/update-record/{record_id}")
async def update_ce_broker_fields(
    record_id: int,
    update_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update CE Broker fields for a specific record"""

    # Get record
    record = (
        db.query(CPERecord)
        .filter(CPERecord.id == record_id, CPERecord.user_id == current_user.id)
        .first()
    )

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # Update fields
    allowed_fields = [
        "course_type",
        "delivery_method",
        "subject_areas",
        "ce_category",
        "instructional_method",
        "course_code",
        "program_level",
        "nasba_sponsor_number",
    ]

    for field, value in update_data.items():
        if field in allowed_fields and hasattr(record, field):
            setattr(record, field, value)

    # Update readiness status
    record.update_ce_broker_fields()
    record.updated_at = datetime.now()

    db.commit()
    db.refresh(record)

    return {
        "success": True,
        "record": record.to_ce_broker_format(),
        "ce_broker_ready": record.ce_broker_ready,
    }


@router.post("/mark-exported/{license_number}")
async def mark_records_exported(
    license_number: str,
    record_ids: List[int],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark records as exported to CE Broker"""

    # Verify user owns this license
    if current_user.license_number != license_number:
        raise HTTPException(
            status_code=403,
            detail="You can only update records for your own license number",
        )

    # Update records
    updated_count = (
        db.query(CPERecord)
        .filter(
            CPERecord.id.in_(record_ids),
            CPERecord.user_id == current_user.id,
            CPERecord.cpa_license_number == license_number,
        )
        .update(
            {
                CPERecord.ce_broker_exported: True,
                CPERecord.ce_broker_export_date: datetime.now(),
                CPERecord.updated_at: datetime.now(),
            },
            synchronize_session=False,
        )
    )

    db.commit()

    return {
        "success": True,
        "updated_records": updated_count,
        "export_date": datetime.now().isoformat(),
    }


# Helper functions


def generate_csv_export(ce_broker_data: List[dict]) -> dict:
    """Generate CSV format for CE Broker export"""

    output = io.StringIO()

    if not ce_broker_data:
        return {"csv_content": "", "filename": "ce_broker_export.csv"}

    # Define CSV headers matching CE Broker form fields
    headers = [
        "Course Name",
        "Provider Name",
        "Completion Date",
        "CPE Hours",
        "Ethics Hours",
        "Course Type",
        "Delivery Method",
        "Subject Areas",
        "Instructional Method",
        "NASBA Sponsor",
        "Course Code",
    ]

    writer = csv.writer(output)
    writer.writerow(headers)

    for record in ce_broker_data:
        writer.writerow(
            [
                record.get("course_name", ""),
                record.get("provider_name", ""),
                record.get("completion_date", ""),
                record.get("cpe_hours", ""),
                record.get("ethics_hours", ""),
                record.get("course_type", ""),
                record.get("delivery_method", ""),
                "; ".join(record.get("subject_areas", [])),
                record.get("instructional_method", ""),
                record.get("nasba_sponsor", ""),
                record.get("course_code", ""),
            ]
        )

    csv_content = output.getvalue()
    output.close()

    return {
        "csv_content": csv_content,
        "filename": f"ce_broker_export_{datetime.now().strftime('%Y%m%d')}.csv",
        "total_records": len(ce_broker_data),
    }


def generate_clipboard_format(ce_broker_data: List[dict]) -> dict:
    """Generate clipboard-friendly format for easy copy/paste into CE Broker"""

    clipboard_text = "=== CE BROKER EXPORT ===\n"
    clipboard_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    clipboard_text += f"Total Records: {len(ce_broker_data)}\n\n"

    for i, record in enumerate(ce_broker_data, 1):
        clipboard_text += f"COURSE #{i}\n"
        clipboard_text += "-" * 50 + "\n"
        clipboard_text += f"Course Name: {record.get('course_name', 'N/A')}\n"
        clipboard_text += f"Provider: {record.get('provider_name', 'N/A')}\n"
        clipboard_text += f"Date Completed: {record.get('completion_date', 'N/A')}\n"
        clipboard_text += f"CPE Hours: {record.get('cpe_hours', 'N/A')}\n"
        clipboard_text += f"Ethics Hours: {record.get('ethics_hours', 'N/A')}\n"
        clipboard_text += f"Course Type: {record.get('course_type', 'N/A')}\n"
        clipboard_text += f"Delivery Method: {record.get('delivery_method', 'N/A')}\n"
        clipboard_text += (
            f"Subject Areas: {'; '.join(record.get('subject_areas', []))}\n"
        )
        clipboard_text += (
            f"Instructional Method: {record.get('instructional_method', 'N/A')}\n"
        )
        clipboard_text += f"NASBA Sponsor: {record.get('nasba_sponsor', 'N/A')}\n"
        clipboard_text += f"Course Code: {record.get('course_code', 'N/A')}\n"
        clipboard_text += "\n"

    return {
        "clipboard_text": clipboard_text,
        "total_records": len(ce_broker_data),
        "instructions": [
            "Copy the text above to your clipboard",
            "Navigate to CE Broker reporting page",
            "Paste the course information into each field",
            "Submit each course individually",
        ],
    }


def analyze_missing_fields(records: List[CPERecord]) -> dict:
    """Analyze what fields are missing across records"""

    if not records:
        return {"total_records": 0, "missing_fields": {}}

    missing_analysis = {
        "course_type": 0,
        "delivery_method": 0,
        "subject_areas": 0,
        "instructional_method": 0,
        "course_title": 0,
        "provider": 0,
        "completion_date": 0,
        "cpe_credits": 0,
    }

    for record in records:
        if not record.course_type:
            missing_analysis["course_type"] += 1
        if not record.delivery_method:
            missing_analysis["delivery_method"] += 1
        if not record.subject_areas or len(record.subject_areas) == 0:
            missing_analysis["subject_areas"] += 1
        if not record.instructional_method:
            missing_analysis["instructional_method"] += 1
        if not record.course_title:
            missing_analysis["course_title"] += 1
        if not record.provider:
            missing_analysis["provider"] += 1
        if not record.completion_date:
            missing_analysis["completion_date"] += 1
        if not record.cpe_credits:
            missing_analysis["cpe_credits"] += 1

    return {
        "total_records": len(records),
        "missing_fields": missing_analysis,
        "most_common_missing": max(missing_analysis.items(), key=lambda x: x[1]),
    }


def get_missing_fields(record: CPERecord) -> List[str]:
    """Get list of missing fields for a specific record"""
    missing = []

    if not record.course_title:
        missing.append("course_title")
    if not record.provider:
        missing.append("provider")
    if not record.completion_date:
        missing.append("completion_date")
    if not record.cpe_credits:
        missing.append("cpe_credits")
    if not record.course_type:
        missing.append("course_type")
    if not record.delivery_method:
        missing.append("delivery_method")
    if not record.subject_areas or len(record.subject_areas) == 0:
        missing.append("subject_areas")

    return missing
