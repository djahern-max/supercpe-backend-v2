# app/api/uploads.py - CLEAN AND ORGANIZED VERSION
"""
SuperCPE Upload API Endpoints

This module handles all file upload functionality including:
- Certificate uploads (authenticated and legacy)
- Document storage and retrieval
- AI processing of certificates
- Status tracking and compliance dashboards
"""

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
from fastapi.responses import RedirectResponse
from botocore.exceptions import ClientError

# Core imports
from app.core.database import get_db
from app.services.jwt_service import get_current_user
from app.models.user import User

# Service imports
from app.services.cpa_import import CPAImportService
from app.services.document_storage import DocumentStorageService
from app.services.stripe_service import StripeService
from app.services.vision_service import EnhancedVisionService
from app.services.upload_service import (
    create_enhanced_cpe_record_from_parsing,
)

# Model imports
from app.models.cpa import CPA
from app.models.cpe_record import CPERecord

# Standard library imports
import tempfile
import os
from datetime import datetime
import logging
import json

# Configure logging
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload", tags=["Upload"])

# ===== CONSTANTS =====
INITIAL_FREE_UPLOADS = 10  # First phase limit
EXTENDED_FREE_UPLOADS = 20  # Additional uploads in second phase
TOTAL_FREE_UPLOADS = 30  # Combined limit (10 + 20)
MAX_FREE_UPLOADS = 10  # Keep for backward compatibility initially

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

    # Check file size (10MB limit)
    if hasattr(file, "size") and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")


async def process_with_ai(file: UploadFile, license_number: str):
    """AI processing using Google Vision API - handles both PDFs and images"""
    try:
        from app.services.vision_service import EnhancedVisionService

        vision_service = EnhancedVisionService()

        # Read file content
        await file.seek(0)
        content = await file.read()

        logger.info(
            f"Processing file: {file.filename}, content_type: {file.content_type}, size: {len(content)} bytes"
        )

        # Extract text using Google Vision API - now handles both PDFs and images
        raw_text = await vision_service.extract_text_from_pdf(
            content, file.content_type
        )

        # Parse CPE data
        parsed_data = vision_service.parse_cpe_certificate(raw_text)

        return {
            "success": True,
            "parsed_data": parsed_data,
            "raw_text": raw_text,
            "confidence_score": 0.8,
            "parsing_method": "google_vision",
        }

    except Exception as e:
        logger.error(f"Vision API processing failed: {e}")
        logger.exception("Full vision processing error:")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")


def check_for_similar_certificates(
    db: Session, license_number: str, user_id: int, parsed_data: dict, filename: str
) -> dict:
    """
    Soft duplicate detection - warns but never blocks uploads
    Returns warning info if similar certificates found
    """

    # Get existing certificates for this user/license
    existing_records = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number, CPERecord.user_id == user_id
        )
        .all()
    )

    if not existing_records:
        return None  # No existing records to compare

    # Extract data from current upload
    current_course = (
        parsed_data.get("course_title", {}).get("value", "").lower().strip()
    )
    current_provider = parsed_data.get("provider", {}).get("value", "").lower().strip()
    current_date_str = parsed_data.get("completion_date", {}).get("value", "")
    current_filename = filename.lower()

    # Parse current date
    current_date = None
    if current_date_str:
        try:
            current_date = datetime.fromisoformat(current_date_str).date()
        except:
            try:
                current_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
            except:
                pass

    similar_certificates = []

    for record in existing_records:
        similarity_score = 0
        similarity_reasons = []

        # Check filename similarity (exact match gets high score)
        if (
            record.original_filename
            and record.original_filename.lower() == current_filename
        ):
            similarity_score += 0.8
            similarity_reasons.append("identical filename")

        # Check course title similarity
        if record.course_title and current_course:
            record_course = record.course_title.lower().strip()

            # Exact match
            if record_course == current_course:
                similarity_score += 0.6
                similarity_reasons.append("identical course title")
            # High similarity (contains key words)
            elif (len(current_course) > 10 and current_course in record_course) or (
                len(record_course) > 10 and record_course in current_course
            ):
                similarity_score += 0.4
                similarity_reasons.append("similar course title")

        # Check provider similarity
        if record.provider and current_provider:
            record_provider = record.provider.lower().strip()
            if record_provider == current_provider:
                similarity_score += 0.3
                similarity_reasons.append("same provider")

        # Check date proximity (within 30 days)
        if record.completion_date and current_date:
            date_diff = abs((record.completion_date - current_date).days)
            if date_diff == 0:
                similarity_score += 0.4
                similarity_reasons.append("identical completion date")
            elif date_diff <= 7:
                similarity_score += 0.2
                similarity_reasons.append("completion date within 1 week")
            elif date_diff <= 30:
                similarity_score += 0.1
                similarity_reasons.append("completion date within 1 month")

        # If similarity score is high enough, consider it similar
        if similarity_score >= 0.6:  # Threshold for "similar"
            similar_certificates.append(
                {
                    "record_id": record.id,
                    "course_title": record.course_title,
                    "provider": record.provider,
                    "completion_date": (
                        record.completion_date.isoformat()
                        if record.completion_date
                        else None
                    ),
                    "original_filename": record.original_filename,
                    "similarity_score": round(similarity_score, 2),
                    "similarity_reasons": similarity_reasons,
                    "created_at": (
                        record.created_at.isoformat() if record.created_at else None
                    ),
                }
            )

    # Return warning if similar certificates found
    if similar_certificates:
        return {
            "warning_type": "potential_duplicate",
            "message": "This certificate appears similar to previous uploads",
            "similar_count": len(similar_certificates),
            "similar_certificates": similar_certificates[:3],  # Limit to top 3 matches
            "recommendation": "Please review your uploaded certificates to avoid duplicates",
        }

    return None


@router.post("/upload-certificate-authenticated/{license_number}")
async def upload_certificate_authenticated(
    license_number: str,
    file: UploadFile = File(...),
    parse_with_ai: bool = True,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """AUTHENTICATED UPLOAD: Fixed version with proper storage tier and error handling"""

    # Verify user owns this license
    if current_user.license_number != license_number:
        raise HTTPException(
            status_code=403,
            detail="You can only upload certificates for your own license number",
        )

    # Verify CPA exists in database
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(
            status_code=404,
            detail="CPA license not found in our database",
        )

    try:
        logger.info(f"Starting authenticated upload for license {license_number}")

        # Check subscription status to determine storage tier
        stripe_service = StripeService(db)
        has_subscription = stripe_service.has_active_subscription(license_number)
        storage_tier = "premium" if has_subscription else "free"

        logger.info(
            f"User subscription status: {has_subscription}, storage_tier: {storage_tier}"
        )

        # For non-premium users, check upload limits
        if not has_subscription:
            # Count existing free uploads by this user
            free_uploads = (
                db.query(CPERecord)
                .filter(
                    CPERecord.cpa_license_number == license_number,
                    CPERecord.user_id == current_user.id,
                    CPERecord.storage_tier == "free",
                )
                .count()
            )

            logger.info(f"User has {free_uploads} free uploads used")

            # Check if user is at limit
            if free_uploads >= TOTAL_FREE_UPLOADS:
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "Upload limit reached",
                        "message": f"You've used all {TOTAL_FREE_UPLOADS} free uploads. Please upgrade to continue.",
                        "uploads_used": free_uploads,
                        "limit": TOTAL_FREE_UPLOADS,
                        "upgrade_required": True,
                    },
                )

        # Validate file
        validate_file(file)

        # Step 1: Upload file to storage
        storage_service = DocumentStorageService()
        upload_result = await storage_service.upload_cpe_certificate(
            file, license_number
        )

        if not upload_result.get("success"):
            raise HTTPException(status_code=500, detail=upload_result.get("error"))

        logger.info(f"File uploaded successfully: {upload_result}")

        # Step 2: Process with AI if requested
        if parse_with_ai:
            logger.info("Starting AI parsing...")

            # Get parsing result from vision service
            parsing_result = await process_with_ai(file, license_number)

            # DEBUG: Log what we got from parsing
            logger.info(f"Parsing result keys: {list(parsing_result.keys())}")
            logger.info(f"Raw text available: {bool(parsing_result.get('raw_text'))}")

            # Step 3: Create CPE record using the enhanced creation function
            cpe_record = create_enhanced_cpe_record_from_parsing(
                parsing_result,
                file,
                license_number,
                current_user,
                upload_result,
                storage_tier,  # Pass the determined storage tier
            )

            # Save to database
            db.add(cpe_record)
            db.commit()
            db.refresh(cpe_record)

            logger.info(
                f"Successfully saved CPE record with storage_tier: {cpe_record.storage_tier}"
            )

            # Verify what was saved
            logger.info(f"Saved record details:")
            logger.info(f"  - ID: {cpe_record.id}")
            logger.info(f"  - Course title: {cpe_record.course_title}")
            logger.info(f"  - CPE credits: {cpe_record.cpe_credits}")
            logger.info(f"  - Storage tier: {cpe_record.storage_tier}")
            logger.info(f"  - User ID: {cpe_record.user_id}")

            return {
                "success": True,
                "message": "✅ Certificate uploaded and saved successfully",
                "cpe_record": {
                    "id": cpe_record.id,
                    "course_title": cpe_record.course_title,
                    "cpe_credits": cpe_record.cpe_credits,
                    "ethics_credits": cpe_record.ethics_credits,
                    "provider": cpe_record.provider,
                    "completion_date": (
                        cpe_record.completion_date.isoformat()
                        if cpe_record.completion_date
                        else None
                    ),
                    "storage_tier": cpe_record.storage_tier,
                },
                "file_info": upload_result,
                "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
                "ai_parsing_enabled": True,
                "parsing_result": parsing_result,
                "upload_status": {
                    "storage_tier": storage_tier,
                    "is_premium": has_subscription,
                },
            }

        else:
            # Create basic record without AI parsing
            logger.info("Creating basic record without AI parsing...")

            # Create a basic CPE record manually
            cpe_record = CPERecord(
                cpa_license_number=license_number,
                user_id=current_user.id,
                document_filename=upload_result.get("filename", file.filename),
                original_filename=file.filename,
                cpe_credits=0.0,  # To be filled manually
                ethics_credits=0.0,  # To be filled manually
                course_title="Manual Entry Required",
                provider="Unknown Provider",
                completion_date=datetime.utcnow().date(),
                storage_tier=storage_tier,  # Set the correct storage tier
                created_at=datetime.utcnow(),
            )

            db.add(cpe_record)
            db.commit()
            db.refresh(cpe_record)

            logger.info(
                f"Successfully saved basic CPE record with storage_tier: {cpe_record.storage_tier}"
            )

            return {
                "success": True,
                "message": "✅ Certificate uploaded successfully (manual entry required)",
                "cpe_record": {
                    "id": cpe_record.id,
                    "storage_tier": cpe_record.storage_tier,
                },
                "file_info": upload_result,
                "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
                "ai_parsing_enabled": False,
                "upload_status": {
                    "storage_tier": storage_tier,
                    "is_premium": has_subscription,
                },
            }

    except HTTPException:
        # Re-raise HTTP exceptions (like 402 for limit reached)
        raise
    except Exception as e:
        logger.error(f"Error in authenticated upload: {str(e)}")
        logger.exception("Full traceback:")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/accept-extended-trial/{license_number}")
async def accept_extended_trial(
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept the extended trial offer (20 additional uploads)"""

    # Verify user owns this license
    if current_user.license_number != license_number:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if user is eligible for extended trial
    existing_uploads = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number,
            CPERecord.storage_tier == "free",
        )
        .count()
    )

    if existing_uploads != INITIAL_FREE_UPLOADS:
        raise HTTPException(status_code=400, detail="Not eligible for extended trial")

    # Check if user has already accepted extended trial
    if current_user.accepted_extended_trial:
        raise HTTPException(status_code=400, detail="Extended trial already accepted")

    try:
        # Update user record to mark extended trial as accepted
        current_user.accepted_extended_trial = True
        current_user.extended_trial_accepted_at = datetime.now()
        current_user.updated_at = datetime.now()

        # Commit the changes
        db.commit()
        db.refresh(current_user)

        return {
            "success": True,
            "message": "Extended trial activated! You now have 20 additional uploads.",
            "user": {
                "accepted_extended_trial": current_user.accepted_extended_trial,
                "extended_trial_accepted_at": current_user.extended_trial_accepted_at,
            },
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error accepting extended trial: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to activate extended trial: {str(e)}"
        )


@router.get("/user-upload-status/{license_number}")
async def get_user_upload_status(
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get authenticated user's upload status with extended trial tracking"""

    # Verify user owns this license
    if current_user.license_number != license_number:
        raise HTTPException(
            status_code=403,
            detail="You can only view status for your own license number",
        )

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA license number not found")

    # Count uploads by this user
    user_uploads = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number,
            CPERecord.user_id == current_user.id,
        )
        .count()
    )

    # Count free tier uploads
    free_uploads = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number,
            CPERecord.user_id == current_user.id,
            CPERecord.storage_tier == "free",
        )
        .count()
    )

    # Check subscription status
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    # FOR PREMIUM USERS: Override all limits and phases
    if has_subscription:
        return {
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "name": current_user.name,
                "license_number": current_user.license_number,
            },
            "cpa": {"license_number": license_number, "name": cpa.full_name},
            "upload_stats": {
                "total_uploads": user_uploads,
                "free_uploads_used": free_uploads,
                "remaining_free_uploads": -1,  # Unlimited
                "max_free_uploads": -1,  # Unlimited
                "at_limit": False,  # Never at limit for premium
                "has_premium_subscription": True,
            },
            # Extended trial tracking (not relevant for premium but keep for compatibility)
            "extended_trial_info": {
                "accepted_extended_trial": current_user.accepted_extended_trial,
                "extended_trial_accepted_at": current_user.extended_trial_accepted_at,
            },
            # Phase tracking for premium users
            "upload_phase": "premium",  # Special phase for premium users
            "initial_uploads_used": (
                free_uploads
                if free_uploads <= INITIAL_FREE_UPLOADS
                else INITIAL_FREE_UPLOADS
            ),
            "extended_uploads_used": (
                max(0, free_uploads - INITIAL_FREE_UPLOADS)
                if free_uploads > INITIAL_FREE_UPLOADS
                else 0
            ),
            "total_uploads_used": free_uploads,
            "remaining_in_phase": -1,  # Unlimited
            "total_remaining": -1,  # Unlimited
            # Status flags for premium users
            "at_limit": False,  # Never at limit
            "needs_extended_offer": False,  # No offer needed
            "accepted_extended_trial": current_user.accepted_extended_trial,
            "status": "premium",
            "message": "✨ Premium subscriber - unlimited uploads!",
            "authenticated": True,
        }

    # FOR FREE USERS: Calculate phase-based status (existing logic)
    if free_uploads < INITIAL_FREE_UPLOADS:
        # Phase 1: Initial free trial (uploads 1-10)
        upload_phase = "initial"
        initial_uploads_used = free_uploads
        extended_uploads_used = 0
        remaining_in_phase = INITIAL_FREE_UPLOADS - free_uploads
        total_remaining = TOTAL_FREE_UPLOADS - free_uploads
        at_limit = False
        needs_extended_offer = False
        message = f"✅ {remaining_in_phase} uploads remaining in your free trial"

    elif free_uploads == INITIAL_FREE_UPLOADS:
        # Phase transition: Show extended offer
        upload_phase = "transition"
        initial_uploads_used = INITIAL_FREE_UPLOADS
        extended_uploads_used = 0
        remaining_in_phase = (
            EXTENDED_FREE_UPLOADS if current_user.accepted_extended_trial else 0
        )
        total_remaining = (
            EXTENDED_FREE_UPLOADS if current_user.accepted_extended_trial else 0
        )
        at_limit = not current_user.accepted_extended_trial
        needs_extended_offer = not current_user.accepted_extended_trial
        message = (
            "🎉 Free trial complete! Ready for 20 additional uploads?"
            if not current_user.accepted_extended_trial
            else f"🚀 {remaining_in_phase} extended uploads remaining"
        )

    elif free_uploads < TOTAL_FREE_UPLOADS:
        # Phase 2: Extended trial (uploads 11-30)
        upload_phase = "extended"
        initial_uploads_used = INITIAL_FREE_UPLOADS
        extended_uploads_used = free_uploads - INITIAL_FREE_UPLOADS
        remaining_in_phase = TOTAL_FREE_UPLOADS - free_uploads
        total_remaining = TOTAL_FREE_UPLOADS - free_uploads
        at_limit = False
        needs_extended_offer = False
        message = f"🚀 {remaining_in_phase} extended uploads remaining"

    else:
        # Phase 3: Limit reached (30+ uploads)
        upload_phase = "limit_reached"
        initial_uploads_used = INITIAL_FREE_UPLOADS
        extended_uploads_used = EXTENDED_FREE_UPLOADS
        remaining_in_phase = 0
        total_remaining = 0
        at_limit = True
        needs_extended_offer = False
        message = "🎯 Ready to upgrade? You've experienced everything SuperCPE offers!"

    remaining_uploads = max(0, TOTAL_FREE_UPLOADS - free_uploads)

    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "license_number": current_user.license_number,
        },
        "cpa": {"license_number": license_number, "name": cpa.full_name},
        "upload_stats": {
            "total_uploads": user_uploads,
            "free_uploads_used": free_uploads,
            "remaining_free_uploads": remaining_uploads,
            "max_free_uploads": TOTAL_FREE_UPLOADS,
            "at_limit": at_limit,
            "has_premium_subscription": False,  # This is a free user
        },
        # Extended trial tracking
        "extended_trial_info": {
            "accepted_extended_trial": current_user.accepted_extended_trial,
            "extended_trial_accepted_at": current_user.extended_trial_accepted_at,
        },
        # Phase tracking (matches free-tier-status response)
        "upload_phase": upload_phase,
        "initial_uploads_used": initial_uploads_used,
        "extended_uploads_used": extended_uploads_used,
        "total_uploads_used": free_uploads,
        "remaining_in_phase": remaining_in_phase,
        "total_remaining": total_remaining,
        # Status flags
        "at_limit": at_limit,
        "needs_extended_offer": needs_extended_offer,
        "accepted_extended_trial": current_user.accepted_extended_trial,
        "status": ("available" if remaining_uploads > 0 else "limit_reached"),
        "message": message,
        "authenticated": True,
    }


@router.post("/upload-cpe-certificate/{license_number}")
async def upload_cpe_certificate_premium(
    license_number: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PREMIUM: Unlimited uploads for subscribers"""

    # Verify user owns this license
    if current_user.license_number != license_number:
        raise HTTPException(
            status_code=403,
            detail="You can only upload certificates for your own license number",
        )

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
                "error": "Premium subscription required",
                "message": "This endpoint requires an active premium subscription",
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

        if not upload_result.get("success"):
            raise HTTPException(status_code=500, detail=upload_result.get("error"))

        # Step 2: Process with AI
        parsing_result = await process_with_ai(file, license_number)

        # Step 2.5: DEFINE STORAGE_TIER (ADD THIS LINE!)
        storage_tier = "premium"  # Define storage_tier before using it

        # Step 3: Create CPE record with premium tier
        cpe_record = create_enhanced_cpe_record_from_parsing(
            parsing_result,
            file,
            license_number,
            current_user,
            upload_result,
            storage_tier,  # Now this variable exists
        )

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


# ===== STATUS ENDPOINTS =====


@router.get("/free-tier-status/{license_number}")
async def get_free_tier_status(license_number: str, db: Session = Depends(get_db)):
    """Get current free tier upload status with enhanced phase tracking - NO AUTH REQUIRED for status checking"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA license number not found")

    # Count existing free uploads for this license
    total_free_uploads = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number,
            CPERecord.storage_tier == "free",
        )
        .count()
    )

    # Check if user has premium subscription
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    # Calculate phase-based status
    if total_free_uploads < INITIAL_FREE_UPLOADS:
        # Phase 1: Initial free trial (uploads 1-10)
        upload_phase = "initial"
        initial_uploads_used = total_free_uploads
        extended_uploads_used = 0
        remaining_in_phase = INITIAL_FREE_UPLOADS - total_free_uploads
        total_remaining = TOTAL_FREE_UPLOADS - total_free_uploads
        at_limit = False
        needs_extended_offer = False
        message = f"✅ {remaining_in_phase} uploads remaining in your free trial"

    elif total_free_uploads == INITIAL_FREE_UPLOADS:
        # Phase transition: Show extended offer
        upload_phase = "transition"
        initial_uploads_used = INITIAL_FREE_UPLOADS
        extended_uploads_used = 0
        remaining_in_phase = EXTENDED_FREE_UPLOADS
        total_remaining = EXTENDED_FREE_UPLOADS
        at_limit = False
        needs_extended_offer = True
        message = "🎉 Free trial complete! Ready for 20 additional uploads?"

    elif total_free_uploads < TOTAL_FREE_UPLOADS:
        # Phase 2: Extended trial (uploads 11-30)
        upload_phase = "extended"
        initial_uploads_used = INITIAL_FREE_UPLOADS
        extended_uploads_used = total_free_uploads - INITIAL_FREE_UPLOADS
        remaining_in_phase = TOTAL_FREE_UPLOADS - total_free_uploads
        total_remaining = TOTAL_FREE_UPLOADS - total_free_uploads
        at_limit = False
        needs_extended_offer = False
        message = f"🚀 {remaining_in_phase} extended uploads remaining"

    else:
        # Phase 3: Limit reached (30+ uploads)
        upload_phase = "limit_reached"
        initial_uploads_used = INITIAL_FREE_UPLOADS
        extended_uploads_used = EXTENDED_FREE_UPLOADS
        remaining_in_phase = 0
        total_remaining = 0
        at_limit = True
        needs_extended_offer = False
        message = "🎯 Ready to upgrade? You've experienced everything SuperCPE offers!"

    # Determine overall status
    if has_subscription:
        status = "premium"
        message = "✨ Premium subscriber - unlimited uploads!"
    elif total_remaining > 0:
        status = "available"
    else:
        status = "limit_reached"

    return {
        # Basic info
        "license_number": license_number,
        "cpa_name": cpa.full_name,
        "has_premium_subscription": has_subscription,
        "auth_required": True,
        # Phase tracking (NEW)
        "upload_phase": upload_phase,
        "initial_uploads_used": initial_uploads_used,
        "extended_uploads_used": extended_uploads_used,
        "total_uploads_used": total_free_uploads,
        "remaining_in_phase": remaining_in_phase,
        "total_remaining": total_remaining,
        # Phase limits (NEW)
        "limits": {
            "initial_limit": INITIAL_FREE_UPLOADS,
            "extended_limit": EXTENDED_FREE_UPLOADS,
            "total_limit": TOTAL_FREE_UPLOADS,
        },
        # Status flags
        "at_limit": at_limit,
        "needs_extended_offer": needs_extended_offer,
        "status": status,
        "upgrade_required": at_limit and not has_subscription,
        # User-friendly message
        "message": message,
        # Legacy compatibility (keep for existing frontend code)
        "uploads_used": total_free_uploads,
        "uploads_remaining": total_remaining,
        "max_free_uploads": TOTAL_FREE_UPLOADS,  # Updated to reflect new total
    }


@router.get("/compliance-dashboard/{license_number}")
async def get_compliance_dashboard_free(
    license_number: str, db: Session = Depends(get_db)
):
    """Get compliance dashboard for any license number - no auth required"""

    # Find the CPA
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    # Get CPE records for this license (both authenticated and legacy)
    cpe_records = (
        db.query(CPERecord)
        .filter(CPERecord.cpa_license_number == license_number)
        .order_by(CPERecord.created_at.desc())
        .all()
    )

    # Calculate totals
    total_cpe = sum(record.cpe_credits or 0 for record in cpe_records)
    total_ethics = sum(record.ethics_credits or 0 for record in cpe_records)

    # Count by storage tier
    free_uploads = len([r for r in cpe_records if r.storage_tier == "free"])
    premium_uploads = len([r for r in cpe_records if r.storage_tier == "premium"])

    # Check subscription status
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    # Prepare certificates data
    certificates = []
    for record in cpe_records:
        certificates.append(
            {
                "id": record.id,
                "course_title": record.course_title,
                "provider_name": getattr(record, "provider", "Unknown Provider"),
                "completion_date": (
                    record.completion_date.isoformat()
                    if record.completion_date
                    else None
                ),
                "cpe_credits": record.cpe_credits,
                "ethics_credits": record.ethics_credits,
                "file_name": getattr(record, "original_filename", "Unknown File"),
                "storage_tier": record.storage_tier,
                "ai_extracted": getattr(record, "parsing_method", "")
                == "google_vision",
                "created_at": (
                    record.created_at.isoformat() if record.created_at else None
                ),
                "user_id": getattr(
                    record, "user_id", None
                ),  # Include for ownership checking
            }
        )

    return {
        "cpa": {"license_number": cpa.license_number, "name": cpa.full_name},
        "compliance_summary": {
            "total_cpe_hours": total_cpe,
            "total_ethics_hours": total_ethics,
            "total_certificates": len(cpe_records),
        },
        "certificates": certificates,
        "upload_status": {
            "free_uploads_used": free_uploads,
            "free_uploads_remaining": max(0, MAX_FREE_UPLOADS - free_uploads),
            "max_free_uploads": TOTAL_FREE_UPLOADS,
            "at_limit": free_uploads >= TOTAL_FREE_UPLOADS,
            "has_subscription": has_subscription,
            "auth_required": True,  # Indicate auth is now required
        },
        "summary": {
            "total_records": len(cpe_records),
            "total_cpe_credits": total_cpe,
            "total_ethics_credits": total_ethics,
            "free_uploads_used": free_uploads,
            "premium_uploads": premium_uploads,
            "subscription_status": "active" if has_subscription else "free",
        },
    }


# ===== DOCUMENT MANAGEMENT ENDPOINTS =====


@router.delete("/certificate/{record_id}")
async def delete_certificate(
    record_id: int,
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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

    # Verify user owns this record
    if cpe_record.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only delete your own certificates",
        )

    storage_deletion_result = None
    storage_service = DocumentStorageService()

    # Step 1: Delete the file from Digital Ocean Spaces if it exists
    try:
        if hasattr(cpe_record, "document_filename") and cpe_record.document_filename:
            logger.info(f"Deleting file from storage: {cpe_record.document_filename}")
            storage_deletion_result = storage_service.delete_file(
                cpe_record.document_filename
            )

            if not storage_deletion_result.get("success"):
                logger.warning(
                    f"Failed to delete file from storage: {storage_deletion_result.get('error')}"
                )
        else:
            logger.info(f"No file to delete for certificate {record_id}")
            storage_deletion_result = {
                "success": True,
                "message": "No file associated with record",
            }

    except Exception as storage_error:
        logger.error(f"Error deleting file from storage: {storage_error}")
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
            "provider": getattr(cpe_record, "provider", "Unknown"),
            "document_filename": getattr(cpe_record, "document_filename", None),
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


@router.get("/document/{record_id}")
async def get_document(
    record_id: int,
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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

    # Verify user owns this record (if user_id exists)
    if (
        hasattr(cpe_record, "user_id")
        and cpe_record.user_id
        and cpe_record.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only view your own certificates",
        )

    # Check if document exists
    document_filename = getattr(cpe_record, "document_filename", None)
    if not document_filename:
        raise HTTPException(
            status_code=404, detail="No document file associated with this certificate"
        )

    try:
        # Generate presigned URL for viewing
        storage_service = DocumentStorageService()
        download_url = storage_service.generate_download_url(
            document_filename, expiration=3600  # 1 hour expiration
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
    record_id: int,
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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

    # Verify user owns this record (if user_id exists)
    if (
        hasattr(cpe_record, "user_id")
        and cpe_record.user_id
        and cpe_record.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only view your own certificates",
        )

    # Check if document exists
    document_filename = getattr(cpe_record, "document_filename", None)
    if not document_filename:
        raise HTTPException(
            status_code=404, detail="No document file associated with this certificate"
        )

    try:
        # Generate presigned URL for viewing
        storage_service = DocumentStorageService()
        download_url = storage_service.generate_download_url(
            document_filename, expiration=3600  # 1 hour expiration
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
