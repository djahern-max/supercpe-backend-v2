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
    """Enhanced vision service with CE Broker field extraction"""

    def __init__(self):
        self.confidence_threshold = 0.7
        self.subject_detector = SubjectAreaDetector()

    def extract_ce_broker_fields(self, raw_text: str, parsed_data: Dict) -> Dict:
        """Extract CE Broker specific fields from certificate text"""

        # Get basic extracted data
        course_title = parsed_data.get("course_title", "")
        field_of_study = parsed_data.get("field_of_study", "")
        instructional_method = self.extract_instructional_method(raw_text)

        # Auto-detect CE Broker fields
        subject_areas = self.subject_detector.detect_subject_areas(
            course_title, parsed_data.get("provider", ""), raw_text, field_of_study
        )

        course_type = CEBrokerMappings.detect_course_type(
            raw_text, instructional_method
        )

        delivery_method = CEBrokerMappings.detect_delivery_method(
            course_type, instructional_method, raw_text
        )

        # Extract additional fields
        nasba_sponsor = self.extract_nasba_sponsor(raw_text)
        course_code = self.extract_course_code(raw_text)
        program_level = self.extract_program_level(raw_text)

        return {
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

    def extract_instructional_method(self, raw_text: str) -> Optional[str]:
        """Extract instructional method from certificate text"""
        if not raw_text:
            return None

        # Common patterns for instructional methods
        patterns = [
            r"Instructional Method:\s*([^\n]+)",
            r"Method:\s*([^\n]+)",
            r"Delivery:\s*([^\n]+)",
            r"Format:\s*([^\n]+)",
            r"(QAS Self-Study)",
            r"(Group Study)",
            r"(Individual Study)",
            r"(Self-Study)",
            r"(Online)",
            r"(Webinar)",
            r"(Classroom)",
            r"(Seminar)",
        ]

        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def extract_nasba_sponsor(self, raw_text: str) -> Optional[str]:
        """Extract NASBA sponsor number from certificate"""
        if not raw_text:
            return None

        # Patterns for NASBA sponsor numbers
        patterns = [
            r"NASBA\s*#?\s*(\d+)",
            r"Sponsor\s*#?\s*(\d+)",
            r"NASBA\s+Sponsor\s*#?\s*(\d+)",
            r"Registry\s*#?\s*(\d+)",
            r"#(\d{6})",  # 6-digit numbers often NASBA
        ]

        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def extract_course_code(self, raw_text: str) -> Optional[str]:
        """Extract course code from certificate"""
        if not raw_text:
            return None

        patterns = [
            r"Course Code:\s*([^\n]+)",
            r"Code:\s*([A-Z0-9\-_]+)",
            r"Course\s*#:\s*([^\n]+)",
            r"Program Code:\s*([^\n]+)",
            r"([A-Z]\d{3}-\d{4}-\d{2}-[A-Z]+)",  # Pattern like M290-2024-01-SSDL
        ]

        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def extract_program_level(self, raw_text: str) -> Optional[str]:
        """Extract program level (Basic, Intermediate, Advanced)"""
        if not raw_text:
            return None

        patterns = [
            r"Level:\s*(Basic|Intermediate|Advanced)",
            r"Program Level:\s*(Basic|Intermediate|Advanced)",
            r"\b(Basic|Intermediate|Advanced)\s+Level",
        ]

        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()

        return None

    def determine_ce_category(self, subject_areas: List[str], course_title: str) -> str:
        """Determine CE category for CE Broker"""

        # Check for ethics-related content
        ethics_keywords = [
            "ethics",
            "professional responsibility",
            "conduct",
            "integrity",
        ]
        ethics_subjects = ["Administrative practices"]

        course_title_lower = (course_title or "").lower()

        # Check if this is an ethics course
        if any(keyword in course_title_lower for keyword in ethics_keywords) or any(
            subject in subject_areas for subject in ethics_subjects
        ):
            return "Professional Ethics CPE"

        return "General CPE"  # Default

    def check_ce_broker_readiness(
        self, parsed_data: Dict, ce_broker_data: Dict
    ) -> bool:
        """Check if record has all required fields for CE Broker export"""
        required_fields = [
            parsed_data.get("course_title"),
            parsed_data.get("provider"),
            parsed_data.get("completion_date"),
            parsed_data.get("cpe_credits"),
            ce_broker_data.get("course_type"),
            ce_broker_data.get("delivery_method"),
            ce_broker_data.get("subject_areas"),
        ]

        return all(
            field is not None and field != "" and field != []
            for field in required_fields
        )

    def enhance_parsed_data(self, raw_text: str, basic_parsed_data: Dict) -> Dict:
        """Main method to enhance basic parsed data with CE Broker fields"""

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
