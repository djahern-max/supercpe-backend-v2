# app/services/provider_detection_service.py
"""
CPE Provider Detection and Template-Based Extraction System

This approach uses a single endpoint but detects the provider and applies
provider-specific extraction templates for higher accuracy.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProviderTemplate:
    """Template for extracting data from specific CPE providers"""

    provider_name: str
    detection_patterns: List[str]  # Patterns to identify this provider
    extraction_rules: Dict[str, List[str]]  # Field -> list of regex patterns
    confidence_multiplier: float = 1.0  # Boost confidence for known providers
    special_processing: Optional[str] = None  # Custom processing method name


class CPEProviderDetectionService:
    """Service to detect CPE providers and apply appropriate extraction templates"""

    def __init__(self):
        self.provider_templates = self._initialize_templates()

    def _initialize_templates(self) -> Dict[str, ProviderTemplate]:
        """Initialize provider-specific extraction templates"""

        templates = {}

        # MasterCPE Template
        templates["mastercpe"] = ProviderTemplate(
            provider_name="MasterCPE Professional Online Education",
            detection_patterns=[
                r"MasterCPE",
                r"Professional Online Education",
                r"Course Code:\s*M\d{3}-\d{4}-\d{2}-[A-Z]+",
                r"Elizabeth Kolar.*Executive Vice President",
            ],
            extraction_rules={
                "course_title": [
                    r"for successfully completing\s*([^\n]+)",
                    r"Course Title:\s*([^\n]+)",
                ],
                "provider": [
                    r"(MasterCPE.*Professional Online Education)",
                    r"(MasterCPE[^\n]*)",
                ],
                "cpe_credits": [r"CPE Credits:\s*(\d+\.?\d*)"],
                "completion_date": [r"Date:\s*([A-Za-z]+,\s*[A-Za-z]+\s+\d+,\s*\d{4})"],
                "certificate_number": [r"Course Code:\s*([M]\d{3}-\d{4}-\d{2}-[A-Z]+)"],
                "subject_area": [r"Field of Study:\s*([^\n]+)"],
                "instructional_method": [r"Instructional Method:\s*([^\n]+)"],
            },
            confidence_multiplier=1.2,
        )

        # AICPA Template
        templates["aicpa"] = ProviderTemplate(
            provider_name="American Institute of CPAs",
            detection_patterns=[
                r"AICPA",
                r"American Institute of CPAs",
                r"aicpa\.org",
                r"AICPA\s*#\d+",
            ],
            extraction_rules={
                "course_title": [
                    r"Course:\s*([^\n]+)",
                    r"Program:\s*([^\n]+)",
                    r"successfully completed\s*([^\n]+)",
                ],
                "provider": [r"(American Institute of CPAs)", r"(AICPA[^\n]*)"],
                "cpe_credits": [
                    r"CPE Hours?:\s*(\d+\.?\d*)",
                    r"Credits?:\s*(\d+\.?\d*)",
                ],
                "completion_date": [
                    r"Completion Date:\s*(\d{1,2}/\d{1,2}/\d{4})",
                    r"Date Completed:\s*([^\n]+)",
                ],
            },
            confidence_multiplier=1.1,
        )

        # Surgent Template
        templates["surgent"] = ProviderTemplate(
            provider_name="Surgent CPE",
            detection_patterns=[r"Surgent", r"surgentcpe\.com", r"Surgent CPE"],
            extraction_rules={
                "course_title": [r"Course Title:\s*([^\n]+)", r"completed\s*([^\n]+)"],
                "provider": [r"(Surgent[^\n]*)", r"(Surgent CPE)"],
                "cpe_credits": [r"CPE Credit Hours?:\s*(\d+\.?\d*)"],
                "completion_date": [r"Date of Completion:\s*(\d{1,2}/\d{1,2}/\d{4})"],
            },
        )

        # Becker Template
        templates["becker"] = ProviderTemplate(
            provider_name="Becker Professional Education",
            detection_patterns=[
                r"Becker",
                r"beckercpe\.com",
                r"Becker Professional Education",
            ],
            extraction_rules={
                "course_title": [
                    r"Course:\s*([^\n]+)",
                    r"successfully completed\s*([^\n]+)",
                ],
                "provider": [r"(Becker Professional Education)", r"(Becker[^\n]*)"],
                "cpe_credits": [r"CPE Hours?:\s*(\d+\.?\d*)"],
            },
        )

        # Generic/Unknown Provider Template (fallback)
        templates["generic"] = ProviderTemplate(
            provider_name="Unknown Provider",
            detection_patterns=[],  # No detection patterns - this is the fallback
            extraction_rules={
                "course_title": [
                    r"(?:course title|course name|title|course|subject):\s*([^\n\r]+)",
                    r"(?:successfully completing|completion of)\s+([^\n\r]+)",
                    r"certificate of completion\s+(?:for|awarded to).*?(?:for|in)\s+([^\n\r]+)",
                ],
                "provider": [
                    r"(?:provider|sponsor|sponsored by|offered by):\s*([^\n\r]+)",
                    r"([A-Z][A-Za-z\s]+(?:University|College|Institute|Education|Learning|Training))",
                ],
                "cpe_credits": [
                    r"(?:cpe|credit|hour)s?:\s*(\d+\.?\d*)",
                    r"(\d+\.?\d*)\s*(?:cpe|credit|hour)s?",
                ],
                "completion_date": [
                    r"(?:date|completed|completion):\s*(\d{1,2}/\d{1,2}/\d{4})",
                    r"(\d{1,2}/\d{1,2}/\d{4})",
                ],
            },
            confidence_multiplier=0.7,  # Lower confidence for generic extraction
        )

        return templates

    def detect_provider(self, raw_text: str) -> Tuple[str, ProviderTemplate]:
        """
        Detect the CPE provider from certificate text
        Returns (provider_key, template)
        """

        for provider_key, template in self.provider_templates.items():
            if provider_key == "generic":
                continue  # Skip generic, it's our fallback

            # Check if any detection patterns match
            for pattern in template.detection_patterns:
                if re.search(pattern, raw_text, re.IGNORECASE):
                    logger.info(
                        f"Detected provider: {provider_key} using pattern: {pattern}"
                    )
                    return provider_key, template

        # No specific provider detected, use generic
        logger.info("No specific provider detected, using generic template")
        return "generic", self.provider_templates["generic"]

    def extract_with_template(self, raw_text: str, template: ProviderTemplate) -> Dict:
        """Extract data using provider-specific template"""

        extracted_data = {}

        for field, patterns in template.extraction_rules.items():
            for pattern in patterns:
                match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    extracted_data[field] = match.group(1).strip()
                    break

        # Calculate confidence based on template and found fields
        base_confidence = len(extracted_data) / max(len(template.extraction_rules), 1)
        final_confidence = min(1.0, base_confidence * template.confidence_multiplier)

        extracted_data["confidence_score"] = final_confidence
        extracted_data["provider_template"] = template.provider_name

        return extracted_data

    def process_certificate(self, raw_text: str) -> Dict:
        """
        Main processing method: detect provider and extract data
        """

        # Step 1: Detect provider
        provider_key, template = self.detect_provider(raw_text)

        # Step 2: Extract data using template
        extracted_data = self.extract_with_template(raw_text, template)

        # Step 3: Add metadata
        extracted_data.update(
            {
                "detected_provider": provider_key,
                "provider_name": template.provider_name,
                "parsing_method": f"template_{provider_key}",
                "extraction_timestamp": datetime.utcnow().isoformat(),
            }
        )

        return extracted_data


# Integration with your existing vision service
class EnhancedVisionServiceWithProviders:
    """Enhanced version of your vision service with provider detection"""

    def __init__(self):
        self.provider_service = CPEProviderDetectionService()
        # ... your existing vision service initialization

    def parse_cpe_certificate(self, raw_text: str, filename: str = "") -> Dict:
        """
        Enhanced parsing with provider detection
        This replaces your existing parse_cpe_certificate method
        """

        try:
            # Use provider detection for extraction
            result = self.provider_service.process_certificate(raw_text)

            # Map to your existing format for backward compatibility
            return self._map_to_legacy_format(result)

        except Exception as e:
            logger.error(f"Provider-based parsing failed: {e}")
            # Fallback to your existing generic parsing
            return self._legacy_parse_cpe_certificate(raw_text)

    def _map_to_legacy_format(self, provider_result: Dict) -> Dict:
        """Map provider-based results to your existing format"""

        return {
            "course_title": provider_result.get("course_title"),
            "provider": provider_result.get("provider"),
            "cpe_credits": self._safe_float(provider_result.get("cpe_credits", 0)),
            "ethics_credits": self._safe_float(
                provider_result.get("ethics_credits", 0)
            ),
            "completion_date": provider_result.get("completion_date"),
            "certificate_number": provider_result.get("certificate_number"),
            "confidence_score": provider_result.get("confidence_score", 0.5),
            "parsing_method": provider_result.get(
                "parsing_method", "provider_template"
            ),
            # Additional metadata
            "detected_provider": provider_result.get("detected_provider"),
            "provider_template": provider_result.get("provider_name"),
            "subject_area": provider_result.get("subject_area"),
            "instructional_method": provider_result.get("instructional_method"),
        }

    def _safe_float(self, value) -> float:
        """Safely convert value to float"""
        try:
            return float(value) if value else 0.0
        except (ValueError, TypeError):
            return 0.0
