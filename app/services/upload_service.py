# app/services/upload_service.py - SIMPLIFIED VERSION

import logging
import re
from typing import Dict, Optional
from datetime import datetime, date
from app.models.cpe_record import CPERecord

logger = logging.getLogger(__name__)


def create_cpe_record_from_parsing(
    parsing_result: Dict,
    file,
    license_number: str,
    current_user,
    upload_result: Dict,
    storage_tier: str = "free",
):
    """Create CPE record with core data extraction - SIMPLIFIED VERSION"""

    try:
        # Get basic parsed data
        parsed_data = parsing_result.get("parsed_data", {})
        raw_text = parsing_result.get("raw_text", "")

        logger.info(f"Creating CPE record for license {license_number}")
        logger.info(f"Raw text length: {len(raw_text) if raw_text else 0}")
        logger.info(f"Basic parsed data keys: {list(parsed_data.keys())}")

        # Extract core data from the raw text directly
        core_data = extract_core_cpe_data(raw_text, parsed_data)

        # Create CPE record with clean, focused data
        cpe_record = CPERecord(
            # Basic fields
            cpa_license_number=license_number,
            user_id=current_user.id if current_user else None,
            document_filename=upload_result.get("filename", file.filename),
            original_filename=file.filename,
            # Core CPE data (focus on accuracy)
            cpe_credits=core_data.get("cpe_credits", 0.0),
            ethics_credits=core_data.get("ethics_credits", 0.0),
            course_title=core_data.get("course_title"),
            provider=core_data.get("provider"),
            completion_date=core_data.get("completion_date"),
            certificate_number=core_data.get("certificate_number"),
            # AI parsing metadata
            confidence_score=core_data.get("confidence_score", 0.0),
            parsing_method=(
                "google_vision" if parsing_result.get("success") else "manual"
            ),
            raw_text=raw_text,
            parsing_notes=parsing_result.get("notes"),
            # System fields
            storage_tier=storage_tier,
            is_verified=False,
            created_at=datetime.utcnow(),
        )

        logger.info(f"CPE record created successfully:")
        logger.info(f"  - course_title: {cpe_record.course_title}")
        logger.info(f"  - provider: {cpe_record.provider}")
        logger.info(f"  - cpe_credits: {cpe_record.cpe_credits}")
        logger.info(f"  - confidence_score: {cpe_record.confidence_score}")

        return cpe_record

    except Exception as e:
        logger.error(f"Error creating CPE record: {str(e)}")
        logger.exception("Full traceback:")
        raise


def extract_core_cpe_data(raw_text: str, parsed_data: Dict) -> Dict:
    """
    Extract core CPE data with focus on accuracy over completeness.

    """

    if not raw_text:
        return _empty_result()

    try:
        result = {
            "course_title": _extract_course_title(raw_text),
            "provider": _extract_provider(raw_text),
            "cpe_credits": _extract_cpe_credits(raw_text),
            "ethics_credits": _extract_ethics_credits(raw_text),
            "completion_date": _extract_completion_date(raw_text),
            "certificate_number": _extract_certificate_number(raw_text),
            "confidence_score": _calculate_confidence(raw_text),
        }

        # Only return fields where we have reasonable confidence
        # Remove None/empty values to avoid storing garbage data
        filtered_result = {}
        for key, value in result.items():
            if value is not None and value != "" and value != 0.0:
                filtered_result[key] = value

        return filtered_result

    except Exception as e:
        logger.error(f"Error extracting core CPE data: {e}")
        return _empty_result()


def _extract_course_title(text: str) -> Optional[str]:
    """Extract course title - look for common patterns"""
    patterns = [
        r"(?:course title|title|course|subject):\s*([^\n\r]+)",
        r"(?:successfully completing|completion of)\s+([^\n\r]+)",
        r"certificate of completion\s+(?:for|awarded to).*?(?:for|in)\s+([^\n\r]+)",
        r"(?:course|program):\s*([^\n\r]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # Clean up common artifacts
            title = re.sub(r"^(for|in|of)\s+", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\s+", " ", title)  # Normalize whitespace
            # Remove common prefixes that aren't part of the title
            title = re.sub(
                r"^(code|field of study|cpe credits):\s*",
                "",
                title,
                flags=re.IGNORECASE,
            )

            if len(title) > 10 and len(title) < 200:  # Reasonable length
                return title

    return None


def _extract_provider(text: str) -> Optional[str]:
    """Extract provider/sponsor name"""
    patterns = [
        r"(?:provider|sponsor|sponsored by|offered by):\s*([^\n\r]+)",
        r"^([A-Z][^\n\r]*(?:CPE|Education|Institute|University|College|Academy))",
        r"NASBA\s+Sponsor[^\n\r]*\n([^\n\r]+)",
        r"([A-Z][a-zA-Z\s&]+(?:CPE|Education))",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            provider = match.group(1).strip()
            # Clean up
            provider = re.sub(r"[®™©]", "", provider)
            provider = re.sub(r"\s+", " ", provider)
            # Filter out garbage data
            if (
                len(provider) > 3
                and len(provider) < 100
                and not provider.startswith("s, CPE")
            ):
                return provider

    return None


def _extract_cpe_credits(text: str) -> float:
    """Extract CPE credits - be very precise about this"""
    patterns = [
        r"CPE\s+Credits?:\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s+CPE\s+Credits?",
        r"Credits?:\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s+(?:hours?|credits?)\s+(?:of\s+)?CPE",
        r"CPE\s+Credits?:\s*(\d+(?:\.\d+)?)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                credits = float(matches[0])
                # Reasonable bounds for CPE credits
                if 0.5 <= credits <= 50:
                    return credits
            except ValueError:
                continue

    return 0.0


def _extract_ethics_credits(text: str) -> float:
    """Extract ethics credits if mentioned"""
    patterns = [
        r"Ethics?\s+Credits?:\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s+Ethics?\s+Credits?",
        r"Professional\s+Ethics?\s+CPE:\s*(\d+(?:\.\d+)?)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            try:
                credits = float(matches[0])
                if 0.0 <= credits <= 10:  # Ethics credits are usually smaller
                    return credits
            except ValueError:
                continue

    return 0.0


def _extract_completion_date(text: str) -> Optional[date]:
    """Extract completion date"""
    patterns = [
        r"(?:completion date|completed on|date):\s*(\w+,?\s+\w+\s+\d{1,2},?\s+\d{4})",
        r"(?:date|completed):\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"(\w+\s+\d{1,2},?\s+\d{4})",  # "June 6, 2025"
        r"Date:\s*(\w+,?\s+\w+\s+\d{1,2},?\s+\d{4})",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                parsed_date = _parse_date_string(match)
                if parsed_date:
                    return parsed_date
            except:
                continue

    return None


def _parse_date_string(date_str: str) -> Optional[date]:
    """Parse various date string formats"""
    date_str = date_str.strip()

    formats = [
        "%B %d, %Y",  # "June 6, 2025"
        "%b %d, %Y",  # "Jun 6, 2025"
        "%m/%d/%Y",  # "6/6/2025"
        "%m-%d-%Y",  # "6-6-2025"
        "%Y-%m-%d",  # "2025-06-06"
        "%A, %B %d, %Y",  # "Friday, June 6, 2025"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None


def _extract_certificate_number(text: str) -> Optional[str]:
    """Extract certificate number if present"""
    patterns = [
        r"Certificate\s+(?:Number|#):\s*([A-Z0-9-]+)",
        r"Certificate\s+ID:\s*([A-Z0-9-]+)",
        r"(?:ID|Number):\s*([A-Z0-9-]{5,20})",
        r"Course\s+Code:\s*([A-Z0-9-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            cert_num = match.group(1).strip()
            if len(cert_num) >= 3:
                return cert_num

    return None


def _calculate_confidence(text: str) -> float:
    """Calculate parsing confidence based on data found"""
    confidence = 0.0

    # Key indicators of a valid CPE certificate
    indicators = [
        (r"CPE|Continuing Professional Education", 0.3),
        (r"Certificate of Completion", 0.2),
        (r"Credits?", 0.2),
        (r"NASBA", 0.2),
        (r"CPA", 0.1),
    ]

    for pattern, weight in indicators:
        if re.search(pattern, text, re.IGNORECASE):
            confidence += weight

    return min(confidence, 1.0)


def _empty_result() -> Dict:
    """Return empty result structure"""
    return {
        "course_title": None,
        "provider": None,
        "cpe_credits": 0.0,
        "ethics_credits": 0.0,
        "completion_date": None,
        "certificate_number": None,
        "confidence_score": 0.0,
    }


# ===== BACKWARD COMPATIBILITY =====
# Keep the old function name for existing code
def create_enhanced_cpe_record_from_parsing(*args, **kwargs):
    """Backward compatibility wrapper"""
    return create_cpe_record_from_parsing(*args, **kwargs)
