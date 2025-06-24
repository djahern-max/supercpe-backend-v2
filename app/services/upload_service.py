# FILE 3: app/services/upload_service.py (UPDATED)
"""
Enhanced Upload Service with Smart Review Support
"""

import logging
import json
from typing import Dict, Optional
from datetime import datetime, date
from app.models.cpe_record import CPERecord

logger = logging.getLogger(__name__)


def create_enhanced_cpe_record_from_parsing(
    parsing_result: Dict,
    file,
    license_number: str,
    current_user,
    upload_result: Dict,
    storage_tier: str = "free",
):
    """
    UPDATED: Create CPE record with enhanced smart review data
    Now stores both the extracted data AND the smart insights for review
    """
    try:
        # Get the basic parsed data (backward compatibility)
        parsed_data = parsing_result.get("parsed_data", {})
        raw_text = parsing_result.get("raw_text", "")

        logger.info(f"Creating enhanced CPE record for license {license_number}")
        logger.info(f"Raw text length: {len(raw_text) if raw_text else 0}")

        # NEW: Check if we have smart review data
        has_smart_data = "smart_insights" in parsing_result
        processing_method = parsing_result.get("processing_method", "unknown")

        if has_smart_data:
            logger.info("Processing with smart review data")
            # Use the smart review extracted data
            extracted_data = parsed_data
            smart_insights = parsing_result.get("smart_insights", {})
            suggestions = parsing_result.get("suggestions", [])
            review_flags = parsing_result.get("review_flags", [])
        else:
            logger.info("Processing with legacy data format")
            # Fallback to legacy format
            extracted_data = parsed_data
            smart_insights = {}
            suggestions = []
            review_flags = []

        # Create CPE record with enhanced metadata
        cpe_record = CPERecord(
            # Basic identification
            cpa_license_number=license_number,
            user_id=current_user.id if current_user else None,
            document_filename=upload_result.get("filename", file.filename),
            original_filename=file.filename,
            # Core CPE data (from smart extraction or legacy)
            cpe_credits=float(extracted_data.get("cpe_credits", 0.0)),
            ethics_credits=float(extracted_data.get("ethics_credits", 0.0)),
            course_title=extracted_data.get("course_title"),
            provider=extracted_data.get("provider"),
            completion_date=_parse_date_field(extracted_data.get("completion_date")),
            certificate_number=extracted_data.get("certificate_number"),
            # AI/Processing metadata
            confidence_score=float(parsing_result.get("confidence_score", 0.0)),
            parsing_method=processing_method,
            raw_text=raw_text,
            # NEW: Smart review metadata (stored as JSON)
            smart_insights=json.dumps(smart_insights) if smart_insights else None,
            suggestions=json.dumps(suggestions) if suggestions else None,
            review_flags=json.dumps(review_flags) if review_flags else None,
            # Status tracking
            needs_review=len(review_flags) > 0
            or extracted_data.get("course_title") is None,
            is_verified=False,  # Always starts as unverified
            storage_tier=storage_tier,
            # Timestamps
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Log what we created
        logger.info(f"Enhanced CPE record created:")
        logger.info(f"  - course_title: {cpe_record.course_title}")
        logger.info(f"  - provider: {cpe_record.provider}")
        logger.info(f"  - cpe_credits: {cpe_record.cpe_credits}")
        logger.info(f"  - confidence_score: {cpe_record.confidence_score}")
        logger.info(f"  - needs_review: {cpe_record.needs_review}")
        logger.info(f"  - processing_method: {cpe_record.parsing_method}")

        if suggestions:
            logger.info(f"  - suggestions available: {len(suggestions)}")
        if review_flags:
            logger.info(f"  - review flags: {len(review_flags)}")

        return cpe_record

    except Exception as e:
        logger.error(f"Error creating enhanced CPE record: {str(e)}")
        logger.exception("Full traceback:")
        raise


def _parse_date_field(date_value) -> Optional[date]:
    """Helper to parse date field from various formats"""
    if not date_value:
        return None

    if isinstance(date_value, date):
        return date_value

    if isinstance(date_value, str):
        try:
            # Try ISO format first
            return datetime.fromisoformat(date_value).date()
        except:
            try:
                # Try common formats
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"]:
                    return datetime.strptime(date_value, fmt).date()
            except:
                logger.warning(f"Could not parse date: {date_value}")
                return None

    return None


def get_certificate_review_data(cpe_record: CPERecord) -> Dict:
    """
    NEW: Extract smart review data from a CPE record for the review interface
    """
    try:
        review_data = {
            "id": cpe_record.id,
            "filename": cpe_record.original_filename,
            "processing_method": cpe_record.parsing_method,
            "confidence_score": cpe_record.confidence_score,
            "needs_review": cpe_record.needs_review,
            # Current extracted values
            "current_data": {
                "course_title": cpe_record.course_title,
                "provider": cpe_record.provider,
                "cpe_credits": cpe_record.cpe_credits,
                "ethics_credits": cpe_record.ethics_credits,
                "completion_date": (
                    cpe_record.completion_date.isoformat()
                    if cpe_record.completion_date
                    else None
                ),
                "certificate_number": cpe_record.certificate_number,
            },
            # Smart review data (if available)
            "smart_insights": (
                json.loads(cpe_record.smart_insights)
                if cpe_record.smart_insights
                else {}
            ),
            "suggestions": (
                json.loads(cpe_record.suggestions) if cpe_record.suggestions else []
            ),
            "review_flags": (
                json.loads(cpe_record.review_flags) if cpe_record.review_flags else []
            ),
            # Raw text for manual review
            "raw_text": cpe_record.raw_text,
            "raw_text_preview": (
                cpe_record.raw_text[:500] + "..."
                if cpe_record.raw_text and len(cpe_record.raw_text) > 500
                else cpe_record.raw_text
            ),
        }

        return review_data

    except Exception as e:
        logger.error(f"Error extracting review data: {e}")
        return {
            "id": cpe_record.id,
            "error": "Could not load review data",
            "current_data": {
                "course_title": cpe_record.course_title,
                "provider": cpe_record.provider,
                "cpe_credits": cpe_record.cpe_credits,
                "ethics_credits": cpe_record.ethics_credits,
                "completion_date": (
                    cpe_record.completion_date.isoformat()
                    if cpe_record.completion_date
                    else None
                ),
                "certificate_number": cpe_record.certificate_number,
            },
        }


def update_certificate_from_review(
    cpe_record: CPERecord, updated_data: Dict, user_id: Optional[int] = None
) -> CPERecord:
    """
    NEW: Update a certificate record after user review
    """
    try:
        logger.info(f"Updating certificate {cpe_record.id} from user review")

        # Update the core fields
        if "course_title" in updated_data:
            cpe_record.course_title = updated_data["course_title"]

        if "provider" in updated_data:
            cpe_record.provider = updated_data["provider"]

        if "cpe_credits" in updated_data:
            cpe_record.cpe_credits = float(updated_data["cpe_credits"])

        if "ethics_credits" in updated_data:
            cpe_record.ethics_credits = float(updated_data["ethics_credits"])

        if "completion_date" in updated_data:
            cpe_record.completion_date = _parse_date_field(
                updated_data["completion_date"]
            )

        if "certificate_number" in updated_data:
            cpe_record.certificate_number = updated_data["certificate_number"]

        # Mark as reviewed and verified
        cpe_record.needs_review = False
        cpe_record.is_verified = True
        cpe_record.updated_at = datetime.utcnow()

        # Clear suggestions and review flags since they've been addressed
        cpe_record.suggestions = None
        cpe_record.review_flags = None

        # Update confidence score to 1.0 since human verified
        cpe_record.confidence_score = 1.0
        cpe_record.parsing_method = "human_verified"

        logger.info(f"Certificate {cpe_record.id} updated and verified")
        return cpe_record

    except Exception as e:
        logger.error(f"Error updating certificate from review: {e}")
        raise


# Legacy function for backward compatibility
def create_cpe_record_from_parsing(
    parsing_result: Dict,
    file,
    license_number: str,
    current_user,
    upload_result: Dict,
    storage_tier: str = "free",
):
    """Legacy function - redirects to enhanced version"""
    return create_enhanced_cpe_record_from_parsing(
        parsing_result, file, license_number, current_user, upload_result, storage_tier
    )
