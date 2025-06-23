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

        # 🔥 CRITICAL FIX: Flatten the parsed data first
        flat_parsed_data = {}
        for key, value in parsed_data.items():
            if isinstance(value, dict) and "value" in value:
                flat_parsed_data[key] = value["value"]
            else:
                flat_parsed_data[key] = value

        # Enhance with CE Broker fields using the flattened data
        enhanced_data = vision_service.enhance_parsed_data(raw_text, flat_parsed_data)

        # Parse completion date
        completion_date_str = flat_parsed_data.get("completion_date", "")
        parsed_completion_date = None
        if completion_date_str:
            try:
                parsed_completion_date = datetime.fromisoformat(
                    completion_date_str
                ).date()
            except (ValueError, AttributeError):
                try:
                    parsed_completion_date = datetime.strptime(
                        completion_date_str, "%Y-%m-%d"
                    ).date()
                except (ValueError, AttributeError):
                    parsed_completion_date = datetime.utcnow().date()
        else:
            parsed_completion_date = datetime.utcnow().date()

        # Create CPE record with enhanced data
        cpe_record = CPERecord(
            # Basic fields
            cpa_license_number=license_number,
            user_id=current_user.id if current_user else None,
            document_filename=upload_result.get("filename", file.filename),
            original_filename=file.filename,
            # Core CPE data - Use the flattened data
            cpe_credits=float(enhanced_data.get("cpe_credits", 0.0)),
            ethics_credits=float(enhanced_data.get("ethics_credits", 0.0)),
            course_title=enhanced_data.get("course_title", "Manual Entry Required"),
            provider=enhanced_data.get("provider", "Unknown Provider"),
            completion_date=parsed_completion_date,
            certificate_number=enhanced_data.get("certificate_number", ""),
            # CE Broker fields
            course_type=enhanced_data.get("course_type"),
            delivery_method=enhanced_data.get("delivery_method"),
            instructional_method=enhanced_data.get("instructional_method"),
            subject_areas=enhanced_data.get("subject_areas", []),
            field_of_study=enhanced_data.get("field_of_study"),
            ce_category=enhanced_data.get("ce_category"),
            nasba_sponsor_number=enhanced_data.get("nasba_sponsor_number"),
            course_code=enhanced_data.get("course_code"),
            program_level=enhanced_data.get("program_level"),
            ce_broker_ready=enhanced_data.get("ce_broker_ready", False),
            # System fields
            confidence_score=parsing_result.get("confidence_score", 0.0),
            parsing_method=(
                "google_vision"
                if parsing_result and parsing_result.get("success")
                else "manual"
            ),
            raw_text=raw_text,
            storage_tier=storage_tier,
            is_verified=False,
            created_at=datetime.utcnow(),
        )

        logger.info(f"Enhanced CPE record created:")
        logger.info(f"  - course_title: {cpe_record.course_title}")
        logger.info(f"  - provider: {cpe_record.provider}")
        logger.info(f"  - cpe_credits: {cpe_record.cpe_credits}")

        return cpe_record

    except Exception as e:
        logger.error(f"Enhancement failed: {str(e)}")
        logger.exception("Full traceback:")
        raise


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
