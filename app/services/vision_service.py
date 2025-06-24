# app/services/vision_service.py - FIXED VERSION

import logging
import re
import io
from typing import Dict, Optional, List
from datetime import datetime, date
from google.cloud import vision
from pdf2image import convert_from_bytes
from PIL import Image

logger = logging.getLogger(__name__)


class EnhancedVisionService:
    """Enhanced vision service for CPE certificate processing using Google Cloud Vision"""

    def __init__(self):
        self.client = vision.ImageAnnotatorClient()

    def extract_text_from_image(self, image_content: bytes) -> str:
        """Extract raw text from image using Google Vision API"""
        try:
            image = vision.Image(content=image_content)
            response = self.client.text_detection(image=image)

            if response.error.message:
                raise Exception(f"Google Vision API error: {response.error.message}")

            # Get the full text
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
        """Extract text from PDF or image based on content type

        FIXED: Now accepts content_type parameter to handle both PDFs and images
        """
        try:
            logger.info(
                f"Processing file with content_type: {content_type}, size: {len(content)} bytes"
            )

            # Handle images directly
            if content_type and content_type.startswith("image/"):
                logger.info("Processing as image file")
                return self.extract_text_from_image(content)

            # Handle PDFs (default behavior)
            logger.info("Processing as PDF file")

            # Convert PDF to images using pdf2image
            images = convert_from_bytes(content, dpi=300, first_page=1, last_page=3)
            logger.info(f"Converted PDF to {len(images)} images")

            full_text = ""

            for i, image in enumerate(images):
                try:
                    # Convert PIL Image to bytes
                    img_byte_arr = io.BytesIO()
                    image.save(img_byte_arr, format="PNG")
                    img_byte_arr = img_byte_arr.getvalue()

                    # Extract text from this page using Google Vision
                    page_text = self.extract_text_from_image(img_byte_arr)

                    if page_text:
                        full_text += f"\n--- Page {i+1} ---\n{page_text}\n"
                        logger.info(
                            f"Extracted {len(page_text)} characters from page {i+1}"
                        )
                    else:
                        logger.warning(f"No text extracted from page {i+1}")

                except Exception as page_error:
                    logger.error(f"Error processing page {i+1}: {page_error}")
                    continue

            logger.info(f"Total extracted text length: {len(full_text)}")

            # Log a sample of the extracted text for debugging
            if full_text:
                sample = full_text[:200].replace("\n", " ")
                logger.info(f"Extracted text sample: {sample}...")
            else:
                logger.error("No text was extracted from any pages!")

            return full_text.strip()

        except Exception as e:
            logger.error(f"Error extracting text from file: {e}")
            logger.exception("Full file processing error:")
            return ""

    def parse_cpe_certificate(self, raw_text: str) -> Dict:
        """
        Parse core CPE data from raw text.
        Focus on reliability over completeness.
        """
        if not raw_text:
            logger.warning("No raw text provided to parse_cpe_certificate")
            return self._empty_result()

        logger.info(f"Parsing certificate with {len(raw_text)} characters of text")

        try:
            result = {
                "course_title": self._extract_course_title(raw_text),
                "provider": self._extract_provider(raw_text),
                "cpe_credits": self._extract_cpe_credits(raw_text),
                "ethics_credits": self._extract_ethics_credits(raw_text),
                "completion_date": self._extract_completion_date(raw_text),
                "certificate_number": self._extract_certificate_number(raw_text),
                "confidence_score": self._calculate_confidence(raw_text),
            }

            # Log what we found
            logger.info(f"Parsing results:")
            for key, value in result.items():
                if value is not None and value != "" and value != 0.0:
                    logger.info(f"  {key}: {value}")

            # Only return fields where we have reasonable confidence
            filtered_result = {}
            for key, value in result.items():
                if value is not None and value != "" and value != 0.0:
                    filtered_result[key] = value

            logger.info(f"Filtered results: {len(filtered_result)} fields")
            return filtered_result

        except Exception as e:
            logger.error(f"Error parsing certificate: {e}")
            logger.exception("Full parsing error:")
            return self._empty_result()

    def _extract_course_title(self, text: str) -> Optional[str]:
        """Extract course title - look for common patterns"""
        patterns = [
            r"(?:course title|course name|title|course|subject):\s*([^\n\r]+)",
            r"(?:successfully completing|completion of)\s+([^\n\r]+)",
            r"certificate of completion\s+(?:for|awarded to).*?(?:for|in)\s+([^\n\r]+)",
            r"(?:course|program|seminar):\s*([^\n\r]+)",
            r"subject:\s*([^\n\r]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                title = match.group(1).strip()
                # Clean up common artifacts
                title = re.sub(r"^(for|in|of)\s+", "", title, flags=re.IGNORECASE)
                title = re.sub(r"\s+", " ", title)  # Normalize whitespace
                title = title.strip()

                if len(title) > 5 and len(title) < 200:  # Reasonable length
                    logger.info(f"Found course title: {title}")
                    return title

        return None

    def _extract_provider(self, text: str) -> Optional[str]:
        """Extract provider/sponsor name"""
        patterns = [
            r"(?:provider|sponsor|sponsored by|offered by|presenter):\s*([^\n\r]+)",
            r"^([A-Z][^\n\r]*(?:CPE|Education|Institute|University|College|Academy))",
            r"NASBA\s+Sponsor[^\n\r]*\n([^\n\r]+)",
            r"([A-Z][a-zA-Z\s&,\.]+(?:LLC|Inc|Corporation|Institute|Academy|University))",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                provider = match.group(1).strip()
                # Clean up
                provider = re.sub(r"[®™©]", "", provider)
                provider = re.sub(r"\s+", " ", provider)
                provider = provider.strip()

                if len(provider) > 3 and len(provider) < 100:
                    logger.info(f"Found provider: {provider}")
                    return provider

        return None

    def _extract_cpe_credits(self, text: str) -> float:
        """Extract CPE credits - be very precise about this"""
        patterns = [
            r"CPE\s+Credits?:\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s+CPE\s+Credits?",
            r"Credits?:\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s+(?:hours?|credits?)\s+(?:of\s+)?CPE",
            r"(\d+(?:\.\d+)?)\s+CPE\s+(?:hours?|credits?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    credits = float(match.group(1))
                    if 0.0 < credits <= 50.0:  # Reasonable range
                        logger.info(f"Found CPE credits: {credits}")
                        return credits
                except ValueError:
                    continue

        return 0.0

    def _extract_ethics_credits(self, text: str) -> float:
        """Extract ethics credits"""
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
                    if 0.0 < credits <= 20.0:  # Reasonable range
                        logger.info(f"Found ethics credits: {credits}")
                        return credits
                except ValueError:
                    continue

        return 0.0

    def _extract_completion_date(self, text: str) -> Optional[date]:
        """Extract completion date"""
        patterns = [
            r"(?:completion date|completed|date completed):\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(?:on|dated)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    # Try different date formats
                    for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y"]:
                        try:
                            parsed_date = datetime.strptime(match, fmt).date()
                            # Validate reasonable date range
                            if (
                                datetime(2000, 1, 1).date()
                                <= parsed_date
                                <= datetime.now().date()
                            ):
                                logger.info(f"Found completion date: {parsed_date}")
                                return parsed_date
                        except ValueError:
                            continue
                except Exception:
                    continue

        return None

    def _extract_certificate_number(self, text: str) -> Optional[str]:
        """Extract certificate number"""
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
                    logger.info(f"Found certificate number: {cert_num}")
                    return cert_num

        return None

    def _calculate_confidence(self, text: str) -> float:
        """Calculate confidence score based on found indicators"""
        confidence = 0.0

        # Indicators that suggest this is a CPE certificate
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

        logger.info(f"Calculated confidence score: {confidence}")
        return min(confidence, 1.0)

    def _empty_result(self) -> Dict:
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


# Backward compatibility - keep the SimplifiedVisionService name too
SimplifiedVisionService = EnhancedVisionService
