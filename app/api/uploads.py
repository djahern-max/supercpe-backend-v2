# app/api/uploads.py - CLEANED AND FIXED VERSION

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.cpa_import import CPAImportService
from app.services.document_storage import DocumentStorageService
from app.services.stripe_service import StripeService
from app.models.cpa import CPA
from app.models.cpe_record import CPERecord
import tempfile
import os
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload", tags=["Upload"])

# CONSTANTS - Define at top to avoid NameError
MAX_FREE_UPLOADS = 10
ALLOWED_FILE_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"]

# ===== UTILITY FUNCTIONS =====


def validate_file(file: UploadFile):
    """Validate uploaded file type and content"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not supported. Please upload PDF or image files.",
        )


async def process_with_ai(file: UploadFile, license_number: str):
    """Common AI processing logic"""
    from app.services.vision_service import CPEParsingService

    vision_service = CPEParsingService()
    file_extension = os.path.splitext(file.filename)[1].lower()

    # Save file temporarily for AI analysis
    with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
        await file.seek(0)  # Reset file pointer
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name

    try:
        # Parse with AI
        parsing_result = await vision_service.parse_document(
            temp_file_path, file_extension
        )
        return parsing_result
    finally:
        # Clean up temp file
        os.unlink(temp_file_path)


def create_cpe_record_from_ai(
    parsing_result: dict,
    file: UploadFile,
    license_number: str,
    storage_tier: str = "free",
):
    """Create CPERecord from AI parsing results"""
    parsed_data = parsing_result.get("parsed_data", {}) if parsing_result else {}

    # Parse completion date
    completion_date_str = parsed_data.get("completion_date", {}).get("value", "")
    parsed_completion_date = None
    if completion_date_str:
        try:
            parsed_completion_date = datetime.fromisoformat(completion_date_str).date()
        except ValueError:
            try:
                parsed_completion_date = datetime.strptime(
                    completion_date_str, "%Y-%m-%d"
                ).date()
            except ValueError:
                parsed_completion_date = datetime.utcnow().date()

    return CPERecord(
        cpa_license_number=license_number,
        original_filename=file.filename,
        cpe_credits=float(parsed_data.get("cpe_hours", {}).get("value", 0.0)),
        ethics_credits=float(parsed_data.get("ethics_hours", {}).get("value", 0.0)),
        course_title=parsed_data.get("course_title", {}).get("value", "Unknown Course"),
        provider=parsed_data.get("provider", {}).get("value", "Unknown Provider"),
        completion_date=parsed_completion_date or datetime.utcnow().date(),
        certificate_number=parsed_data.get("certificate_number", {}).get("value", ""),
        confidence_score=(
            parsing_result.get("confidence_score", 0.0) if parsing_result else 0.0
        ),
        parsing_method="google_vision",
        raw_text=parsing_result.get("raw_text", "") if parsing_result else "",
        storage_tier=storage_tier,
        is_verified=False,
        created_at=datetime.now(),
    )


# ===== ADMIN ENDPOINTS =====


@router.post("/upload-cpa-list")
async def upload_monthly_cpa_list(
    file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Upload monthly OPLC CPA list (Excel file)"""
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400, detail="File must be Excel format (.xlsx or .xls)"
        )

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name

    try:
        # Import CPAs
        import_service = CPAImportService(db)
        results = import_service.import_from_excel(tmp_file_path)

        return {
            "message": "CPA list uploaded successfully",
            "results": results,
            "filename": file.filename,
        }
    finally:
        # Clean up temp file
        os.unlink(tmp_file_path)


# ===== STATUS ENDPOINTS =====


@router.get("/free-tier-status/{license_number}")
async def get_free_tier_status(license_number: str, db: Session = Depends(get_db)):
    """Get current free tier upload status"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA license number not found")

    # Count existing free uploads for this license
    existing_free_uploads = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number,
            CPERecord.storage_tier == "free",
        )
        .count()
    )

    remaining_uploads = max(0, MAX_FREE_UPLOADS - existing_free_uploads)

    # Check if user has premium subscription
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    return {
        "license_number": license_number,
        "cpa_name": cpa.full_name,
        "uploads_used": existing_free_uploads,
        "uploads_remaining": remaining_uploads,
        "max_free_uploads": MAX_FREE_UPLOADS,
        "at_limit": existing_free_uploads >= MAX_FREE_UPLOADS,
        "has_premium_subscription": has_subscription,
        "status": (
            "premium"
            if has_subscription
            else ("available" if remaining_uploads > 0 else "limit_reached")
        ),
        "upgrade_required": existing_free_uploads >= MAX_FREE_UPLOADS
        and not has_subscription,
        "message": (
            f"✅ {remaining_uploads} uploads remaining with full functionality"
            if remaining_uploads > 0
            else "🎯 Time to upgrade! You've used all 10 free uploads."
        ),
    }


@router.get("/compliance-dashboard/{license_number}")
async def get_compliance_dashboard_free(
    license_number: str, db: Session = Depends(get_db)
):
    """Get compliance dashboard for any license number - no auth required"""

    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA license number not found")

    # Get all CPE records for this license (both free and premium)
    cpe_records = (
        db.query(CPERecord)
        .filter(CPERecord.cpa_license_number == license_number)
        .order_by(CPERecord.completion_date.desc())
        .all()
    )

    # Calculate totals
    total_cpe = sum(float(record.cpe_credits) for record in cpe_records)
    total_ethics = sum(float(record.ethics_credits) for record in cpe_records)

    free_uploads = len([r for r in cpe_records if r.storage_tier == "free"])
    premium_uploads = len([r for r in cpe_records if r.storage_tier == "premium"])

    # Get subscription status
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    return {
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
        "summary": {
            "total_records": len(cpe_records),
            "total_cpe_credits": total_cpe,
            "total_ethics_credits": total_ethics,
            "free_uploads_used": free_uploads,
            "premium_uploads": premium_uploads,
            "subscription_status": "active" if has_subscription else "free",
        },
        "free_tier_status": {
            "uploads_used": free_uploads,
            "uploads_remaining": max(0, MAX_FREE_UPLOADS - free_uploads),
            "max_free_uploads": MAX_FREE_UPLOADS,
            "at_limit": free_uploads >= MAX_FREE_UPLOADS,
        },
        "upload_status": {  # For compatibility with your frontend
            "free_uploads_used": free_uploads,
            "free_uploads_remaining": max(0, MAX_FREE_UPLOADS - free_uploads),
            "premium_uploads": premium_uploads,
            "has_subscription": has_subscription,
        },
        "compliance_summary": {  # For compatibility with your frontend
            "total_cpe_hours": total_cpe,
            "total_ethics_hours": total_ethics,
            "total_certificates": len(cpe_records),
        },
        "certificates": [  # For compatibility with your frontend
            {
                "id": record.id,
                "cpe_credits": record.cpe_credits,
                "ethics_credits": record.ethics_credits,
                "course_title": record.course_title,
                "provider": record.provider,
                "completion_date": (
                    record.completion_date.isoformat()
                    if record.completion_date
                    else None
                ),
                "certificate_number": record.certificate_number,
                "confidence_score": record.confidence_score,
                "is_verified": record.is_verified,
                "original_filename": record.original_filename,
                "storage_tier": record.storage_tier,
                "created_at": (
                    record.created_at.isoformat() if record.created_at else None
                ),
            }
            for record in cpe_records
        ],
    }


# ===== UPLOAD ENDPOINTS =====


@router.post("/upload-certificate-free/{license_number}")
async def upload_certificate_enhanced_free(
    license_number: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """ENHANCED FREE: Upload with FULL functionality for first 10 certificates"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA license number not found")

    # Check subscription status first
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    # If user has premium subscription, use premium flow
    if has_subscription:
        return await upload_cpe_certificate_premium(license_number, file, db)

    # Count existing free uploads
    existing_free_uploads = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number,
            CPERecord.storage_tier == "free",
        )
        .count()
    )

    # Check if at limit
    if existing_free_uploads >= MAX_FREE_UPLOADS:
        raise HTTPException(
            status_code=402,  # Payment Required
            detail={
                "error": "Free upload limit reached",
                "message": f"You've used all {MAX_FREE_UPLOADS} enhanced free uploads",
                "uploads_used": existing_free_uploads,
                "max_uploads": MAX_FREE_UPLOADS,
                "upgrade_required": True,
                "subscription_options": {
                    "monthly": {
                        "price": "$10/month",
                        "description": "Unlimited uploads + premium features",
                    },
                    "annual": {
                        "price": "$96/year",
                        "description": "Unlimited uploads + premium features (2 months free!)",
                        "savings": "20% savings",
                    },
                },
                "benefits_unlocked": [
                    "Unlimited certificate uploads",
                    "Advanced compliance reports",
                    "Priority AI processing",
                    "Secure document vault",
                    "Multi-year compliance tracking",
                    "Professional audit presentations",
                ],
                "call_to_action": "Upgrade now to continue managing your CPE compliance",
            },
        )

    # Validate file
    validate_file(file)

    try:
        # Step 1: Upload to storage using your existing method
        storage_service = DocumentStorageService()
        upload_result = await storage_service.upload_cpe_certificate(
            file, license_number
        )

        if not upload_result["success"]:
            raise HTTPException(status_code=500, detail=upload_result["error"])

        # Step 2: Process with AI
        parsing_result = await process_with_ai(file, license_number)

        # Step 3: Create CPE record
        cpe_record = create_cpe_record_from_ai(
            parsing_result, file, license_number, "free"
        )
        cpe_record.document_filename = upload_result.get("filename", "")

        db.add(cpe_record)
        db.commit()
        db.refresh(cpe_record)

        # Calculate new status
        new_upload_count = existing_free_uploads + 1
        remaining_after_upload = MAX_FREE_UPLOADS - new_upload_count

        return {
            "success": True,
            "message": f"✅ Certificate {new_upload_count}/{MAX_FREE_UPLOADS} processed with full functionality!",
            "filename": file.filename,
            "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
            "parsing_result": parsing_result,
            "storage_info": {
                "uploaded_to_digital_ocean": True,
                "permanent_storage": True,
                "secure_url": upload_result.get("file_url"),
                "storage_tier": "free",
                "no_account_required": True,
            },
            "compliance_tracking": {
                "cpe_hours_added": cpe_record.cpe_credits,
                "ethics_hours_added": cpe_record.ethics_credits,
                "database_record_id": cpe_record.id,
                "tracked_by_license": license_number,
                "assigned_to_period": "2024-2025",
            },
            "free_tier_status": {
                "uploads_used": new_upload_count,
                "remaining_uploads": remaining_after_upload,
                "max_free_uploads": MAX_FREE_UPLOADS,
                "tier": "ENHANCED FREE - NO REGISTRATION REQUIRED",
                "upgrade_needed_after": remaining_after_upload == 0,
            },
            "upgrade_preview": (
                {
                    "trigger_after": remaining_after_upload,
                    "process": "Simple email + payment → All data preserved",
                    "benefit": "Unlimited uploads + premium features",
                    "no_data_loss": f"Your {new_upload_count} certificates will remain accessible",
                }
                if remaining_after_upload <= 2
                else None
            ),
            "next_steps": [
                f"✅ Certificate #{new_upload_count} of {MAX_FREE_UPLOADS} processed",
                "📊 View your compliance dashboard",
                "📋 Generate audit presentation",
                (
                    f"⬆️ Upgrade available after {remaining_after_upload} more uploads"
                    if remaining_after_upload > 0
                    else "⬆️ Ready to upgrade for unlimited uploads!"
                ),
            ],
        }

    except Exception as e:
        logger.error(f"Error in enhanced free upload: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload-cpe-certificate/{license_number}")
async def upload_cpe_certificate_premium(
    license_number: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """PREMIUM: Unlimited uploads for subscribers"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Check for premium subscription
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    if not has_subscription:
        # If no subscription, redirect to free tier (but don't create circular calls)
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Premium subscription required",
                "message": "This endpoint requires an active premium subscription",
                "redirect_to": f"/api/upload/upload-certificate-free/{license_number}",
                "subscription_options": {
                    "monthly": {"price": "$10/month"},
                    "annual": {"price": "$96/year", "savings": "20% savings"},
                },
            },
        )

    # Validate file
    validate_file(file)

    try:
        # Step 1: Upload to storage
        storage_service = DocumentStorageService()
        upload_result = await storage_service.upload_cpe_certificate(
            file, license_number
        )

        if not upload_result["success"]:
            raise HTTPException(status_code=500, detail=upload_result["error"])

        # Step 2: Process with AI
        parsing_result = await process_with_ai(file, license_number)

        # Step 3: Create CPE record with premium tier
        cpe_record = create_cpe_record_from_ai(
            parsing_result, file, license_number, "premium"
        )
        cpe_record.document_filename = upload_result.get("filename", "")

        db.add(cpe_record)
        db.commit()
        db.refresh(cpe_record)

        return {
            "message": "✅ Certificate uploaded to Premium Management Suite",
            "file_info": upload_result,
            "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
            "ai_parsing_enabled": True,
            "parsing_result": parsing_result,
            "storage_benefits": {
                "unlimited_uploads": "No upload limits with premium subscription",
                "priority_processing": "Premium AI analysis priority",
                "advanced_features": "Full premium feature access",
                "professional_ready": "Generate professional reports anytime",
            },
        }

    except Exception as e:
        logger.error(f"Error in premium upload: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ===== ANALYSIS ENDPOINTS =====


@router.post("/analyze-certificate/{license_number}")
async def analyze_certificate_preview(
    license_number: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """FREE: AI-powered certificate analysis - Preview mode (results not saved)"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Validate file
    validate_file(file)

    try:
        # Process with AI (but don't save results)
        parsing_result = await process_with_ai(file, license_number)

        return {
            "message": "🎯 Certificate analyzed successfully with AI",
            "filename": file.filename,
            "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
            "parsing_result": parsing_result,
            "ai_analysis_quality": {
                "confidence": f"{parsing_result.get('confidence_score', 0):.1%}",
                "fields_detected": len(
                    [
                        f
                        for f in parsing_result.get("parsed_data", {}).values()
                        if isinstance(f, dict) and f.get("confidence", 0) > 0.5
                    ]
                ),
                "extraction_notes": "✅ Professional-grade AI analysis complete",
            },
            "storage_status": {
                "current_tier": "FREE ANALYSIS",
                "document_saved": False,
                "analysis_saved": False,
                "note": "Results are temporary - upgrade for permanent organization",
            },
            "upgrade_opportunity": {
                "headline": "📋 Professional CPE Management Suite",
                "value_proposition": "Streamline your continuing education with organized, accessible records",
                "pricing": {"annual": "$96/year", "monthly": "$10/month"},
                "cta": "Upgrade to Professional Management",
            },
        }

    except Exception as e:
        logger.error(f"Error in certificate analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ===== CRUD ENDPOINTS =====


@router.delete("/certificate/{record_id}")
async def delete_certificate(
    record_id: int, license_number: str, db: Session = Depends(get_db)
):
    """Delete a CPE certificate record and its associated file"""

    # Find the CPE record
    cpe_record = db.query(CPERecord).filter(CPERecord.id == record_id).first()
    if not cpe_record:
        raise HTTPException(status_code=404, detail="Certificate record not found")

    # Verify the license number matches (security check)
    if cpe_record.cpa_license_number != license_number:
        raise HTTPException(
            status_code=403,
            detail="Access denied: License number does not match record owner",
        )

    # Delete the file from storage if it exists
    try:
        if cpe_record.document_filename:
            storage_service = DocumentStorageService()
            # Note: You'll need to add delete_file method to DocumentStorageService
            # delete_result = storage_service.delete_file(cpe_record.document_filename)
    except Exception as e:
        logger.error(f"Error deleting file from storage: {str(e)}")

    # Delete the record from the database
    db.delete(cpe_record)
    db.commit()

    return {
        "success": True,
        "message": "Certificate deleted successfully",
        "record_id": record_id,
        "license_number": license_number,
    }
