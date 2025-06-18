from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.cpa_import import CPAImportService
from app.services.document_storage import DocumentStorageService
from app.services.stripe_service import StripeService
from app.models.cpa import CPA
from app.models.cpe_record import CPERecord

# from app.models.user import Subscription
import tempfile
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/upload", tags=["Upload"])


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
        # Redirect to free tier if no subscription
        return await upload_certificate_enhanced_free(license_number, file, db)

    # Proceed with premium upload (unlimited)
    storage_service = DocumentStorageService()
    storage_service.db = db
    result = await storage_service.upload_and_parse_certificate(
        file, license_number, parse_with_ai=True
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "message": "✅ Certificate uploaded to Premium Management Suite",
        "file_info": result,
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
        "ai_parsing_enabled": True,
        "parsing_result": result.get("parsing_result"),
        "storage_benefits": {
            "unlimited_uploads": "No upload limits with premium subscription",
            "priority_processing": "Premium AI analysis priority",
            "advanced_features": "Full premium feature access",
            "professional_ready": "Generate professional reports anytime",
        },
    }


@router.get("/cpa-documents/{license_number}")
async def list_cpa_documents_premium(
    license_number: str, db: Session = Depends(get_db)
):
    """PREMIUM: List all permanently stored documents"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Check for premium subscription
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    if not has_subscription:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Professional Management feature",
                "message": "Upgrade to access your organized document library",
                "preview_message": "You have analyzed certificates, but they're not permanently organized",
                "upgrade_benefits": [
                    "Access all your CPE certificates anytime",
                    "Professional organization and tracking",
                    "Comprehensive compliance history",
                    "Streamlined renewal preparation",
                ],
            },
        )

    # Get documents from premium storage
    storage_service = DocumentStorageService()
    documents = storage_service.list_cpa_documents(license_number)

    return {
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
        "documents": documents,
        "vault_status": "✅ Professional Management Active",
        "total_documents": len(documents),
    }


@router.get("/cpe-records/{license_number}")
async def get_cpe_records_premium(license_number: str, db: Session = Depends(get_db)):
    """PREMIUM: Get your complete CPE compliance history"""

    from app.models.cpe_record import CPERecord

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Check for premium subscription
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    if not has_subscription:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Professional Management feature required",
                "message": "Upgrade to access your comprehensive compliance history",
                "preview": "You've analyzed certificates but they're not permanently organized",
                "professional_value": "Maintain organized records for efficient practice management",
                "upgrade_benefits": [
                    "Complete CPE compliance history",
                    "Professional compliance reporting",
                    "License renewal tracking",
                    "Organized documentation for any inquiry",
                ],
            },
        )

    # Get premium CPE records
    cpe_records = (
        db.query(CPERecord)
        .filter(CPERecord.cpa_license_number == license_number)
        .order_by(CPERecord.completion_date.desc(), CPERecord.created_at.desc())
        .all()
    )

    # Calculate compliance metrics
    total_credits = sum(record.cpe_credits for record in cpe_records)
    total_ethics = sum(record.ethics_credits for record in cpe_records)

    return {
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
        "summary": {
            "total_records": len(cpe_records),
            "total_cpe_credits": total_credits,
            "total_ethics_credits": total_ethics,
            "average_confidence": (
                sum(r.confidence_score for r in cpe_records) / len(cpe_records)
                if cpe_records
                else 0
            ),
            "vault_status": "✅ Professional Management Active",
        },
        "records": [
            {
                "id": record.id,
                "cpe_credits": record.cpe_credits,
                "ethics_credits": record.ethics_credits,
                "course_title": record.course_title,
                "provider": record.provider,
                "completion_date": record.completion_date,
                "certificate_number": record.certificate_number,
                "confidence_score": record.confidence_score,
                "is_verified": record.is_verified,
                "original_filename": record.original_filename,
                "created_at": record.created_at,
            }
            for record in cpe_records
        ],
    }


# NEW: STEP 3 - Review and Save (Premium)
@router.post("/save-reviewed-certificate/{license_number}")
async def save_reviewed_certificate(
    license_number: str,
    file: UploadFile = File(...),
    cpe_credits: float = 0.0,
    ethics_credits: float = 0.0,
    course_title: str = "",
    provider: str = "",
    completion_date: str = "",  # ISO format: 2025-06-02
    certificate_number: str = "",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """PREMIUM: Save user-reviewed CPE data after analysis and corrections"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Check for premium subscription
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    if not has_subscription:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Professional Management subscription required",
                "message": "Upgrade to save your reviewed CPE data permanently",
                "benefits": [
                    "Save corrected and verified CPE records",
                    "Secure document storage with your data",
                    "Professional compliance tracking",
                    "Generate reports with accurate information",
                ],
                "user_data_note": "Your corrections are ready to save - upgrade to preserve them",
                "pricing": "$10/month - Complete professional management suite",
            },
        )

    # Upload document to permanent storage
    storage_service = DocumentStorageService()
    storage_service.db = db

    # Upload the file (without AI parsing since user already reviewed)
    upload_result = await storage_service.upload_and_parse_certificate(
        file, license_number, parse_with_ai=False  # Skip AI since user provided data
    )

    if not upload_result["success"]:
        raise HTTPException(status_code=500, detail=upload_result["error"])

    # Create CPE record with user-reviewed data
    from app.models.cpe_record import CPERecord
    from datetime import datetime
    import json

    # Parse completion date if provided
    parsed_completion_date = None
    if completion_date:
        try:
            parsed_completion_date = datetime.fromisoformat(completion_date).date()
        except ValueError:
            # Try other common formats
            try:
                parsed_completion_date = datetime.strptime(
                    completion_date, "%Y-%m-%d"
                ).date()
            except ValueError:
                pass  # Leave as None if can't parse

    # Create the CPE record with user's reviewed data
    cpe_record = CPERecord(
        cpa_license_number=license_number,
        document_filename=upload_result["filename"],
        original_filename=upload_result["original_name"],
        cpe_credits=cpe_credits,
        ethics_credits=ethics_credits,
        course_title=course_title if course_title else None,
        provider=provider if provider else None,
        completion_date=parsed_completion_date,
        certificate_number=certificate_number if certificate_number else None,
        confidence_score=1.0,  # 100% confidence since user reviewed
        parsing_method="user_reviewed",
        raw_text=None,  # Not needed since user provided final data
        parsing_notes=json.dumps(
            [
                "✅ User reviewed and confirmed all data",
                "✅ Professional quality assurance complete",
                f"✅ {cpe_credits} CPE credits verified",
                f"✅ Saved to Professional Management system",
            ]
        ),
        is_verified=True,
        verified_by="user_review",
        verification_date=datetime.now(),
    )

    db.add(cpe_record)
    db.commit()
    db.refresh(cpe_record)

    return {
        "message": "✅ Certificate successfully saved to Professional Management Suite",
        "status": "saved",
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
        "file_info": {
            "filename": upload_result["filename"],
            "original_name": upload_result["original_name"],
            "file_url": upload_result["file_url"],
            "upload_date": upload_result["upload_date"],
        },
        "cpe_record": {
            "id": cpe_record.id,
            "cpe_credits": cpe_record.cpe_credits,
            "ethics_credits": cpe_record.ethics_credits,
            "course_title": cpe_record.course_title,
            "provider": cpe_record.provider,
            "completion_date": (
                cpe_record.completion_date.isoformat()
                if cpe_record.completion_date
                else None
            ),
            "certificate_number": cpe_record.certificate_number,
            "confidence_score": cpe_record.confidence_score,
            "verification_status": "✅ User verified",
        },
        "professional_benefits": {
            "document_storage": "Certificate securely stored in your professional vault",
            "data_accuracy": "Your reviewed data saved with 100% confidence",
            "compliance_tracking": "Added to your comprehensive education record",
            "reporting_ready": "Available for professional compliance reports",
        },
        "next_steps": [
            "View your complete CPE history at /api/admin/cpe-records/{license_number}",
            "Generate compliance reports anytime",
            "Upload additional certificates for complete tracking",
        ],
    }


# NEW: FREE TIER - The Freemium Hook
@router.post("/analyze-certificate/{license_number}")
async def analyze_certificate_preview(
    license_number: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """FREE: AI-powered certificate analysis - Preview mode (results not saved)"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Parse document WITHOUT saving (free tier)
    from app.services.vision_service import CPEParsingService
    import tempfile

    vision_service = CPEParsingService()

    # Save file temporarily for analysis only
    file_extension = os.path.splitext(file.filename)[1].lower()
    with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name

    try:
        # Parse with AI (but don't save results)
        parsing_result = await vision_service.parse_document(
            temp_file_path, file_extension
        )

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
                "premium_benefits": [
                    "🗂️ Centralized document management - All certificates in one secure location",
                    "📊 Instant compliance reporting - Professional summaries on demand",
                    "📈 Multi-year tracking - Complete educational history at your fingertips",
                    "🔄 Renewal preparation - Automated compliance monitoring",
                    "📋 Board-ready documentation - Organized records for any inquiry",
                ],
                "social_proof": "Trusted by over 500 practicing CPAs for professional record management",
                "pricing": {
                    "annual": "$120/year",
                    "monthly": "$8/month",
                    "value": "Professional document management for $8.00 per month",
                },
                "efficiency_focus": "Save time and stay organized with centralized CPE management",
                "cta": "Upgrade to Professional Management",
                "guarantee": "30-day satisfaction guarantee",
            },
            "next_steps": {
                "step_1": "✅ Analysis complete - Review the fields below",
                "step_2": "✏️ Edit any incorrect information",
                "step_3": "💾 Upgrade to save permanently with corrections",
                "save_endpoint": "/api/admin/save-reviewed-certificate/{license_number}",
            },
        }

    finally:
        # Clean up temp file
        os.unlink(temp_file_path)


# Replace the upload_certificate_free_tier function in app/api/uploads.py with this:


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

    # Check subscription status
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    # If user has premium subscription, redirect to premium endpoint
    if has_subscription:
        # They can use premium upload instead
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

    remaining_uploads = MAX_FREE_UPLOADS - existing_free_uploads

    # CRITICAL: Check if at limit
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
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file type
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not supported. Please upload PDF or image files.",
        )

    try:
        # ENHANCED FREE: Full functionality including AI analysis and cloud storage
        storage_service = DocumentStorageService()
        storage_service.db = db

        # Process with FULL AI analysis (same as premium)
        result = await storage_service.upload_and_parse_certificate(
            file, license_number, parse_with_ai=True
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        # Extract parsing results
        parsing_result = result.get("parsing_result", {})
        parsed_data = parsing_result.get("parsed_data", {})

        # Create CPE record with FULL functionality
        cpe_record = CPERecord(
            cpa_license_number=license_number,
            cpe_credits=float(parsed_data.get("cpe_hours", 0)),
            ethics_credits=float(parsed_data.get("ethics_hours", 0)),
            course_title=parsed_data.get("course_title", file.filename),
            provider=parsed_data.get("provider", ""),
            completion_date=datetime.strptime(
                parsed_data.get("completion_date", datetime.now().strftime("%Y-%m-%d")),
                "%Y-%m-%d",
            ).date(),
            certificate_number=parsed_data.get("certificate_number", ""),
            confidence_score=parsing_result.get("confidence_score", 85),
            original_filename=file.filename,
            file_size=file.size,
            storage_tier="free",  # Mark as free tier
            is_verified=False,  # User can verify later
            created_at=datetime.now(),
        )

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
                "secure_url": result.get("file_url"),
                "storage_tier": "free",
                "no_account_required": True,
            },
            "compliance_tracking": {
                "cpe_hours_added": cpe_record.cpe_credits,
                "ethics_hours_added": cpe_record.ethics_credits,
                "database_record_id": cpe_record.id,
                "tracked_by_license": license_number,
                "assigned_to_period": "2024-2025",  # Add logic for period detection
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

    return {
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
        "compliance_summary": {
            "total_cpe_hours": total_cpe,
            "total_ethics_hours": total_ethics,
            "total_certificates": len(cpe_records),
            "progress_percentage": min(100, (total_cpe / 120) * 100),
        },
        "upload_status": {
            "free_uploads_used": free_uploads,
            "free_uploads_remaining": max(0, 10 - free_uploads),
            "premium_uploads": premium_uploads,
            "total_storage_used": len(cpe_records),
        },
        "certificates": [
            {
                "id": record.id,
                "course_title": record.course_title,
                "provider": record.provider,
                "cpe_credits": float(record.cpe_credits),
                "completion_date": (
                    record.completion_date.isoformat()
                    if record.completion_date
                    else None
                ),
                "storage_tier": record.storage_tier,
                "confidence": record.confidence_score,
            }
            for record in cpe_records
        ],
        "no_account_required": free_uploads > 0,
        "upgrade_available": free_uploads >= 10,
    }


@router.delete("/certificate/{record_id}")
async def delete_certificate(
    record_id: int, license_number: str, db: Session = Depends(get_db)
):
    """Delete a CPE certificate record and its associated file from Digital Ocean Spaces"""

    # 1. Find the CPE record
    cpe_record = db.query(CPERecord).filter(CPERecord.id == record_id).first()

    if not cpe_record:
        raise HTTPException(status_code=404, detail="Certificate record not found")

    # 2. Verify the license number matches (security check)
    if cpe_record.cpa_license_number != license_number:
        raise HTTPException(
            status_code=403,
            detail="Access denied: License number does not match record owner",
        )

    # 3. Delete the file from Digital Ocean Spaces if it exists
    try:
        storage_service = DocumentStorageService()
        if cpe_record.document_filename:
            # Delete the file from DO Spaces
            delete_result = storage_service.delete_file(cpe_record.document_filename)
            if not delete_result.get("success"):
                # Log the error but continue with database deletion
                logger.error(
                    f"Failed to delete file from storage: {delete_result.get('error')}"
                )
    except Exception as e:
        # Log the error but continue with database deletion
        logger.error(f"Error deleting file from storage: {str(e)}")

    # 4. Delete the record from the database
    db.delete(cpe_record)
    db.commit()

    return {
        "success": True,
        "message": "Certificate deleted successfully",
        "record_id": record_id,
        "license_number": license_number,
    }


# ENHANCED: Increased from previous limits to 10 full-featured uploads
MAX_FREE_UPLOADS = 10


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
