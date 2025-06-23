# app/services/vision_service.py - IMPROVED VERSION FOR CPE CERTIFICATE PARSING

import logging
import re
from typing import Dict, List, Optional, Union
from datetime import datetime, date
import tempfile
import os

logger = logging.getLogger(__name__)


class EnhancedVisionService:
    """Enhanced Vision Service for CPE Certificate parsing with improved extraction"""

    def __init__(self):
        """Initialize the Enhanced Vision Service with Google Vision API"""
        try:
            from google.cloud import vision

            # Initialize Google Vision client
            self.vision_client = vision.ImageAnnotatorClient()
            logger.info("Google Vision API client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Google Vision API: {e}")
            self.vision_client = None

    def extract_text_from_file(self, file_content: bytes, content_type: str) -> str:
        """Extract text from uploaded file using Google Vision API"""
        try:
            if not self.vision_client:
                logger.error("Google Vision client not initialized")
                return ""

            logger.info(f"Processing file with content type: {content_type}")

            # Create Vision API image object
            from google.cloud import vision

            image = vision.Image(content=file_content)

            # CRITICAL FIX: Specify features explicitly
            features = [vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION)]

            # Create the request with image and features
            request = vision.AnnotateImageRequest(image=image, features=features)

            # Make the API call
            response = self.vision_client.annotate_image(request=request)

            if response.error.message:
                logger.error(f"Google Vision API error: {response.error.message}")
                return ""

            # Extract text from response
            if response.text_annotations:
                extracted_text = response.text_annotations[0].description
                logger.info(f"Successfully extracted {len(extracted_text)} characters")
                logger.debug(f"Extracted text preview: {extracted_text[:200]}...")
                return extracted_text
            else:
                logger.warning("No text found in document")
                return ""

        except Exception as e:
            logger.error(f"Google Vision text extraction failed: {e}")
            return ""

    def parse_certificate_data(self, raw_text: str, filename: str) -> Dict:
        """Parse structured data from raw certificate text - IMPROVED VERSION"""

        if not raw_text:
            logger.warning("No raw text available for parsing")
            return self._create_empty_parse_result()

        try:
            logger.info("Starting enhanced certificate parsing...")
            logger.debug(f"Raw text to parse: {raw_text[:500]}...")

            # Extract all fields using improved patterns
            cpe_credits = self._extract_cpe_credits(raw_text)
            ethics_credits = self._extract_ethics_credits(raw_text)
            course_title = self._extract_course_title(raw_text)
            provider = self._extract_provider(raw_text)
            completion_date = self._extract_completion_date(raw_text)
            certificate_number = self._extract_certificate_number(raw_text)
            course_code = self._extract_course_code(raw_text)
            field_of_study = self._extract_field_of_study(raw_text)
            instructional_method = self._extract_instructional_method(raw_text)
            nasba_sponsor = self._extract_nasba_sponsor(raw_text)

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                {
                    "cpe_credits": cpe_credits,
                    "course_title": course_title,
                    "provider": provider,
                    "completion_date": completion_date,
                }
            )

            result = {
                "cpe_credits": cpe_credits,
                "ethics_credits": ethics_credits,
                "course_title": course_title,
                "provider": provider,
                "completion_date": completion_date,
                "certificate_number": certificate_number,
                "course_code": course_code,
                "field_of_study": field_of_study,
                "instructional_method": instructional_method,
                "nasba_sponsor": nasba_sponsor,
                "confidence_score": confidence_score,
            }

            logger.info(f"Parsing completed with confidence: {confidence_score:.2f}")
            logger.info(f"Extracted data summary:")
            logger.info(f"  - CPE Credits: {cpe_credits}")
            logger.info(f"  - Course: '{course_title}'")
            logger.info(f"  - Provider: '{provider}'")
            logger.info(f"  - Date: '{completion_date}'")
            logger.info(f"  - Field of Study: '{field_of_study}'")
            logger.info(f"  - Course Code: '{course_code}'")

            return result

        except Exception as e:
            logger.error(f"Certificate parsing failed: {e}")
            return self._create_empty_parse_result()

    def _extract_cpe_credits(self, text: str) -> float:
        """Extract CPE credit hours from text - IMPROVED"""
        patterns = [
            # "CPE Credits: 18.00" format
            r"CPE\s*Credits?[:\s]*(\d+(?:\.\d+)?)",
            # "18.00 CPE" format
            r"(\d+(?:\.\d+)?)\s*CPE",
            # Generic credit patterns
            r"(\d+(?:\.\d+)?)\s*(?:cpe|CPE|credit|hours?|hrs?)",
            r"(?:cpe|CPE|credit|hours?|hrs?)[:\s]*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*(?:continuing|professional|education)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    credits = float(matches[0])
                    logger.info(f"Found CPE credits: {credits}")
                    return credits
                except (ValueError, TypeError):
                    continue

        logger.warning("No CPE credits found")
        return 0.0

    def _extract_ethics_credits(self, text: str) -> float:
        """Extract ethics credit hours from text"""
        patterns = [
            r"Ethics?[:\s]*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*Ethics?",
            r"Professional\s*Ethics?[:\s]*(\d+(?:\.\d+)?)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    credits = float(matches[0])
                    logger.info(f"Found ethics credits: {credits}")
                    return credits
                except (ValueError, TypeError):
                    continue

        return 0.0

    def _extract_course_title(self, text: str) -> str:
        """Extract course title from text - IMPROVED"""
        # Look for common certificate patterns
        patterns = [
            # "for successfully completing [TITLE]"
            r"for\s+successfully\s+completing\s+(.+?)(?:\n|Course\s*Code|Field\s*of\s*Study|CPE|$)",
            # "Certificate of Completion" followed by title
            r"CERTIFICATE\s+OF\s+COMPLETION.+?awarded\s+to.+?for\s+successfully\s+completing\s+(.+?)(?:\n|Course|Field|CPE|$)",
            # Title before "Course Code"
            r"(.+?)(?:\s*Course\s*Code[:\s])",
            # Title on its own line (common pattern)
            r"\n\s*([A-Z][^0-9\n]{10,80})\s*\n",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                title = matches[0].strip()
                # Clean up the title
                title = re.sub(r"\s+", " ", title)  # Remove extra spaces
                title = title.replace("\n", " ").strip()

                # Skip if it's too short or contains unwanted patterns
                if len(title) > 5 and not re.search(
                    r"(certificate|completion|awarded)", title, re.IGNORECASE
                ):
                    logger.info(f"Found course title: '{title}'")
                    return title

        logger.warning("No course title found")
        return ""

    def _extract_provider(self, text: str) -> str:
        """Extract provider/organization from text - IMPROVED"""
        # Look for common provider patterns
        patterns = [
            # MasterCPE, other branded names
            r"(Master\s*CPE|MasterCPE)",
            r"(AICPA|CPA\s*Academy|Surgent|Becker|Kaplan)",
            # Organization patterns
            r"(?:provider|organization|sponsor)[:\s]*(.+?)(?:\n|$)",
            # Executive/signature lines often have company names
            r"Executive\s+Vice\s+President,\s*(.+?)(?:\n|$)",
            # Look for "Professional [something] Education"
            r"Professional\s+(.+?)\s+Education",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                provider = matches[0].strip()
                if len(provider) > 2:
                    logger.info(f"Found provider: '{provider}'")
                    return provider

        logger.warning("No provider found")
        return ""

    def _extract_completion_date(self, text: str) -> str:
        """Extract completion date from text - IMPROVED"""
        # Date patterns specific to your certificate format
        patterns = [
            # "Date: Monday, June 2, 2025" format
            r"Date[:\s]*([A-Za-z]+,\s*[A-Za-z]+\s+\d{1,2},\s*\d{4})",
            # "Monday, June 2, 2025" format
            r"([A-Za-z]+,\s*[A-Za-z]+\s+\d{1,2},\s*\d{4})",
            # Standard date formats
            r"(?:date|completed|completion)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{4}-\d{1,2}-\d{1,2})",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                date_str = matches[0].strip()
                try:
                    # Parse different date formats
                    if "," in date_str and any(
                        month in date_str
                        for month in [
                            "January",
                            "February",
                            "March",
                            "April",
                            "May",
                            "June",
                            "July",
                            "August",
                            "September",
                            "October",
                            "November",
                            "December",
                        ]
                    ):
                        # "Monday, June 2, 2025" format
                        date_str_clean = re.sub(
                            r"^[A-Za-z]+,\s*", "", date_str
                        )  # Remove day of week
                        parsed_date = datetime.strptime(date_str_clean, "%B %d, %Y")
                    elif "/" in date_str or "-" in date_str:
                        # Try various numeric formats
                        date_str = date_str.replace("-", "/")
                        try:
                            parsed_date = datetime.strptime(date_str, "%m/%d/%Y")
                        except ValueError:
                            parsed_date = datetime.strptime(date_str, "%Y/%m/%d")
                    else:
                        continue

                    formatted_date = parsed_date.strftime("%Y-%m-%d")
                    logger.info(f"Found completion date: {formatted_date}")
                    return formatted_date

                except ValueError as e:
                    logger.debug(f"Failed to parse date '{date_str}': {e}")
                    continue

        logger.warning("No completion date found")
        return ""

    def _extract_certificate_number(self, text: str) -> str:
        """Extract certificate number from text"""
        patterns = [
            r"(?:certificate|cert|confirmation)(?:\s+#|\s+number|#)[:\s]*([A-Z0-9-]+)",
            r"#([A-Z0-9-]{4,})",
            r"Certificate\s*#[:\s]*([A-Z0-9-]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                cert_num = matches[0].strip()
                logger.info(f"Found certificate number: {cert_num}")
                return cert_num

        return ""

    def _extract_course_code(self, text: str) -> str:
        """Extract course code from text - IMPROVED"""
        patterns = [
            # "Course Code: M290-2024-01-SSDL" format
            r"Course\s*Code[:\s]*([A-Z0-9-]+)",
            # Generic code patterns
            r"Code[:\s]*([A-Z0-9-]{4,})",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                code = matches[0].strip()
                logger.info(f"Found course code: {code}")
                return code

        return ""

    def _extract_field_of_study(self, text: str) -> str:
        """Extract field of study from text - IMPROVED"""
        patterns = [
            # "Field of Study: Taxes" format
            r"Field\s*of\s*Study[:\s]*([A-Za-z\s]+?)(?:\n|CPE|Date|$)",
            # Sometimes just listed after course info
            r"(?:Subject|Topic|Area)[:\s]*([A-Za-z\s]+?)(?:\n|$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                field = matches[0].strip()
                if len(field) > 2:
                    logger.info(f"Found field of study: '{field}'")
                    return field

        return ""

    def _extract_instructional_method(self, text: str) -> str:
        """Extract instructional method from text - IMPROVED"""
        patterns = [
            # "Instructional Method: QAS Self-Study" format
            r"Instructional\s*Method[:\s]*([^\\n]+?)(?:\n|$)",
            # Common methods
            r"(QAS\s*Self-Study|Group\s*Study|Live\s*Webinar|On-Demand|Correspondence)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                method = matches[0].strip()
                logger.info(f"Found instructional method: '{method}'")
                return method

        return ""

    def _extract_nasba_sponsor(self, text: str) -> str:
        """Extract NASBA sponsor number from text - IMPROVED"""
        patterns = [
            # "NASBA #112530" format
            r"NASBA\s*#([0-9]+)",
            r"NASBA[:\s]*([0-9]+)",
            # Generic sponsor patterns
            r"(?:sponsor|NASBA)(?:\s*#|\s*number)[:\s]*([A-Z0-9-]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                nasba = matches[0].strip()
                logger.info(f"Found NASBA sponsor: {nasba}")
                return nasba

        return ""

    def _calculate_confidence_score(self, data: Dict) -> float:
        """Calculate confidence score based on extracted data quality"""
        score = 0.0

        # Weight different fields by importance
        if data.get("cpe_credits", 0) > 0:
            score += 0.3  # Most important
        if data.get("course_title", ""):
            score += 0.25
        if data.get("provider", ""):
            score += 0.2
        if data.get("completion_date", ""):
            score += 0.25

        return min(score, 1.0)

    def _create_empty_parse_result(self) -> Dict:
        """Create empty parsing result as fallback"""
        return {
            "cpe_credits": 0.0,
            "ethics_credits": 0.0,
            "course_title": "",
            "provider": "",
            "completion_date": "",
            "certificate_number": "",
            "course_code": "",
            "field_of_study": "",
            "instructional_method": "",
            "nasba_sponsor": "",
            "confidence_score": 0.0,
        }

    # Enhanced CE Broker field extraction methods
    def enhance_parsed_data(self, raw_text: str, parsed_data: Dict) -> Dict:
        """Enhance parsed data with CE Broker specific fields"""
        logger.info("Enhancing parsed data with CE Broker fields...")

        # Start with the basic parsed data
        enhanced_data = parsed_data.copy()

        # Extract additional CE Broker fields
        ce_broker_fields = self.extract_ce_broker_fields(raw_text, parsed_data)

        # Merge the fields
        enhanced_data.update(ce_broker_fields)

        return enhanced_data

    def extract_ce_broker_fields(self, raw_text: str, parsed_data: Dict) -> Dict:
        """Extract CE Broker specific fields from certificate text"""

        # Get basic fields
        course_title = parsed_data.get("course_title", "")
        field_of_study = parsed_data.get("field_of_study", "")
        instructional_method = parsed_data.get("instructional_method", "")

        # Determine course type (anytime vs live)
        course_type = self._determine_course_type(instructional_method, raw_text)

        # Determine delivery method
        delivery_method = self._determine_delivery_method(
            instructional_method, raw_text
        )

        # Map field of study to subject areas
        subject_areas = self._map_subject_areas(field_of_study)

        # Determine CE category
        ce_category = self._determine_ce_category(subject_areas, course_title)

        # Check if CE Broker ready
        ce_broker_ready = self._check_ce_broker_readiness(
            parsed_data,
            {
                "course_type": course_type,
                "delivery_method": delivery_method,
                "subject_areas": subject_areas,
            },
        )

        return {
            "course_type": course_type,
            "delivery_method": delivery_method,
            "instructional_method": instructional_method,
            "subject_areas": subject_areas,
            "field_of_study": field_of_study,
            "ce_category": ce_category,
            "ce_broker_ready": ce_broker_ready,
        }

    def _determine_course_type(self, instructional_method: str, raw_text: str) -> str:
        """Determine if course is 'live' or 'anytime' for CE Broker"""
        if not instructional_method:
            return "anytime"  # Default

        method_lower = instructional_method.lower()
        if "live" in method_lower or "webinar" in method_lower:
            return "live"
        else:
            return "anytime"

    def _determine_delivery_method(
        self, instructional_method: str, raw_text: str
    ) -> str:
        """Determine delivery method for CE Broker"""
        if not instructional_method:
            return "Computer-Based Training"  # Default

        method_lower = instructional_method.lower()
        if "self-study" in method_lower or "computer" in method_lower:
            return "Computer-Based Training"
        elif "webinar" in method_lower or "broadcast" in method_lower:
            return "Prerecorded Broadcast"
        elif "correspondence" in method_lower:
            return "Correspondence"
        else:
            return "Computer-Based Training"

    def _map_subject_areas(self, field_of_study: str) -> List[str]:
        """Map field of study to CE Broker subject areas"""
        if not field_of_study:
            return []

        field_lower = field_of_study.lower()

        # Map common fields to CE Broker categories
        mapping = {
            "taxes": ["Taxes"],
            "tax": ["Taxes"],
            "taxation": ["Taxes"],
            "accounting": ["Accounting"],
            "auditing": ["Auditing"],
            "audit": ["Auditing"],
            "finance": ["Finance"],
            "financial": ["Finance"],
            "ethics": ["Administrative practices"],
            "business law": ["Business law"],
            "law": ["Business law"],
        }

        for key, subjects in mapping.items():
            if key in field_lower:
                return subjects

        # Default to Finance if no match
        return ["Finance"]

    def _determine_ce_category(
        self, subject_areas: List[str], course_title: str
    ) -> str:
        """Determine CE category for CE Broker"""
        if "Administrative practices" in subject_areas:
            title_lower = course_title.lower() if course_title else ""
            if "ethics" in title_lower or "professional responsibility" in title_lower:
                return "Professional Ethics CPE"

        return "General CPE"

    def _check_ce_broker_readiness(self, parsed_data: Dict, ce_fields: Dict) -> bool:
        """Check if record has all required fields for CE Broker export"""
        required_fields = [
            parsed_data.get("course_title"),
            parsed_data.get("provider"),
            parsed_data.get("completion_date"),
            ce_fields.get("course_type"),
            ce_fields.get("delivery_method"),
            ce_fields.get("subject_areas"),
        ]

        # Check if all required fields are present and not empty
        ready = all(field for field in required_fields if field is not None)

        return ready
