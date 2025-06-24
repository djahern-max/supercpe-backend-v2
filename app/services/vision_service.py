# FILE 2: app/services/vision_service.py (UPDATED)
"""
Enhanced Vision Service with Smart Review Integration
"""

import logging
import re
import io
from typing import Dict, Optional, List
from datetime import datetime, date
from google.cloud import vision
from pdf2image import convert_from_bytes
from PIL import Image

# Import our new smart reviewer
from app.services.smart_certificate_reviewer import SmartCertificateReviewer

logger = logging.getLogger(__name__)


class EnhancedVisionService:
    """Enhanced vision service with smart review capabilities"""

    def __init__(self):
        self.client = vision.ImageAnnotatorClient()
        self.smart_reviewer = SmartCertificateReviewer()

    def extract_text_from_image(self, image_content: bytes) -> str:
        """Extract raw text from image using Google Vision API"""
        try:
            image = vision.Image(content=image_content)
            response = self.client.text_detection(image=image)

            if response.error.message:
                raise Exception(f"Google Vision API error: {response.error.message}")

            texts = response.text_annotations
            if texts:
                return texts[0].description
            return ""

        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            return ""

    async def extract_text_from_pdf(
        self, content: bytes, content_type: str = None
    ) -> str:
        """Extract text from PDF or image based on content type"""
        try:
            logger.info(
                f"Processing file with content_type: {content_type}, size: {len(content)} bytes"
            )

            # Handle images directly
            if content_type and content_type.startswith("image/"):
                logger.info("Processing as image file")
                return self.extract_text_from_image(content)

            # Handle PDFs
            logger.info("Processing as PDF file")

            images = convert_from_bytes(content, dpi=300, first_page=1, last_page=3)
            logger.info(f"Converted PDF to {len(images)} images")

            full_text = ""
            for i, image in enumerate(images):
                try:
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format="PNG")
                    img_byte_arr = img_byte_arr.getvalue()

                    page_text = self.extract_text_from_image(img_byte_arr)
                    if page_text:
                        full_text += f"\n--- Page {i+1} ---\n{page_text}\n"
                        logger.info(
                            f"Extracted {len(page_text)} characters from page {i+1}"
                        )

                except Exception as page_error:
                    logger.error(f"Error processing page {i+1}: {page_error}")
                    continue

            logger.info(f"Total extracted text length: {len(full_text)}")
            return full_text.strip()

        except Exception as e:
            logger.error(f"Error extracting text from file: {e}")
            return ""

    def parse_cpe_certificate(self, raw_text: str, filename: str = "") -> Dict:
        """
        NEW: Enhanced parsing using Smart Review System
        Returns both simple data (backward compatibility) and rich insights
        """
        if not raw_text:
            logger.warning("No raw text provided to parse_cpe_certificate")
            return self._legacy_empty_result()

        logger.info(f"Enhanced parsing certificate with {len(raw_text)} characters")

        try:
            # Use smart reviewer for enhanced processing
            smart_result = self.smart_reviewer.process_raw_text(raw_text, filename)

            # For backward compatibility, return the extracted_data at the top level
            # But also include the rich insights for the new review interface
            legacy_format = smart_result["extracted_data"].copy()
            legacy_format.update(
                {
                    "confidence_score": smart_result["confidence_score"],
                    # NEW: Add smart review data
                    "smart_insights": smart_result["insights"],
                    "suggestions": smart_result["suggestions"],
                    "review_flags": smart_result["review_flags"],
                    "processing_method": "smart_review",
                }
            )

            logger.info(
                f"Enhanced parsing complete - confidence: {smart_result['confidence_score']:.2f}"
            )
            logger.info(
                f"Found {len(smart_result['suggestions'])} suggestions for user review"
            )

            return legacy_format

        except Exception as e:
            logger.error(f"Error in enhanced parsing: {e}")
            logger.exception("Full parsing error:")
            # Fallback to legacy parsing
            return self._legacy_parse_cpe_certificate(raw_text)

    def _legacy_parse_cpe_certificate(self, raw_text: str) -> Dict:
        """Fallback to original simple parsing if smart review fails"""
        logger.info("Using legacy parsing as fallback")

        try:
            result = {
                "course_title": self._extract_course_title(raw_text),
                "provider": self._extract_provider(raw_text),
                "cpe_credits": self._extract_cpe_credits(raw_text),
                "ethics_credits": self._extract_ethics_credits(raw_text),
                "completion_date": self._extract_completion_date(raw_text),
                "certificate_number": self._extract_certificate_number(raw_text),
                "confidence_score": self._calculate_confidence(raw_text),
                "processing_method": "legacy_fallback",
            }

            # Remove None/empty values
            filtered_result = {}
            for key, value in result.items():
                if value is not None and value != "" and value != 0.0:
                    filtered_result[key] = value

            return filtered_result

        except Exception as e:
            logger.error(f"Error in legacy parsing: {e}")
            return self._legacy_empty_result()

    # Keep all the original methods for backward compatibility
    def _extract_course_title(self, text: str) -> Optional[str]:
        """Original course title extraction"""
        patterns = [
            r"(?:course title|course name|title|course|subject):\s*([^\n\r]+)",
            r"(?:successfully completing|completion of)\s+([^\n\r]+)",
            r"certificate of completion\s+(?:for|awarded to).*?(?:for|in)\s+([^\n\r]+)",
            r"(?:course|program|seminar):\s*([^\n\r]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                title = match.group(1).strip()
                title = re.sub(r"^(for|in|of)\s+", "", title, flags=re.IGNORECASE)
                title = re.sub(r"\s+", " ", title)

                if len(title) > 5 and len(title) < 200:
                    return title
        return None

    def _extract_provider(self, text: str) -> Optional[str]:
        """Original provider extraction"""
        patterns = [
            r"(?:provider|sponsor|sponsored by|offered by|presenter):\s*([^\n\r]+)",
            r"^([A-Z][^\n\r]*(?:CPE|Education|Institute|University|College|Academy))",
            r"NASBA\s+Sponsor[^\n\r]*\n([^\n\r]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                provider = match.group(1).strip()
                provider = re.sub(r"[®™©]", "", provider)
                provider = re.sub(r"\s+", " ", provider)

                if len(provider) > 3 and len(provider) < 100:
                    return provider
        return None

    def _extract_cpe_credits(self, text: str) -> float:
        """Original CPE credits extraction"""
        patterns = [
            r"CPE\s+Credits?:\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s+CPE\s+Credits?",
            r"Credits?:\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s+(?:hours?|credits?)\s+(?:of\s+)?CPE",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    credits = float(match.group(1))
                    if 0.0 < credits <= 50.0:
                        return credits
                except ValueError:
                    continue
        return 0.0

    def _extract_ethics_credits(self, text: str) -> float:
        """Original ethics credits extraction"""
        patterns = [
            r"Ethics\s+Credits?:\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s+Ethics\s+Credits?",
            r"Ethics:\s*(\d+(?:\.\d+)?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    credits = float(match.group(1))
                    if 0.0 < credits <= 20.0:
                        return credits
                except ValueError:
                    continue
        return 0.0

    def _extract_completion_date(self, text: str) -> Optional[date]:
        """Original completion date extraction"""
        patterns = [
            r"(?:completion date|completed|date completed):\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y"]:
                        try:
                            parsed_date = datetime.strptime(match, fmt).date()
                            if (
                                datetime(2000, 1, 1).date()
                                <= parsed_date
                                <= datetime.now().date()
                            ):
                                return parsed_date
                        except ValueError:
                            continue
                except Exception:
                    continue
        return None

    def _extract_certificate_number(self, text: str) -> Optional[str]:
        """Original certificate number extraction"""
        patterns = [
            r"(?:certificate|cert|reference)\s+(?:number|#|no):\s*([A-Z0-9-]+)",
            r"(?:confirmation|ref)\s+(?:number|#|no):\s*([A-Z0-9-]+)",
            r"#([A-Z0-9-]{5,})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                cert_num = match.group(1).strip()
                if len(cert_num) >= 5:
                    return cert_num
        return None

    def _calculate_confidence(self, text: str) -> float:
        """Original confidence calculation"""
        confidence = 0.0
        indicators = [
            (r"CPE|Continuing Professional Education", 0.3),
            (r"certificate", 0.2),
            (r"completion", 0.2),
            (r"credits?", 0.2),
            (r"NASBA", 0.2),
            (r"CPA", 0.1),
        ]

        for pattern, weight in indicators:
            if re.search(pattern, text, re.IGNORECASE):
                confidence += weight

        return min(confidence, 1.0)

    def _legacy_empty_result(self) -> Dict:
        """Return empty result in legacy format"""
        return {
            "course_title": None,
            "provider": None,
            "cpe_credits": 0.0,
            "ethics_credits": 0.0,
            "completion_date": None,
            "certificate_number": None,
            "confidence_score": 0.0,
            "processing_method": "legacy",
        }


# Backward compatibility
SimplifiedVisionService = EnhancedVisionService
