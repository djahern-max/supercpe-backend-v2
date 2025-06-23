# app/services/vision_service.py - Complete Enhanced Vision Service

import re
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class SubjectAreaDetector:
    """Automatically detect CE Broker subject areas from course content"""

    def __init__(self):
        # CE Broker subject areas with associated keywords
        self.subject_keywords = {
            "Taxes": [
                "tax",
                "taxation",
                "income tax",
                "corporate tax",
                "sales tax",
                "property tax",
                "tax preparation",
                "tax planning",
                "irs",
                "1040",
                "deductions",
                "credits",
                "withholding",
                "estimated tax",
                "tax law",
                "tax code",
                "tax compliance",
                "tax return",
                "taxable income",
            ],
            "Finance": [
                "finance",
                "financial",
                "investment",
                "portfolio",
                "banking",
                "credit",
                "debt",
                "loan",
                "mortgage",
                "interest",
                "cash flow",
                "financial planning",
                "capital",
                "equity",
                "bonds",
                "securities",
                "financial analysis",
                "budgeting",
                "financial management",
                "financial statements",
                "valuation",
                "cost of capital",
            ],
            "Public accounting": [
                "public accounting",
                "cpa firm",
                "audit",
                "auditing",
                "attestation",
                "compilation",
                "review",
                "financial statement audit",
                "gaas",
                "pcaob",
                "independence",
                "professional standards",
                "peer review",
            ],
            "Governmental accounting": [
                "government",
                "governmental",
                "municipal",
                "public sector",
                "gasb",
                "fund accounting",
                "governmental funds",
                "proprietary funds",
                "fiduciary funds",
                "budget",
                "appropriation",
                "grant accounting",
            ],
            "Public auditing": [
                "government audit",
                "compliance audit",
                "single audit",
                "yellow book",
                "gagas",
                "federal audit",
                "state audit",
                "performance audit",
            ],
            "Business law": [
                "business law",
                "corporate law",
                "contract",
                "legal",
                "litigation",
                "compliance",
                "regulations",
                "securities law",
                "employment law",
                "intellectual property",
                "bankruptcy",
                "mergers",
                "acquisitions",
            ],
            "Business management and organization": [
                "management",
                "leadership",
                "organization",
                "strategy",
                "operations",
                "human resources",
                "hr",
                "organizational behavior",
                "project management",
                "process improvement",
                "efficiency",
                "productivity",
                "team building",
                "business strategy",
                "organizational development",
                "change management",
            ],
            "Economics": [
                "economics",
                "economic",
                "economy",
                "macroeconomics",
                "microeconomics",
                "inflation",
                "recession",
                "gdp",
                "monetary policy",
                "fiscal policy",
                "market analysis",
                "economic indicators",
                "supply and demand",
                "economic theory",
                "market economy",
            ],
            "Communications": [
                "communication",
                "communications",
                "presentation",
                "writing",
                "speaking",
                "public speaking",
                "business communication",
                "interpersonal",
                "negotiation",
                "conflict resolution",
                "customer service",
                "business writing",
                "effective communication",
            ],
            "Computer science": [
                "computer",
                "technology",
                "software",
                "hardware",
                "programming",
                "database",
                "cybersecurity",
                "it",
                "information technology",
                "systems",
                "network",
                "cloud computing",
                "data analytics",
                "artificial intelligence",
                "automation",
                "digital transformation",
            ],
            "Personal development": [
                "personal development",
                "professional development",
                "career",
                "skills development",
                "training",
                "education",
                "learning",
                "self improvement",
                "professional growth",
                "time management",
                "work-life balance",
                "stress management",
            ],
            "Statistics": [
                "statistics",
                "statistical",
                "data analysis",
                "regression",
                "correlation",
                "probability",
                "sampling",
                "statistical methods",
                "descriptive statistics",
                "inferential statistics",
                "hypothesis testing",
            ],
            "Mathematics": [
                "mathematics",
                "mathematical",
                "calculus",
                "algebra",
                "quantitative",
                "mathematical modeling",
                "financial mathematics",
                "actuarial",
            ],
            "Marketing": [
                "marketing",
                "advertising",
                "promotion",
                "brand",
                "customer acquisition",
                "market research",
                "digital marketing",
                "social media marketing",
                "sales",
                "customer relationship",
                "market analysis",
            ],
            "Personnel and human resources": [
                "human resources",
                "hr",
                "personnel",
                "employee",
                "hiring",
                "recruitment",
                "compensation",
                "benefits",
                "performance management",
                "employee relations",
                "workplace",
                "labor relations",
                "payroll",
            ],
            "Management advisory services": [
                "advisory",
                "consulting",
                "business advisory",
                "management consulting",
                "advisory services",
                "business consulting",
                "strategic advisory",
                "financial advisory",
                "operational advisory",
            ],
            "Administrative practices": [
                "administrative",
                "administration",
                "office management",
                "procedures",
                "policies",
                "workflow",
                "business processes",
                "documentation",
                "record keeping",
                "filing systems",
                "office procedures",
                "ethics",
                "professional responsibility",
                "conduct",
                "integrity",
            ],
            "Social environment of business": [
                "social responsibility",
                "corporate social responsibility",
                "csr",
                "sustainability",
                "environmental",
                "diversity",
                "inclusion",
                "corporate citizenship",
                "stakeholder",
                "community relations",
                "social impact",
                "environmental impact",
            ],
            "Production": [
                "production",
                "manufacturing",
                "operations",
                "supply chain",
                "inventory",
                "quality control",
                "lean manufacturing",
                "six sigma",
                "process improvement",
                "operational efficiency",
                "logistics",
            ],
            "Specialized knowledge and its application": [
                "specialized",
                "industry specific",
                "niche",
                "specialized knowledge",
                "expert",
                "advanced",
                "technical expertise",
                "domain knowledge",
            ],
        }

    def detect_subject_areas(
        self,
        course_title: str,
        provider: str = "",
        raw_text: str = "",
        field_of_study: str = "",
    ) -> List[str]:
        """Detect subject areas based on course content"""
        # Combine all text for analysis
        combined_text = " ".join(
            [course_title or "", provider or "", raw_text or "", field_of_study or ""]
        ).lower()

        detected_areas = []
        scores = {}

        # Score each subject area based on keyword matches
        for subject, keywords in self.subject_keywords.items():
            score = 0
            matched_keywords = []

            for keyword in keywords:
                # Count occurrences of each keyword
                count = len(
                    re.findall(
                        r"\b" + re.escape(keyword.lower()) + r"\b", combined_text
                    )
                )
                if count > 0:
                    score += count
                    matched_keywords.append(keyword)

            if score > 0:
                scores[subject] = {"score": score, "keywords": matched_keywords}

        # Select subject areas with significant scores
        if scores:
            # Sort by score, take top matches
            sorted_subjects = sorted(
                scores.items(), key=lambda x: x[1]["score"], reverse=True
            )

            # Take subjects with score >= 1 (at least one keyword match)
            for subject, data in sorted_subjects:
                if data["score"] >= 1:
                    detected_areas.append(subject)

                # Limit to top 3 most relevant areas
                if len(detected_areas) >= 3:
                    break

        # Apply business rules and fallbacks
        detected_areas = self._apply_business_rules(
            detected_areas, course_title, combined_text
        )

        return detected_areas

    def _apply_business_rules(
        self, detected_areas: List[str], course_title: str, combined_text: str
    ) -> List[str]:
        """Apply business rules to refine subject area detection"""

        # If no areas detected, apply fallback logic
        if not detected_areas:
            # Check for common patterns
            title_lower = course_title.lower() if course_title else ""

            if any(word in title_lower for word in ["tax", "taxation"]):
                detected_areas.append("Taxes")
            elif any(
                word in title_lower
                for word in [
                    "finance",
                    "financial",
                    "money",
                    "investment",
                    "debt",
                    "interest",
                ]
            ):
                detected_areas.append("Finance")
            elif any(word in title_lower for word in ["business", "management"]):
                detected_areas.append("Business management and organization")
            elif any(word in title_lower for word in ["economic", "economy"]):
                detected_areas.append("Economics")
            elif any(
                word in title_lower for word in ["communication", "writing", "speaking"]
            ):
                detected_areas.append("Communications")
            elif any(
                word in title_lower for word in ["computer", "technology", "software"]
            ):
                detected_areas.append("Computer science")
            elif any(word in title_lower for word in ["ethics", "ethical"]):
                detected_areas.append("Administrative practices")
            else:
                # Default fallback for accounting courses
                detected_areas.append("Specialized knowledge and its application")

        # Remove duplicates while preserving order
        seen = set()
        filtered_areas = []
        for area in detected_areas:
            if area not in seen:
                seen.add(area)
                filtered_areas.append(area)

        return filtered_areas


class CEBrokerMappings:
    """Helper class for CE Broker field mappings and detection"""

    @staticmethod
    def detect_subject_areas(
        course_title: str, field_of_study: str = "", raw_text: str = ""
    ) -> List[str]:
        """Detect subject areas using the SubjectAreaDetector"""
        detector = SubjectAreaDetector()
        return detector.detect_subject_areas(course_title, "", raw_text, field_of_study)

    @staticmethod
    def detect_course_type(raw_text: str, instructional_method: str = "") -> str:
        """Detect if course is Live or Anytime"""
        if not raw_text and not instructional_method:
            return "anytime"  # Default assumption

        combined_text = f"{raw_text} {instructional_method}".lower()

        # Live indicators
        live_indicators = [
            "live",
            "webinar",
            "classroom",
            "instructor-led",
            "seminar",
            "workshop",
            "conference",
            "presentation",
            "lecture",
            "group study",
        ]

        # Anytime indicators
        anytime_indicators = [
            "self-study",
            "online",
            "computer-based",
            "self-paced",
            "on-demand",
            "qas",
            "individual study",
            "correspondence",
        ]

        live_score = sum(
            1 for indicator in live_indicators if indicator in combined_text
        )
        anytime_score = sum(
            1 for indicator in anytime_indicators if indicator in combined_text
        )

        if live_score > anytime_score:
            return "live"
        else:
            return "anytime"  # Default to anytime

    @staticmethod
    def detect_delivery_method(
        course_type: str, instructional_method: str = "", raw_text: str = ""
    ) -> str:
        """Detect delivery method based on course type and content"""
        combined_text = f"{instructional_method} {raw_text}".lower()

        # Computer-based training indicators
        if any(
            indicator in combined_text
            for indicator in [
                "computer",
                "online",
                "internet",
                "web-based",
                "digital",
                "software",
                "app",
                "platform",
            ]
        ):
            return "Computer-Based Training (ie: online courses)"

        # Correspondence indicators
        elif any(
            indicator in combined_text
            for indicator in [
                "correspondence",
                "mail",
                "written",
                "reading",
                "book",
                "manual",
                "text",
            ]
        ):
            return "Correspondence"

        # Prerecorded broadcast indicators
        elif any(
            indicator in combined_text
            for indicator in [
                "recorded",
                "video",
                "broadcast",
                "replay",
                "playback",
                "dvd",
                "cd-rom",
            ]
        ):
            return "Prerecorded Broadcast"

        # Default based on course type
        else:
            return "Computer-Based Training (ie: online courses)"  # Most common default


class EnhancedVisionService:
    """Enhanced vision service with REAL Google Vision API integration"""

    def __init__(self):
        self.confidence_threshold = 0.7
        self.subject_detector = SubjectAreaDetector()

        # Initialize Google Vision client
        try:
            from google.cloud import vision

            self.vision_client = vision.ImageAnnotatorClient()
            logger.info("Google Vision API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Vision API: {e}")
            self.vision_client = None

    def extract_text_from_file(self, file_content: bytes, content_type: str) -> str:
        """Extract text from uploaded file using Google Vision API"""

        if not self.vision_client:
            logger.error("Google Vision API client not available")
            return ""

        try:
            from google.cloud import vision

            # Create image object
            image = vision.Image(content=file_content)

            # Perform text detection
            response = self.vision_client.text_detection(image=image)

            # Extract text
            texts = response.text_annotations

            if texts:
                extracted_text = texts[0].description
                logger.info(
                    f"Successfully extracted {len(extracted_text)} characters via Google Vision"
                )
                return extracted_text
            else:
                logger.warning("No text found in image via Google Vision")
                return ""

        except Exception as e:
            logger.error(f"Google Vision text extraction failed: {e}")
            return ""

    def parse_certificate_data(self, raw_text: str, filename: str) -> Dict:
        """Parse structured data from raw text using AI"""

        if not raw_text:
            logger.warning("No raw text available for parsing")
            return self._create_empty_parse_result()

        try:
            logger.info("Starting intelligent text parsing...")

            # Extract CPE credits using pattern matching and AI
            cpe_credits = self._extract_cpe_credits(raw_text)
            ethics_credits = self._extract_ethics_credits(raw_text)
            course_title = self._extract_course_title(raw_text)
            provider = self._extract_provider(raw_text)
            completion_date = self._extract_completion_date(raw_text)
            certificate_number = self._extract_certificate_number(raw_text)

            # Calculate confidence score based on extracted fields
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
                "confidence_score": confidence_score,
            }

            logger.info(f"Parsing completed with confidence: {confidence_score}")
            logger.info(
                f"Extracted: CPE={cpe_credits}, Title='{course_title[:50] if course_title else 'None'}...', Provider='{provider}'"
            )

            return result

        except Exception as e:
            logger.error(f"Intelligent parsing failed: {e}")
            return self._create_empty_parse_result()

    def _extract_cpe_credits(self, text: str) -> float:
        """Extract CPE credit hours from text"""
        import re

        # Common patterns for CPE credits
        patterns = [
            r"(\d+(?:\.\d+)?)\s*(?:cpe|CPE|credit|hours?|hrs?)",
            r"(?:cpe|CPE|credit|hours?|hrs?)[:\s]*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*(?:continuing|professional|education)",
            r"(\d+(?:\.\d+)?)\s*(?:hour|hr)s?\s*(?:cpe|CPE)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    credits = float(matches[0])
                    if 0.5 <= credits <= 50:  # Reasonable range
                        logger.info(f"Found CPE credits: {credits}")
                        return credits
                except ValueError:
                    continue

        logger.warning("No CPE credits found in text")
        return 0.0

    def _extract_ethics_credits(self, text: str) -> float:
        """Extract ethics credit hours from text"""
        import re

        if re.search(r"ethics?|professional\s+responsibility", text, re.IGNORECASE):
            # Look for ethics-specific credit amounts
            patterns = [
                r"ethics?[:\s]*(\d+(?:\.\d+)?)",
                r"(\d+(?:\.\d+)?)\s*ethics?",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    try:
                        return float(matches[0])
                    except ValueError:
                        continue

        return 0.0

    def _extract_course_title(self, text: str) -> str:
        """Extract course title from text"""
        import re

        # Look for title patterns
        lines = text.split("\n")

        # Common title indicators
        title_patterns = [
            r"(?:course|title|program|seminar|workshop)[:\s]*(.+?)(?:\n|$)",
            r"(?:certification|certificate)\s+(?:in|of|for)[:\s]*(.+?)(?:\n|$)",
        ]

        for pattern in title_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                title = matches[0].strip()
                if len(title) > 5:  # Reasonable title length
                    logger.info(f"Found course title: {title}")
                    return title

        # Fallback: use first substantial line
        for line in lines:
            line = line.strip()
            if len(line) > 10 and not re.match(r"^\d+", line):
                logger.info(f"Using fallback title: {line}")
                return line

        logger.warning("No course title found")
        return ""

    def _extract_provider(self, text: str) -> str:
        """Extract provider/organization from text"""
        import re

        # Common provider patterns
        patterns = [
            r"(?:provided|presented|offered|sponsored)\s+by[:\s]*(.+?)(?:\n|$)",
            r"(?:provider|sponsor|organization)[:\s]*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                provider = matches[0].strip()
                if len(provider) > 2:
                    logger.info(f"Found provider: {provider}")
                    return provider

        logger.warning("No provider found")
        return ""

    def _extract_completion_date(self, text: str) -> str:
        """Extract completion date from text"""
        import re
        from datetime import datetime

        # Date patterns
        date_patterns = [
            r"(?:completed|completion|date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(?:completed|completion|date)[:\s]*(\w+ \d{1,2}, \d{4})",
            r"(\w+ \d{1,2}, \d{4})",
        ]

        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                date_str = matches[0].strip()
                try:
                    # Try to parse and normalize the date
                    if "/" in date_str or "-" in date_str:
                        parsed_date = datetime.strptime(
                            date_str.replace("-", "/"), "%m/%d/%Y"
                        )
                    else:
                        parsed_date = datetime.strptime(date_str, "%B %d, %Y")

                    formatted_date = parsed_date.strftime("%Y-%m-%d")
                    logger.info(f"Found completion date: {formatted_date}")
                    return formatted_date
                except ValueError:
                    continue

        logger.warning("No completion date found")
        return ""

    def _extract_certificate_number(self, text: str) -> str:
        """Extract certificate number from text"""
        import re

        patterns = [
            r"(?:certificate|cert|confirmation)(?:\s+#|\s+number|#)[:\s]*([A-Z0-9-]+)",
            r"#([A-Z0-9-]{4,})",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                cert_num = matches[0].strip()
                logger.info(f"Found certificate number: {cert_num}")
                return cert_num

        return ""

    def _calculate_confidence_score(self, data: Dict) -> float:
        """Calculate confidence score based on extracted data quality"""
        score = 0.0

        if data.get("cpe_credits", 0) > 0:
            score += 0.3
        if data.get("course_title", ""):
            score += 0.3
        if data.get("provider", ""):
            score += 0.2
        if data.get("completion_date", ""):
            score += 0.2

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
            "confidence_score": 0.0,
        }

    # ADD MISSING METHODS THAT ARE REFERENCED BUT NOT DEFINED:

    def extract_instructional_method(self, raw_text: str) -> Optional[str]:
        """Extract instructional method from text"""
        if not raw_text:
            return None

        text_lower = raw_text.lower()

        if "qas" in text_lower or "self-study" in text_lower:
            return "QAS Self-Study"
        elif "group" in text_lower:
            return "Group Study"
        elif "correspondence" in text_lower:
            return "Correspondence"
        else:
            return None

    def extract_nasba_sponsor(self, raw_text: str) -> Optional[str]:
        """Extract NASBA sponsor number from text"""
        import re

        patterns = [
            r"nasba[:\s]*([A-Z0-9-]+)",
            r"sponsor[:\s]*([A-Z0-9-]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, raw_text, re.IGNORECASE)
            if matches:
                return matches[0].strip()

        return None

    def extract_course_code(self, raw_text: str) -> Optional[str]:
        """Extract course code from text"""
        import re

        patterns = [
            r"course[:\s]*code[:\s]*([A-Z0-9-]+)",
            r"code[:\s]*([A-Z0-9-]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, raw_text, re.IGNORECASE)
            if matches:
                return matches[0].strip()

        return None

    def extract_program_level(self, raw_text: str) -> Optional[str]:
        """Extract program level from text"""
        text_lower = raw_text.lower()

        if "advanced" in text_lower:
            return "Advanced"
        elif "intermediate" in text_lower:
            return "Intermediate"
        elif "basic" in text_lower or "beginner" in text_lower:
            return "Basic"
        else:
            return None

    def determine_ce_category(self, subject_areas: List[str], course_title: str) -> str:
        """Determine CE category based on subject areas and title"""
        if not subject_areas:
            return "General CPE"

        # Check for ethics indicators
        if "Administrative practices" in subject_areas:
            title_lower = course_title.lower() if course_title else ""
            if "ethics" in title_lower or "professional responsibility" in title_lower:
                return "Professional Ethics CPE"

        # Default to General CPE
        return "General CPE"

    def extract_ce_broker_fields(self, raw_text: str, parsed_data: Dict) -> Dict:
        """Extract CE Broker specific fields from certificate text - IMPROVED VERSION"""

        logger.info("Starting CE Broker field extraction...")

        try:
            # Get basic extracted data
            course_title = parsed_data.get("course_title", "") or ""
            field_of_study = parsed_data.get("field_of_study", "") or ""

            logger.info(f"Course title: '{course_title}'")
            logger.info(f"Field of study: '{field_of_study}'")
            logger.info(f"Raw text available: {bool(raw_text)}")

            # Extract instructional method first
            instructional_method = self.extract_instructional_method(raw_text)
            logger.info(f"Extracted instructional_method: '{instructional_method}'")

            # Auto-detect CE Broker fields with improved logging
            subject_areas = self.subject_detector.detect_subject_areas(
                course_title, parsed_data.get("provider", ""), raw_text, field_of_study
            )
            logger.info(f"Detected subject_areas: {subject_areas}")

            # IMPROVED: Better course type detection with fallbacks
            course_type = self._detect_course_type_with_fallbacks(
                raw_text, instructional_method, course_title
            )
            logger.info(f"Detected course_type: '{course_type}'")

            # IMPROVED: Better delivery method detection
            delivery_method = self._detect_delivery_method_with_fallbacks(
                course_type, instructional_method, raw_text, course_title
            )
            logger.info(f"Detected delivery_method: '{delivery_method}'")

            # Extract additional fields
            nasba_sponsor = self.extract_nasba_sponsor(raw_text)
            course_code = self.extract_course_code(raw_text)
            program_level = self.extract_program_level(raw_text)

            logger.info(
                f"Additional fields - NASBA: {nasba_sponsor}, Code: {course_code}, Level: {program_level}"
            )

            # Ensure we have minimum required fields
            if not course_type:
                course_type = "anytime"  # Safe default
                logger.warning("No course_type detected, using default: 'anytime'")

            if not delivery_method:
                delivery_method = (
                    "Computer-Based Training (ie: online courses)"  # Safe default
                )
                logger.warning("No delivery_method detected, using default")

            if not subject_areas or len(subject_areas) == 0:
                subject_areas = [
                    "Specialized knowledge and its application"
                ]  # Safe default
                logger.warning("No subject_areas detected, using default")

            result = {
                "course_type": course_type,
                "delivery_method": delivery_method,
                "instructional_method": instructional_method,
                "subject_areas": subject_areas,
                "nasba_sponsor_number": nasba_sponsor,
                "course_code": course_code,
                "program_level": program_level,
                "ce_category": self.determine_ce_category(subject_areas, course_title),
                "ce_broker_ready": self.check_ce_broker_readiness(
                    parsed_data,
                    {
                        "course_type": course_type,
                        "delivery_method": delivery_method,
                        "subject_areas": subject_areas,
                    },
                ),
            }

            logger.info(f"Final CE Broker fields: {result}")
            return result

        except Exception as e:
            logger.error(f"Error in CE Broker field extraction: {str(e)}")
            logger.exception("Full traceback:")

            # Return safe defaults
            return {
                "course_type": "anytime",
                "delivery_method": "Computer-Based Training (ie: online courses)",
                "instructional_method": None,
                "subject_areas": ["Specialized knowledge and its application"],
                "nasba_sponsor_number": None,
                "course_code": None,
                "program_level": None,
                "ce_category": "General CPE",
                "ce_broker_ready": False,
            }

    def _detect_course_type_with_fallbacks(
        self, raw_text: str, instructional_method: str, course_title: str
    ) -> str:
        """Improved course type detection with multiple fallback strategies"""

        if not raw_text and not instructional_method and not course_title:
            return "anytime"  # Default assumption

        combined_text = f"{raw_text} {instructional_method} {course_title}".lower()

        # Live indicators (more comprehensive)
        live_indicators = [
            "live",
            "webinar",
            "classroom",
            "instructor-led",
            "seminar",
            "workshop",
            "conference",
            "presentation",
            "lecture",
            "group study",
            "in-person",
            "face-to-face",
            "interactive",
            "real-time",
            "scheduled",
            "session",
        ]

        # Anytime indicators (more comprehensive)
        anytime_indicators = [
            "self-study",
            "online",
            "computer-based",
            "self-paced",
            "on-demand",
            "qas",
            "individual study",
            "correspondence",
            "digital",
            "e-learning",
            "video",
            "recorded",
            "tutorial",
            "course materials",
            "study guide",
        ]

        live_score = sum(
            1 for indicator in live_indicators if indicator in combined_text
        )
        anytime_score = sum(
            1 for indicator in anytime_indicators if indicator in combined_text
        )

        logger.info(
            f"Course type scoring - Live: {live_score}, Anytime: {anytime_score}"
        )

        if live_score > anytime_score:
            return "live"
        else:
            return "anytime"  # Default to anytime

    def _detect_delivery_method_with_fallbacks(
        self,
        course_type: str,
        instructional_method: str,
        raw_text: str,
        course_title: str,
    ) -> str:
        """Improved delivery method detection with better pattern matching"""

        combined_text = f"{instructional_method} {raw_text} {course_title}".lower()

        # Computer-based training indicators (expanded)
        if any(
            indicator in combined_text
            for indicator in [
                "computer",
                "online",
                "internet",
                "web-based",
                "digital",
                "software",
                "app",
                "platform",
                "e-learning",
                "virtual",
                "portal",
                "website",
            ]
        ):
            return "Computer-Based Training (ie: online courses)"

        # Correspondence indicators (expanded)
        elif any(
            indicator in combined_text
            for indicator in [
                "correspondence",
                "mail",
                "written",
                "reading",
                "book",
                "manual",
                "text",
                "study guide",
                "materials",
                "self-study",
                "individual",
            ]
        ):
            return "Correspondence"

        # Prerecorded broadcast indicators (expanded)
        elif any(
            indicator in combined_text
            for indicator in [
                "recorded",
                "video",
                "broadcast",
                "replay",
                "playback",
                "dvd",
                "cd-rom",
                "streaming",
                "media",
                "recording",
            ]
        ):
            return "Prerecorded Broadcast"

        # Default based on course type
        else:
            return "Computer-Based Training (ie: online courses)"  # Most common default

    def check_ce_broker_readiness(
        self, parsed_data: Dict, ce_broker_data: Dict
    ) -> bool:
        """Check if record has all required fields for CE Broker export - IMPROVED"""

        required_checks = [
            ("course_title", parsed_data.get("course_title")),
            ("provider", parsed_data.get("provider")),
            ("completion_date", parsed_data.get("completion_date")),
            ("cpe_credits", parsed_data.get("cpe_credits")),
            ("course_type", ce_broker_data.get("course_type")),
            ("delivery_method", ce_broker_data.get("delivery_method")),
            ("subject_areas", ce_broker_data.get("subject_areas")),
        ]

        missing_fields = []
        for field_name, field_value in required_checks:
            if field_value is None or field_value == "" or field_value == []:
                missing_fields.append(field_name)

        is_ready = len(missing_fields) == 0

        if missing_fields:
            logger.warning(f"CE Broker not ready. Missing fields: {missing_fields}")
        else:
            logger.info("CE Broker ready - all required fields present")

        return is_ready

    def enhance_parsed_data(self, raw_text: str, basic_parsed_data: Dict) -> Dict:
        """Main method to enhance basic parsed data with CE Broker fields - IMPROVED"""

        logger.info("Starting data enhancement...")

        # Extract CE Broker specific fields
        ce_broker_fields = self.extract_ce_broker_fields(raw_text, basic_parsed_data)

        # Combine with basic data
        enhanced_data = {**basic_parsed_data, **ce_broker_fields}

        # Add metadata
        enhanced_data["parsing_enhanced"] = True
        enhanced_data["enhancement_timestamp"] = datetime.now().isoformat()

        logger.info(
            f"Enhanced parsing completed. CE Broker ready: {ce_broker_fields['ce_broker_ready']}"
        )

        return enhanced_data


# Create CPE record with enhanced CE Broker fields
def create_enhanced_cpe_record_from_parsing(
    parsing_result: Dict,
    file,
    license_number: str,
    current_user,
    upload_result: Dict,
    storage_tier: str = "free",
):
    """Create CPE record with enhanced CE Broker fields"""

    from app.models.cpe_record import CPERecord
    from datetime import datetime

    # Initialize enhanced vision service
    vision_service = EnhancedVisionService()

    # Get basic parsed data
    parsed_data = parsing_result.get("parsed_data", {})
    raw_text = parsing_result.get("raw_text", "")

    # Enhance with CE Broker fields
    enhanced_data = vision_service.enhance_parsed_data(raw_text, parsed_data)

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
        # CE Broker fields
        course_type=enhanced_data.get("course_type"),
        delivery_method=enhanced_data.get("delivery_method"),
        instructional_method=enhanced_data.get("instructional_method"),
        subject_areas=enhanced_data.get("subject_areas"),
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

    return cpe_record
