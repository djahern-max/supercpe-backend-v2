# app/api/uploads.py - CLEANED AND FIXED VERSION

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
    Query,
)
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
from fastapi.responses import RedirectResponse
from botocore.exceptions import ClientError


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

    # Transform CPE records to match frontend expectations
    certificates = []
    for record in cpe_records:
        certificates.append(
            {
                "id": record.id,
                "course_title": record.course_title or "Untitled Course",
                "provider": record.provider or "Unknown Provider",
                "completion_date": (
                    record.completion_date.isoformat()
                    if record.completion_date
                    else None
                ),
                "cpe_credits": float(record.cpe_credits),
                "ethics_credits": float(record.ethics_credits),
                "certificate_number": record.certificate_number or "",
                "confidence": record.confidence_score or 0.0,
                "storage_tier": record.storage_tier,
                "is_verified": record.is_verified or False,
            }
        )

    # FIXED: Return data in the EXACT format ProfessionalCPEDashboard expects
    return {
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
        # THIS IS THE KEY FIX - Dashboard expects "compliance_summary" not "summary"
        "compliance_summary": {
            # Dashboard expects "total_cpe_hours" not "total_cpe_credits"
            "total_cpe_hours": total_cpe,
            "total_ethics_hours": total_ethics,
            "total_certificates": len(cpe_records),
        },
        # Also keep the certificates data that the dashboard needs
        "certificates": certificates,
        # Upload status for freemium functionality
        "upload_status": {
            "free_uploads_used": free_uploads,
            "free_uploads_remaining": max(0, MAX_FREE_UPLOADS - free_uploads),
            "max_free_uploads": MAX_FREE_UPLOADS,
            "at_limit": free_uploads >= MAX_FREE_UPLOADS,
            "has_subscription": has_subscription,
        },
        # Additional metadata
        "summary": {
            "total_records": len(cpe_records),
            "total_cpe_credits": total_cpe,  # Keep this for backward compatibility
            "total_ethics_credits": total_ethics,
            "free_uploads_used": free_uploads,
            "premium_uploads": premium_uploads,
            "subscription_status": "active" if has_subscription else "free",
        },
    }


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
                    "step_2": "Choose Professional plan ($96/year)",
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
                "pricing": "$96/year - Complete professional management suite",
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

        # Step 2: Parse with AI (if enabled) - FIXED PARSING
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
                # DEBUG: Print parsing result
                print(f"AI Parsing Result: {parsing_result}")
            finally:
                # Clean up temp file
                os.unlink(temp_file_path)

        # Step 3: Extract parsed data - FIXED EXTRACTION
        parsed_data = {}
        cpe_hours = 0.0
        ethics_hours = 0.0
        course_title = "Unknown Course"
        provider = "Unknown Provider"
        certificate_number = ""

        if parsing_result and parsing_result.get("success"):
            parsed_data = parsing_result.get("parsed_data", {})
            print(f"Parsed Data: {parsed_data}")

            # FIXED: Better extraction of CPE hours
            if "cpe_hours" in parsed_data:
                cpe_val = parsed_data["cpe_hours"]
                if isinstance(cpe_val, dict):
                    cpe_hours = float(cpe_val.get("value", 0.0))
                else:
                    cpe_hours = float(cpe_val) if cpe_val else 0.0

            # FIXED: Better extraction of ethics hours
            if "ethics_hours" in parsed_data:
                ethics_val = parsed_data["ethics_hours"]
                if isinstance(ethics_val, dict):
                    ethics_hours = float(ethics_val.get("value", 0.0))
                else:
                    ethics_hours = float(ethics_val) if ethics_val else 0.0

            # FIXED: Better extraction of course title
            if "course_title" in parsed_data:
                title_val = parsed_data["course_title"]
                if isinstance(title_val, dict):
                    course_title = title_val.get("value", file.filename)
                else:
                    course_title = str(title_val) if title_val else file.filename

            # FIXED: Better extraction of provider
            if "provider" in parsed_data:
                provider_val = parsed_data["provider"]
                if isinstance(provider_val, dict):
                    provider = provider_val.get("value", "Unknown Provider")
                else:
                    provider = str(provider_val) if provider_val else "Unknown Provider"

            # FIXED: Better extraction of certificate number
            if "certificate_number" in parsed_data:
                cert_val = parsed_data["certificate_number"]
                if isinstance(cert_val, dict):
                    certificate_number = cert_val.get("value", "")
                else:
                    certificate_number = str(cert_val) if cert_val else ""

        # DEBUG: Print extracted values
        print(f"Extracted CPE Hours: {cpe_hours}")
        print(f"Extracted Ethics Hours: {ethics_hours}")
        print(f"Course Title: {course_title}")

        # Step 4: Parse completion date - FIXED
        completion_date_str = ""
        if "completion_date" in parsed_data:
            date_val = parsed_data["completion_date"]
            if isinstance(date_val, dict):
                completion_date_str = date_val.get("value", "")
            else:
                completion_date_str = str(date_val) if date_val else ""

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
        else:
            parsed_completion_date = datetime.utcnow().date()

        # Step 5: Create CPE record with FIXED values
        cpe_record = CPERecord(
            cpa_license_number=license_number,
            document_filename=upload_result.get("filename", ""),
            original_filename=file.filename,
            # FIXED: Use properly extracted values
            cpe_credits=cpe_hours,  # This should now have actual hours
            ethics_credits=ethics_hours,  # This should now have actual ethics hours
            course_title=course_title,
            provider=provider,
            completion_date=parsed_completion_date,
            certificate_number=certificate_number,
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

        # DEBUG: Print saved record
        print(
            f"Saved CPE Record - ID: {cpe_record.id}, CPE: {cpe_record.cpe_credits}, Ethics: {cpe_record.ethics_credits}"
        )

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
                "no_data_loss": f"Your {existing_free_uploads + 1} certificates will remain accessible",
            },
            "next_steps": [
                f"✅ Certificate #{existing_free_uploads + 1} of {MAX_FREE_UPLOADS} processed",
                "📊 View your compliance dashboard",
                "📋 Generate audit presentation",
                (
                    f"⬆️ Upgrade available after {remaining_uploads} more uploads"
                    if remaining_uploads > 0
                    else "⬆️ Ready to upgrade for unlimited uploads!"
                ),
            ],
        }

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in license-based free upload: {e}")
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

    storage_deletion_result = None
    storage_service = DocumentStorageService()

    # Step 1: Delete the file from Digital Ocean Spaces if it exists
    try:
        if cpe_record.document_filename:
            logger.info(f"Deleting file from storage: {cpe_record.document_filename}")
            storage_deletion_result = storage_service.delete_file(
                cpe_record.document_filename
            )

            if not storage_deletion_result["success"]:
                logger.warning(
                    f"Failed to delete file from storage: {storage_deletion_result.get('error')}"
                )
                # Continue with database deletion even if file deletion fails
        else:
            logger.info(f"No file to delete for certificate {record_id}")
            storage_deletion_result = {
                "success": True,
                "message": "No file associated with record",
            }

    except Exception as storage_error:
        logger.error(f"Error deleting file from storage: {storage_error}")
        # Continue with database deletion even if storage deletion fails
        storage_deletion_result = {"success": False, "error": str(storage_error)}

    # Step 2: Delete the database record
    try:
        logger.info(f"Deleting database record for certificate {record_id}")

        # Store certificate info for response
        certificate_info = {
            "id": cpe_record.id,
            "course_title": cpe_record.course_title,
            "cpe_credits": cpe_record.cpe_credits,
            "completion_date": (
                cpe_record.completion_date.isoformat()
                if cpe_record.completion_date
                else None
            ),
            "provider": cpe_record.provider,
            "document_filename": cpe_record.document_filename,
        }

        # Delete from database
        db.delete(cpe_record)
        db.commit()

        logger.info(f"Successfully deleted certificate {record_id} from database")

        return {
            "success": True,
            "message": "Certificate deleted successfully",
            "certificate_id": record_id,
            "certificate_info": certificate_info,
            "storage_deletion": storage_deletion_result,
            "database_deletion": {
                "success": True,
                "message": "Record removed from database",
            },
        }

    except Exception as db_error:
        logger.error(f"Error deleting certificate from database: {db_error}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete certificate from database: {str(db_error)}",
        )


# Also, make sure your DocumentStorageService.delete_file method is working properly.
# Your delete_file method looks correct, but let me provide an enhanced version:

# In app/services/document_storage.py, replace the delete_file method with this enhanced version:


def delete_file(self, file_key: str) -> dict:
    """Delete a file from Digital Ocean Spaces"""
    try:
        logger.info(f"Attempting to delete file: {file_key}")

        # Check if file exists first
        try:
            self.client.head_object(Bucket=self.bucket, Key=file_key)
            logger.info(f"File exists in storage: {file_key}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                # File doesn't exist, but we'll consider this a successful deletion
                logger.info(f"File already doesn't exist in storage: {file_key}")
                return {
                    "success": True,
                    "message": "File does not exist in storage (already deleted)",
                    "file_key": file_key,
                }
            else:
                # Some other error occurred while checking
                logger.error(f"Error checking file existence: {e}")
                raise

        # Delete the file
        logger.info(f"Deleting file from Digital Ocean Spaces: {file_key}")
        self.client.delete_object(Bucket=self.bucket, Key=file_key)

        # Verify deletion by trying to access the file again
        try:
            self.client.head_object(Bucket=self.bucket, Key=file_key)
            # If we get here, the file still exists, which means deletion failed
            logger.error(f"File still exists after deletion attempt: {file_key}")
            return {
                "success": False,
                "error": "File still exists after deletion attempt",
                "file_key": file_key,
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                # File doesn't exist anymore, which means deletion was successful
                logger.info(f"Successfully deleted file: {file_key}")
                return {
                    "success": True,
                    "message": "File deleted successfully from Digital Ocean Spaces",
                    "file_key": file_key,
                }
            else:
                # Some other error occurred while verifying
                logger.error(f"Error verifying deletion: {e}")
                raise

    except Exception as e:
        logger.error(f"Error deleting file {file_key}: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to delete file from storage: {str(e)}",
            "file_key": file_key,
        }


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
                    "step_2": "Choose Professional plan ($96/year)",
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
                "pricing": "$96/year - Complete professional management suite",
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
                "no_data_loss": f"Your {existing_free_uploads + 1} certificates will remain accessible",
            },
            "next_steps": [
                f"✅ Certificate #{existing_free_uploads + 1} of {MAX_FREE_UPLOADS} processed",
                "📊 View your compliance dashboard",
                "📋 Generate audit presentation",
                (
                    f"⬆️ Upgrade available after {remaining_uploads} more uploads"
                    if remaining_uploads > 0
                    else "⬆️ Ready to upgrade for unlimited uploads!"
                ),
            ],
        }

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in license-based free upload: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# Also add this new endpoint:
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


@router.get("/document/{record_id}")
async def get_document(
    record_id: int, license_number: str, db: Session = Depends(get_db)
):
    """Get a presigned URL to view/download a certificate document"""

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

    # Check if document exists
    if not cpe_record.document_filename:
        raise HTTPException(
            status_code=404, detail="No document file associated with this certificate"
        )

    try:
        # Generate presigned URL for viewing
        storage_service = DocumentStorageService()
        download_url = storage_service.generate_download_url(
            cpe_record.document_filename, expiration=3600  # 1 hour expiration
        )

        if not download_url:
            raise HTTPException(
                status_code=500, detail="Failed to generate document access URL"
            )

        return {
            "success": True,
            "document_url": download_url,
            "certificate_id": record_id,
            "original_filename": cpe_record.course_title or "certificate.pdf",
            "expires_in": 3600,
            "message": "Document URL generated successfully",
        }

    except Exception as e:
        logger.error(f"Error generating document URL for record {record_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve document: {str(e)}"
        )


@router.get("/view-document/{record_id}")
async def view_document(
    record_id: int, license_number: str, db: Session = Depends(get_db)
):
    """Redirect directly to the document for viewing"""

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

    # Check if document exists
    if not cpe_record.document_filename:
        raise HTTPException(
            status_code=404, detail="No document file associated with this certificate"
        )

    try:
        # Generate presigned URL for viewing
        storage_service = DocumentStorageService()
        download_url = storage_service.generate_download_url(
            cpe_record.document_filename, expiration=3600  # 1 hour expiration
        )

        if not download_url:
            raise HTTPException(
                status_code=500, detail="Failed to generate document access URL"
            )

        # Redirect directly to the document
        return RedirectResponse(url=download_url)

    except Exception as e:
        logger.error(f"Error viewing document for record {record_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to view document: {str(e)}"
        )
