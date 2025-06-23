# app/api/uploads.py - Simplified Vision Service Upload API
"""
Simplified SuperCPE Upload API

Core functionality:
- File upload and validation
- AI processing with Google Vision API
- Document storage and retrieval
- Basic authentication and error handling
"""

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException,
    BackgroundTasks,
)
from sqlalchemy.orm import Session
from typing import Dict, Optional
import logging
import tempfile
import os
from datetime import datetime

# Core imports
from app.core.database import get_db
from app.services.jwt_service import get_current_user
from app.models.user import User
from app.models.cpe_record import CPERecord

# Service imports
from app.services.vision_service import EnhancedVisionService
from app.services.document_storage import DocumentStorageService

# Configure logging
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload", tags=["Upload"])

# ===== CONSTANTS =====
ALLOWED_FILE_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
FREE_UPLOAD_LIMIT = 10

# ===== UTILITY FUNCTIONS =====


def get_processing_quality(confidence_score: float) -> str:
    """Determine processing quality based on confidence score"""
    if confidence_score >= 0.8:
        return "excellent"
    elif confidence_score >= 0.6:
        return "good"
    elif confidence_score >= 0.4:
        return "moderate"
    else:
        return "manual_review_needed"


def validate_file(file: UploadFile) -> None:
    """Validate uploaded file type and size"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not supported. Please upload PDF or image files.",
        )

    # Check file size
    if hasattr(file, "size") and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")


async def process_with_vision_ai(file: UploadFile, license_number: str) -> Dict:
    """Process file with Google Vision API with proper error handling"""
    try:
        logger.info(f"Starting AI processing for {file.filename}")

        # Initialize vision service
        vision_service = EnhancedVisionService()

        # Read file content
        file_content = await file.read()
        await file.seek(0)  # Reset file pointer

        # Extract text using Google Vision API
        try:
            raw_text = vision_service.extract_text_from_file(
                file_content, file.content_type
            )
            logger.info(f"Successfully extracted {len(raw_text)} characters of text")
        except Exception as vision_error:
            logger.error(f"Google Vision API failed: {vision_error}")
            # Fallback to empty text if Vision API fails
            raw_text = ""

        # Parse certificate data (handle empty text gracefully)
        if raw_text:
            try:
                parsed_data = vision_service.parse_certificate_data(
                    raw_text, file.filename
                )
            except Exception as parse_error:
                logger.error(f"Parsing failed: {parse_error}")
                # Fallback to empty data
                parsed_data = {
                    "cpe_credits": 0.0,
                    "ethics_credits": 0.0,
                    "course_title": "",
                    "provider": "",
                    "completion_date": "",
                    "certificate_number": "",
                    "confidence_score": 0.0,
                }
        else:
            # No text extracted, return empty data
            parsed_data = {
                "cpe_credits": 0.0,
                "ethics_credits": 0.0,
                "course_title": "",
                "provider": "",
                "completion_date": "",
                "certificate_number": "",
                "confidence_score": 0.0,
            }

        # Return structured result
        return {
            "success": True,
            "parsed_data": {
                "cpe_hours": parsed_data.get("cpe_credits", 0.0),  # Map for frontend
                "ethics_hours": parsed_data.get(
                    "ethics_credits", 0.0
                ),  # Map for frontend
                "course_title": parsed_data.get("course_title", ""),
                "provider": parsed_data.get("provider", ""),
                "completion_date": parsed_data.get("completion_date", ""),
                "certificate_number": parsed_data.get("certificate_number", ""),
            },
            "confidence_score": parsed_data.get("confidence_score", 0.0),
            "raw_text": raw_text,
            "processing_method": (
                "google_vision_api" if raw_text else "manual_entry_required"
            ),
        }

    except Exception as e:
        logger.error(f"AI processing failed: {e}")
        # Return empty result instead of failing
        return {
            "success": False,
            "parsed_data": {
                "cpe_hours": 0.0,
                "ethics_hours": 0.0,
                "course_title": "",
                "provider": "",
                "completion_date": "",
                "certificate_number": "",
            },
            "confidence_score": 0.0,
            "raw_text": "",
            "processing_method": "failed_manual_entry_required",
        }


def create_cpe_record(
    parsing_result: Dict,
    file: UploadFile,
    license_number: str,
    current_user: User,
    upload_result: Dict,
    db: Session,
) -> CPERecord:
    """Create CPE record from parsing results using correct field names"""
    try:
        parsed_data = parsing_result.get("parsed_data", {})

        # Create new CPE record with correct field names from your model
        cpe_record = CPERecord(
            cpa_license_number=license_number,
            user_id=current_user.id,
            # Document info - use correct field names
            document_filename=upload_result.get("filename"),
            original_filename=file.filename,
            # Core CPE data - use your model's field names
            cpe_credits=float(
                parsed_data.get("cpe_hours", 0)
            ),  # Note: mapping cpe_hours -> cpe_credits
            ethics_credits=float(
                parsed_data.get("ethics_hours", 0)
            ),  # Note: mapping ethics_hours -> ethics_credits
            course_title=parsed_data.get("course_title", ""),
            provider=parsed_data.get("provider", ""),
            completion_date=parsed_data.get("completion_date"),
            certificate_number=parsed_data.get("certificate_number", ""),
            # Parsing metadata
            confidence_score=parsing_result.get("confidence_score", 0.0),
            parsing_method=parsing_result.get("processing_method", "google_vision_api"),
            raw_text=parsing_result.get("raw_text", ""),
            # System fields
            created_at=datetime.utcnow(),
        )

        db.add(cpe_record)
        db.commit()
        db.refresh(cpe_record)

        return cpe_record

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create CPE record: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save record: {str(e)}")


# ===== API ENDPOINTS =====


@router.post("/upload-certificate-authenticated/{license_number}")
async def upload_certificate_authenticated(
    license_number: str,
    file: UploadFile = File(...),
    parse_with_ai: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    AUTHENTICATED UPLOAD: Upload and process a CPE certificate with display data

    - Validates file type and size
    - Processes with Google Vision API
    - Stores document and creates CPE record
    - Returns detailed certificate display information
    """

    # Validate user permissions
    if current_user.license_number != license_number:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate file
    validate_file(file)

    try:
        # Initialize storage service
        storage_service = DocumentStorageService()

        # Step 1: Store the document using the correct method
        logger.info(f"Uploading file: {file.filename}")
        upload_result = await storage_service.upload_cpe_certificate(
            file, license_number
        )

        if not upload_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"File upload failed: {upload_result.get('error')}",
            )

        # Step 2: Process with AI if requested
        if parse_with_ai:
            logger.info(f"Processing with AI: {file.filename}")
            parsing_result = await process_with_vision_ai(file, license_number)
        else:
            # Basic result if AI processing is skipped
            parsing_result = {
                "success": True,
                "parsed_data": {
                    "cpe_hours": 0.0,
                    "ethics_hours": 0.0,
                    "course_title": "",
                    "provider": "",
                    "completion_date": "",
                    "certificate_number": "",
                },
                "confidence_score": 0.0,
                "raw_text": "",
                "processing_method": "manual_entry_required",
            }

        # Step 3: Create CPE record
        logger.info(f"Creating CPE record for: {file.filename}")
        cpe_record = create_cpe_record(
            parsing_result, file, license_number, current_user, upload_result, db
        )

        # Return success response with detailed certificate display data
        return {
            "success": True,
            "message": "Certificate uploaded and processed successfully",
            "data": {
                "record_id": cpe_record.id,
                "filename": file.filename,
                "parsed_data": parsing_result["parsed_data"],
                "confidence_score": parsing_result["confidence_score"],
                "document_url": upload_result.get("file_url"),
                # Additional display data for immediate viewing
                "certificate_display": {
                    "course_title": cpe_record.course_title,
                    "provider": cpe_record.provider,
                    "cpe_hours": float(
                        cpe_record.cpe_credits
                    ),  # Map back to frontend expectation
                    "ethics_hours": float(
                        cpe_record.ethics_credits
                    ),  # Map back to frontend expectation
                    "completion_date": cpe_record.completion_date,
                    "certificate_number": cpe_record.certificate_number,
                    "processing_quality": get_processing_quality(
                        parsing_result["confidence_score"]
                    ),
                    "extracted_text_preview": (
                        parsing_result.get("raw_text", "")[:500] + "..."
                        if len(parsing_result.get("raw_text", "")) > 500
                        else parsing_result.get("raw_text", "")
                    ),
                    "file_info": {
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "upload_timestamp": datetime.utcnow().isoformat(),
                    },
                },
            },
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/certificate/{license_number}")
async def upload_certificate_simple(
    license_number: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload and process a CPE certificate

    - Validates file type and size
    - Processes with Google Vision API
    - Stores document and creates CPE record
    """

    # Validate user permissions
    if current_user.license_number != license_number:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate file
    validate_file(file)

    try:
        # Initialize storage service
        storage_service = DocumentStorageService()

        # Step 1: Store the document
        logger.info(f"Uploading file: {file.filename}")
        upload_result = storage_service.store_document(
            file, license_number, "certificate"
        )

        if not upload_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"File upload failed: {upload_result.get('error')}",
            )

        # Step 2: Process with AI
        logger.info(f"Processing with AI: {file.filename}")
        parsing_result = await process_with_vision_ai(file, license_number)

        # Step 3: Create CPE record
        logger.info(f"Creating CPE record for: {file.filename}")
        cpe_record = create_cpe_record(
            parsing_result, file, license_number, current_user, upload_result, db
        )

        # Return success response with detailed certificate display data
        return {
            "success": True,
            "message": "Certificate uploaded and processed successfully",
            "data": {
                "record_id": cpe_record.id,
                "filename": file.filename,
                "parsed_data": parsing_result["parsed_data"],
                "confidence_score": parsing_result["confidence_score"],
                "document_url": upload_result.get("url"),
                # Additional display data for immediate viewing
                "certificate_display": {
                    "course_title": cpe_record.course_title,
                    "provider": cpe_record.provider,
                    "cpe_hours": float(cpe_record.cpe_hours),
                    "ethics_hours": float(cpe_record.ethics_hours),
                    "completion_date": cpe_record.completion_date,
                    "certificate_number": cpe_record.certificate_number,
                    "processing_quality": get_processing_quality(
                        parsing_result["confidence_score"]
                    ),
                    "extracted_text_preview": (
                        parsing_result.get("raw_text", "")[:500] + "..."
                        if len(parsing_result.get("raw_text", "")) > 500
                        else parsing_result.get("raw_text", "")
                    ),
                    "file_info": {
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "upload_timestamp": datetime.utcnow().isoformat(),
                    },
                },
            },
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/certificates/{license_number}")
async def get_certificates(
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all certificates for a license number with detailed display information"""

    # Validate user permissions
    if current_user.license_number != license_number:
        raise HTTPException(status_code=403, detail="Access denied")

    # Query certificates
    certificates = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number,
            CPERecord.user_id == current_user.id,
        )
        .order_by(CPERecord.created_at.desc())
        .all()
    )

    return {
        "success": True,
        "data": [
            {
                "id": cert.id,
                "course_title": cert.course_title,
                "provider": cert.provider,
                "cpe_hours": cert.cpe_credits,  # Map to frontend expectation
                "ethics_hours": cert.ethics_credits,  # Map to frontend expectation
                "completion_date": cert.completion_date,
                "certificate_number": cert.certificate_number,
                "confidence_score": cert.confidence_score,
                "document_filename": cert.document_filename,
                "created_at": cert.created_at,
                "updated_at": cert.updated_at,
                # Enhanced display data
                "certificate_display": {
                    "processing_quality": get_processing_quality(
                        cert.confidence_score or 0.0
                    ),
                    "has_ethics": bool(cert.ethics_credits and cert.ethics_credits > 0),
                    "total_credits": float(cert.cpe_credits or 0)
                    + float(cert.ethics_credits or 0),
                    "file_type": (
                        cert.document_filename.split(".")[-1].upper()
                        if cert.document_filename
                        else "UNKNOWN"
                    ),
                    "extracted_text_preview": (
                        cert.raw_text[:200] + "..."
                        if cert.raw_text and len(cert.raw_text) > 200
                        else cert.raw_text
                    ),
                },
            }
            for cert in certificates
        ],
        "total": len(certificates),
        "summary": {
            "total_cpe_hours": sum(
                float(cert.cpe_credits or 0) for cert in certificates
            ),
            "total_ethics_hours": sum(
                float(cert.ethics_credits or 0) for cert in certificates
            ),
            "certificates_count": len(certificates),
            "high_confidence_count": len(
                [
                    cert
                    for cert in certificates
                    if cert.confidence_score and cert.confidence_score >= 0.8
                ]
            ),
        },
    }


@router.get("/certificate/{record_id}/details")
async def get_certificate_details(
    record_id: int,
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific certificate for display"""

    # Find the record
    cpe_record = db.query(CPERecord).filter(CPERecord.id == record_id).first()
    if not cpe_record:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # Validate permissions
    if (
        cpe_record.cpa_license_number != license_number
        or cpe_record.user_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "success": True,
        "data": {
            "id": cpe_record.id,
            "course_title": cpe_record.course_title,
            "provider": cpe_record.provider,
            "cpe_hours": cpe_record.cpe_credits,  # Map to frontend expectation
            "ethics_hours": cpe_record.ethics_credits,  # Map to frontend expectation
            "completion_date": cpe_record.completion_date,
            "certificate_number": cpe_record.certificate_number,
            "confidence_score": cpe_record.confidence_score,
            "document_url": cpe_record.document_url,
            "document_filename": cpe_record.document_filename,
            "raw_extracted_text": cpe_record.raw_text,  # Use correct field name
            "created_at": cpe_record.created_at,
            "updated_at": cpe_record.updated_at,
            # Enhanced display information
            "display_info": {
                "processing_quality": get_processing_quality(
                    cpe_record.confidence_score or 0.0
                ),
                "has_ethics": bool(
                    cpe_record.ethics_credits and cpe_record.ethics_credits > 0
                ),
                "total_credits": float(cpe_record.cpe_credits or 0)
                + float(cpe_record.ethics_credits or 0),
                "file_type": (
                    cpe_record.document_filename.split(".")[-1].upper()
                    if cpe_record.document_filename
                    else "UNKNOWN"
                ),
                "text_length": len(cpe_record.raw_text) if cpe_record.raw_text else 0,
                "has_certificate_number": bool(cpe_record.certificate_number),
                "completion_date_formatted": (
                    cpe_record.completion_date.strftime("%B %d, %Y")
                    if cpe_record.completion_date
                    else None
                ),
            },
        },
    }


@router.delete("/certificate/{record_id}")
async def delete_certificate(
    record_id: int,
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a CPE certificate record and its file"""

    # Find the record
    cpe_record = db.query(CPERecord).filter(CPERecord.id == record_id).first()
    if not cpe_record:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # Validate permissions
    if (
        cpe_record.cpa_license_number != license_number
        or cpe_record.user_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        # Delete file from storage
        storage_service = DocumentStorageService()
        if cpe_record.document_filename:
            deletion_result = storage_service.delete_file(cpe_record.document_filename)
            logger.info(f"Storage deletion result: {deletion_result}")

        # Delete database record
        db.delete(cpe_record)
        db.commit()

        return {
            "success": True,
            "message": "Certificate deleted successfully",
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.get("/status/{license_number}")
async def get_upload_status(
    license_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get upload status and limits for user"""

    # Validate permissions
    if current_user.license_number != license_number:
        raise HTTPException(status_code=403, detail="Access denied")

    # Count uploads
    upload_count = (
        db.query(CPERecord)
        .filter(
            CPERecord.cpa_license_number == license_number,
            CPERecord.user_id == current_user.id,
        )
        .count()
    )

    return {
        "success": True,
        "data": {
            "uploads_used": upload_count,
            "uploads_remaining": max(0, FREE_UPLOAD_LIMIT - upload_count),
            "upload_limit": FREE_UPLOAD_LIMIT,
            "can_upload": upload_count < FREE_UPLOAD_LIMIT,
        },
    }


@router.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "success": True,
        "message": "Upload service is healthy",
        "timestamp": datetime.utcnow(),
    }
