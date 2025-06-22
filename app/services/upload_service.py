# app/services/upload_service.py - Enhanced upload processing

import logging
from typing import Dict, Optional
from app.services.vision_service import EnhancedVisionService
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
    """Create CPE record with enhanced CE Broker fields - FIXED VERSION"""

    from datetime import datetime

    try:
        # Initialize enhanced vision service
        vision_service = EnhancedVisionService()

        # Get basic parsed data
        parsed_data = parsing_result.get("parsed_data", {})
        raw_text = parsing_result.get("raw_text", "")

        logger.info(f"Starting enhanced parsing for license {license_number}")
        logger.info(f"Raw text length: {len(raw_text) if raw_text else 0}")
        logger.info(f"Basic parsed data keys: {list(parsed_data.keys())}")

        # CRITICAL FIX: Ensure we have raw text for processing
        if not raw_text:
            logger.warning("No raw text available for CE Broker field extraction")
            # Try to get raw text from parsed data if available
            raw_text = parsed_data.get("raw_text", "")

        # Enhance with CE Broker fields
        enhanced_data = vision_service.enhance_parsed_data(raw_text, parsed_data)

        logger.info(f"Enhanced data extracted:")
        logger.info(f"  - course_type: {enhanced_data.get('course_type')}")
        logger.info(f"  - delivery_method: {enhanced_data.get('delivery_method')}")
        logger.info(f"  - subject_areas: {enhanced_data.get('subject_areas')}")
        logger.info(f"  - ce_broker_ready: {enhanced_data.get('ce_broker_ready')}")

        # Create CPE record with all fields
        cpe_record = CPERecord(
            # Basic fields
            cpa_license_number=license_number,
            user_id=current_user.id if current_user else None,
            document_filename=upload_result.get("file_key", file.filename),
            original_filename=file.filename,
            # Core CPE data
            cpe_credits=enhanced_data.get("cpe_credits", 0.0),
            ethics_credits=enhanced_data.get("ethics_credits", 0.0),
            course_title=enhanced_data.get("course_title"),
            provider=enhanced_data.get("provider"),
            completion_date=enhanced_data.get("completion_date"),
            certificate_number=enhanced_data.get("certificate_number"),
            # CE Broker fields - ENSURE THESE ARE SET
            course_type=enhanced_data.get("course_type"),
            delivery_method=enhanced_data.get("delivery_method"),
            instructional_method=enhanced_data.get("instructional_method"),
            subject_areas=enhanced_data.get(
                "subject_areas", []
            ),  # Default to empty list
            field_of_study=enhanced_data.get("field_of_study"),
            ce_category=enhanced_data.get("ce_category"),
            nasba_sponsor_number=enhanced_data.get("nasba_sponsor_number"),
            course_code=enhanced_data.get("course_code"),
            program_level=enhanced_data.get("program_level"),
            ce_broker_ready=enhanced_data.get("ce_broker_ready", False),
            # Parsing metadata
            confidence_score=parsing_result.get("confidence_score", 0.0),
            parsing_method=parsing_result.get("parsing_method", "google_vision"),
            raw_text=raw_text,
            parsing_notes=parsing_result.get("notes"),
            # System fields
            storage_tier=storage_tier,
            created_at=datetime.now(),
        )

        # ADDITIONAL FIX: Force update CE Broker readiness after creation
        if hasattr(cpe_record, "update_ce_broker_fields"):
            cpe_record.update_ce_broker_fields()

        logger.info(f"CPE record created with CE Broker fields:")
        logger.info(f"  - Final course_type: {cpe_record.course_type}")
        logger.info(f"  - Final delivery_method: {cpe_record.delivery_method}")
        logger.info(f"  - Final subject_areas: {cpe_record.subject_areas}")
        logger.info(f"  - Final ce_broker_ready: {cpe_record.ce_broker_ready}")

        return cpe_record

    except Exception as e:
        logger.error(f"Error in enhanced CPE record creation: {str(e)}")
        logger.exception("Full traceback:")

        # Fallback: create basic record without enhancement
        return CPERecord(
            cpa_license_number=license_number,
            user_id=current_user.id if current_user else None,
            document_filename=upload_result.get("file_key", file.filename),
            original_filename=file.filename,
            cpe_credits=parsed_data.get("cpe_credits", 0.0),
            ethics_credits=parsed_data.get("ethics_credits", 0.0),
            course_title=parsed_data.get("course_title"),
            provider=parsed_data.get("provider"),
            completion_date=parsed_data.get("completion_date"),
            certificate_number=parsed_data.get("certificate_number"),
            raw_text=raw_text,
            storage_tier=storage_tier,
            created_at=datetime.now(),
        )


def debug_ce_broker_extraction(raw_text: str, parsed_data: Dict) -> Dict:
    """Debug helper to test CE Broker field extraction"""

    vision_service = EnhancedVisionService()

    logger.info("=== DEBUG CE BROKER EXTRACTION ===")
    logger.info(f"Raw text preview: {raw_text[:200]}...")
    logger.info(f"Parsed data: {parsed_data}")

    # Test individual extraction methods
    try:
        # Test course type detection
        course_type = vision_service.extract_ce_broker_fields(
            raw_text, parsed_data
        ).get("course_type")
        logger.info(f"Extracted course_type: {course_type}")

        # Test delivery method detection
        delivery_method = vision_service.extract_ce_broker_fields(
            raw_text, parsed_data
        ).get("delivery_method")
        logger.info(f"Extracted delivery_method: {delivery_method}")

        # Test subject areas detection
        subject_areas = vision_service.extract_ce_broker_fields(
            raw_text, parsed_data
        ).get("subject_areas")
        logger.info(f"Extracted subject_areas: {subject_areas}")

        # Full enhancement
        enhanced_data = vision_service.enhance_parsed_data(raw_text, parsed_data)
        logger.info(f"Full enhanced data: {enhanced_data}")

        return enhanced_data

    except Exception as e:
        logger.error(f"Error in debug extraction: {str(e)}")
        logger.exception("Full traceback:")
        return {}
