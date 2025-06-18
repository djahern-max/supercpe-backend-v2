from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.cpa_import import CPAImportService
from app.services.document_storage import DocumentStorageService
from app.services.stripe_service import StripeService
from app.models.cpa import CPA
from app.models.cpe_record import CPERecord
from app.models.payment import CPASubscription
import tempfile
import os
from datetime import datetime

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
    parse_with_ai: bool = True,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """PREMIUM: Upload and permanently store CPE certificates with Professional Management"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Check for active premium subscription
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    if not has_subscription:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Professional Management subscription required",
                "message": "Upgrade to Professional CPE Management for secure document storage",
                "benefits": [
                    "Secure, centralized document storage",
                    "Organized compliance history",
                    "Instant professional reports",
                    "Streamlined renewal preparation",
                ],
                "pricing": "$58/year - Complete professional management suite",
                "upgrade_url": "/api/payments/create-subscription",
            },
        )

    # Upload and parse document with PERMANENT storage
    storage_service = DocumentStorageService()
    storage_service.db = db
    result = await storage_service.upload_and_parse_certificate(
        file, license_number, parse_with_ai
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "message": "✅ Certificate uploaded and securely stored in Professional Management Suite",
        "file_info": result,
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
        "ai_parsing_enabled": parse_with_ai,
        "parsing_result": result.get("parsing_result"),
        "storage_benefits": {
            "secure_vault": "Documents securely organized in professional management system",
            "ai_analysis": "Smart parsing completed and archived",
            "compliance_tracking": "Added to your comprehensive education record",
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
                "pricing": "$58/year - Complete professional management suite",
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
                    "annual": "$58/year",
                    "monthly": "$6.99/month",
                    "value": "Professional document management for $4.83 per month",
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
async def upload_certificate_free_tier(
    license_number: str,
    file: UploadFile = File(...),
    parse_with_ai: bool = True,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """ENHANCED FREE TIER: License-based uploads - No authentication required"""

    # Verify CPA exists in your CPA database
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(
            status_code=404, detail="CPA license number not found in NH database"
        )

    # Check free upload limit using license number directly
    existing_free_uploads = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number,
            CPERecord.storage_tier == "free",
        )
        .count()
    )

    MAX_FREE_UPLOADS = 10

    if existing_free_uploads >= MAX_FREE_UPLOADS:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Free upload limit reached",
                "message": f"You've used all {MAX_FREE_UPLOADS} free uploads with full functionality",
                "cpa_info": {
                    "license_number": license_number,
                    "name": cpa.full_name,
                    "uploads_completed": existing_free_uploads,
                },
                "upgrade_flow": {
                    "step_1": "Create account with email (required for billing)",
                    "step_2": "Choose Professional plan ($58/year)",
                    "step_3": "All your free uploads will be preserved",
                    "benefit": "Continue with unlimited uploads + premium features",
                },
                "benefits_already_received": [
                    "🤖 AI-powered certificate analysis",
                    "☁️ Secure Digital Ocean Spaces storage",
                    "📊 Real-time compliance tracking",
                    "📋 Professional audit presentation tools",
                ],
                "upgrade_url": f"/upgrade?license={license_number}",
                "pricing": "$58/year - Complete professional management suite",
            },
        )

    try:
        # Step 1: Upload to Digital Ocean Spaces
        storage_service = DocumentStorageService()
        upload_result = await storage_service.upload_cpe_certificate(
            file, license_number
        )

        if not upload_result["success"]:
            raise HTTPException(status_code=500, detail=upload_result["error"])

        # Step 2: Parse with AI (if enabled)
        parsing_result = None
        if parse_with_ai:
            from app.services.vision_service import CPEParsingService
            import tempfile

            vision_service = CPEParsingService()
            file_extension = os.path.splitext(file.filename)[1].lower()

            # Save file temporarily for AI analysis
            with tempfile.NamedTemporaryFile(
                suffix=file_extension, delete=False
            ) as temp_file:
                await file.seek(0)  # Reset file pointer
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                # Parse with AI
                parsing_result = await vision_service.parse_document(
                    temp_file_path, file_extension
                )
            finally:
                # Clean up temp file
                os.unlink(temp_file_path)

        # Step 3: Extract parsed data
        parsed_data = {}
        if parsing_result and parsing_result.get("success"):
            parsed_data = parsing_result.get("parsed_data", {})

        # Step 4: Parse completion date
        completion_date_str = parsed_data.get("completion_date", {}).get("value", "")
        parsed_completion_date = None
        if completion_date_str:
            try:
                parsed_completion_date = datetime.fromisoformat(
                    completion_date_str
                ).date()
            except ValueError:
                try:
                    parsed_completion_date = datetime.strptime(
                        completion_date_str, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    parsed_completion_date = datetime.utcnow().date()

        # Step 5: Create CPE record with FULL functionality
        cpe_record = CPERecord(
            # Using your existing model fields
            cpa_license_number=license_number,
            document_filename=upload_result.get("filename", ""),
            original_filename=file.filename,
            # CPE details from AI parsing
            cpe_credits=float(parsed_data.get("cpe_hours", {}).get("value", 0.0)),
            ethics_credits=float(parsed_data.get("ethics_hours", {}).get("value", 0.0)),
            course_title=parsed_data.get("course_title", {}).get(
                "value", "Unknown Course"
            ),
            provider=parsed_data.get("provider", {}).get("value", "Unknown Provider"),
            completion_date=parsed_completion_date or datetime.utcnow().date(),
            certificate_number=parsed_data.get("certificate_number", {}).get(
                "value", ""
            ),
            # Parsing metadata
            confidence_score=(
                parsing_result.get("confidence_score", 0.0) if parsing_result else 0.0
            ),
            parsing_method="google_vision" if parse_with_ai else "manual",
            raw_text=parsing_result.get("raw_text", "") if parsing_result else "",
            # FREE TIER STORAGE
            storage_tier="free",
            # Verification status
            is_verified=False,
        )

        db.add(cpe_record)
        db.commit()
        db.refresh(cpe_record)

        # Calculate remaining uploads
        remaining_uploads = MAX_FREE_UPLOADS - (existing_free_uploads + 1)

        return {
            "message": "🎉 Certificate uploaded successfully with FULL functionality!",
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
            },
            "free_tier_status": {
                "uploads_used": existing_free_uploads + 1,
                "remaining_uploads": remaining_uploads,
                "max_free_uploads": MAX_FREE_UPLOADS,
                "tier": "ENHANCED FREE - NO REGISTRATION REQUIRED",
            },
            "seamless_upgrade_path": {
                "when_needed": f"After {remaining_uploads} more uploads",
                "process": "Simple email + payment → All data preserved",
                "benefit": "Unlimited uploads + premium features",
                "no_data_loss": "Your 10 certificates will remain accessible",
            },
            "next_steps": [
                f"✅ Certificate #{existing_free_uploads + 1} of {MAX_FREE_UPLOADS} processed",
                "📊 View your compliance dashboard",
                "📋 Generate audit presentation",
                f"⬆️ Upgrade available after {remaining_uploads} more uploads",
            ],
        }

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in license-based free upload: {e}")
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
