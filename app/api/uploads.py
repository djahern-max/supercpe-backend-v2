from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.cpa_import import CPAImportService
from app.services.document_storage import DocumentStorageService
from app.services.stripe_service import StripeService
from app.models.cpa import CPA
from app.models.payment import CPASubscription
import tempfile
import os

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


# Keep the old endpoint name for backwards compatibility but redirect to new strategy
@router.post("/test-ai-parsing/{license_number}")
async def test_ai_parsing_redirect(
    license_number: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """DEPRECATED: Use /analyze-certificate/ instead"""
    return await analyze_certificate_preview(license_number, file, db)
