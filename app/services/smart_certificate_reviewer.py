# FILE 1: app/services/smart_certificate_reviewer.py (NEW FILE)
"""
Smart Certificate Review Service
Processes raw OCR text and provides intelligent suggestions for CPE data extraction
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date

logger = logging.getLogger(__name__)


class SmartCertificateReviewer:
    """Enhanced certificate processing with multiple candidate extraction"""

    def __init__(self):
        self.common_providers = {
            "AICPA",
            "NASBA",
            "Surgent",
            "Becker",
            "Kaplan",
            "CPE Link",
            "MasterCPE",
            "Illumeo",
            "Thomson Reuters",
            "CCH",
            "BDO",
            "Deloitte",
            "EY",
            "KPMG",
            "PwC",
            "Grant Thornton",
            "RSM",
            "CliftonLarsonAllen",
            "Crowe",
            "Mazars",
            "BKD",
        }

        self.subject_areas = {
            "Accounting",
            "Auditing",
            "Tax",
            "Ethics",
            "Consulting",
            "Financial Reporting",
            "Government",
            "Not-for-Profit",
            "Technology",
            "Forensic",
            "Valuation",
        }

    def process_raw_text(self, raw_text: str, filename: str = "") -> Dict:
        """Main processing function that extracts multiple candidates for each field"""
        if not raw_text or len(raw_text.strip()) < 10:
            return self._empty_result()

        logger.info(f"Smart processing certificate: {filename}")
        logger.info(f"Raw text length: {len(raw_text)} characters")

        # Extract insights with multiple candidates
        insights = self._extract_insights(raw_text)

        # Generate user-friendly suggestions
        suggestions = self._generate_suggestions(insights, filename)

        # Calculate overall confidence
        confidence = self._calculate_overall_confidence(insights)

        # Generate best guess for immediate use
        best_guess = self._generate_best_guess(insights)

        # Identify what needs review
        review_flags = self._identify_review_needs(insights)

        result = {
            # Core data
            "extracted_data": best_guess,
            "confidence_score": confidence,
            # Rich insights for review interface
            "insights": insights,
            "suggestions": suggestions,
            "review_flags": review_flags,
            # Metadata
            "processing_method": "smart_review",
            "raw_text_length": len(raw_text),
            "candidates_found": self._count_candidates(insights),
        }

        logger.info(f"Smart processing complete - confidence: {confidence:.2f}")
        return result

    def _extract_insights(self, text: str) -> Dict:
        """Extract multiple candidates for each field type"""
        return {
            "possible_titles": self._find_possible_titles(text),
            "possible_providers": self._find_possible_providers(text),
            "possible_credits": self._find_possible_credits(text),
            "possible_dates": self._find_possible_dates(text),
            "possible_reference_numbers": self._find_reference_numbers(text),
            "document_type": self._identify_document_type(text),
            "key_phrases": self._extract_key_phrases(text),
        }

    def _find_possible_titles(self, text: str) -> List[Dict]:
        """Find multiple potential course titles with confidence scores"""
        candidates = []

        # Pattern-based extraction
        title_patterns = [
            (r"(?:course title|title|course|subject|program):\s*(.+?)(?:\n|$)", 0.8),
            (r"(?:successfully complet\w+|complet\w+ of)\s+(.+?)(?:\n|$)", 0.7),
            (r"certificate.{0,20}(?:for|of|in)\s+(.+?)(?:\n|$)", 0.6),
            (r'"([^"]{10,100})"', 0.5),
            (r"^([A-Z][a-z].{10,80})$", 0.4),  # Lines that look like titles
        ]

        for pattern, base_confidence in title_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                title = self._clean_title(match.group(1))
                if self._is_valid_title(title):
                    confidence = self._calculate_title_confidence(
                        title, text, base_confidence
                    )
                    candidates.append(
                        {
                            "text": title,
                            "confidence": confidence,
                            "source": "pattern_match",
                            "pattern_used": pattern,
                        }
                    )

        # Sort by confidence and remove duplicates
        candidates = self._deduplicate_candidates(candidates)
        return sorted(candidates, key=lambda x: x["confidence"], reverse=True)[:5]

    def _find_possible_providers(self, text: str) -> List[Dict]:
        """Find multiple potential providers"""
        candidates = []

        # Check against known providers first
        for provider in self.common_providers:
            if provider.lower() in text.lower():
                candidates.append(
                    {"text": provider, "confidence": 0.9, "source": "known_provider"}
                )

        # Pattern-based extraction
        provider_patterns = [
            (r"(?:provider|sponsor|offered by|presenter):\s*(.+?)(?:\n|$)", 0.8),
            (
                r"([A-Z][a-zA-Z\s&,\.]+(?:LLC|Inc|Corporation|Institute|Academy|University|College))",
                0.6,
            ),
            (r"NASBA\s+Sponsor[^\n]*\n([^\n]+)", 0.7),
        ]

        for pattern, base_confidence in provider_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                provider = self._clean_provider(match.group(1))
                if self._is_valid_provider(provider):
                    confidence = self._calculate_provider_confidence(
                        provider, text, base_confidence
                    )
                    candidates.append(
                        {
                            "text": provider,
                            "confidence": confidence,
                            "source": "pattern_match",
                        }
                    )

        candidates = self._deduplicate_candidates(candidates)
        return sorted(candidates, key=lambda x: x["confidence"], reverse=True)[:3]

    def _find_possible_credits(self, text: str) -> List[Dict]:
        """Find all possible credit values (CPE and Ethics)"""
        candidates = []

        credit_patterns = [
            (r"CPE\s+Credits?:\s*(\d+(?:\.\d+)?)", "cpe", 0.9),
            (r"(\d+(?:\.\d+)?)\s+CPE\s+Credits?", "cpe", 0.8),
            (r"(\d+(?:\.\d+)?)\s+(?:hours?|credits?)\s+(?:of\s+)?CPE", "cpe", 0.7),
            (r"Ethics.*?(\d+(?:\.\d+)?)", "ethics", 0.8),
            (r"(\d+(?:\.\d+)?)\s+Ethics", "ethics", 0.9),
            (r"Credits?:\s*(\d+(?:\.\d+)?)", "cpe", 0.5),  # Generic credits
        ]

        for pattern, credit_type, base_confidence in credit_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    credits = float(match.group(1))
                    if 0 < credits <= 50:  # Reasonable range
                        candidates.append(
                            {
                                "value": credits,
                                "type": credit_type,
                                "confidence": base_confidence,
                                "context": match.group(0),
                                "source": "pattern_match",
                            }
                        )
                except ValueError:
                    continue

        return candidates

    def _find_possible_dates(self, text: str) -> List[Dict]:
        """Find all possible completion dates"""
        candidates = []

        date_patterns = [
            r"(?:completion date|completed|date completed):\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(?:on|dated)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        ]

        for pattern in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                date_str = match.group(1)
                parsed_date = self._parse_date(date_str)
                if parsed_date:
                    candidates.append(
                        {
                            "date": parsed_date,
                            "text": date_str,
                            "confidence": self._calculate_date_confidence(parsed_date),
                            "source": "pattern_match",
                        }
                    )

        candidates = self._deduplicate_dates(candidates)
        return sorted(candidates, key=lambda x: x["confidence"], reverse=True)[:3]

    def _generate_suggestions(self, insights: Dict, filename: str) -> List[Dict]:
        """Generate user-friendly suggestions for review"""
        suggestions = []

        # Title suggestions
        if len(insights["possible_titles"]) > 1:
            suggestions.append(
                {
                    "type": "title_selection",
                    "field": "course_title",
                    "message": "Multiple course titles found. Please select the correct one:",
                    "options": [
                        {
                            "value": t["text"],
                            "confidence": t["confidence"],
                            "label": f'"{t["text"]}" ({int(t["confidence"] * 100)}% confidence)',
                        }
                        for t in insights["possible_titles"]
                    ],
                }
            )

        # Provider suggestions
        if len(insights["possible_providers"]) > 1:
            suggestions.append(
                {
                    "type": "provider_selection",
                    "field": "provider",
                    "message": "Multiple providers found. Please select the correct one:",
                    "options": [
                        {
                            "value": p["text"],
                            "confidence": p["confidence"],
                            "label": f'{p["text"]} ({int(p["confidence"] * 100)}% confidence)',
                        }
                        for p in insights["possible_providers"]
                    ],
                }
            )

        # Credit clarification
        cpe_credits = [c for c in insights["possible_credits"] if c["type"] == "cpe"]
        if len(cpe_credits) > 1:
            suggestions.append(
                {
                    "type": "credit_clarification",
                    "field": "cpe_credits",
                    "message": "Multiple CPE credit values found. Please verify:",
                    "options": [
                        {
                            "value": c["value"],
                            "label": f'{c["value"]} credits (from: "{c["context"]}")',
                        }
                        for c in cpe_credits
                    ],
                }
            )

        return suggestions

    def _generate_best_guess(self, insights: Dict) -> Dict:
        """Generate best guess data for immediate use"""
        return {
            "course_title": (
                insights["possible_titles"][0]["text"]
                if insights["possible_titles"]
                else None
            ),
            "provider": (
                insights["possible_providers"][0]["text"]
                if insights["possible_providers"]
                else None
            ),
            "cpe_credits": self._get_best_credit_value(
                insights["possible_credits"], "cpe"
            ),
            "ethics_credits": self._get_best_credit_value(
                insights["possible_credits"], "ethics"
            ),
            "completion_date": (
                insights["possible_dates"][0]["date"]
                if insights["possible_dates"]
                else None
            ),
            "certificate_number": (
                insights["possible_reference_numbers"][0]["text"]
                if insights["possible_reference_numbers"]
                else None
            ),
        }

    def _identify_review_needs(self, insights: Dict) -> List[Dict]:
        """Identify what fields need human review"""
        flags = []

        if not insights["possible_titles"]:
            flags.append(
                {
                    "field": "course_title",
                    "severity": "high",
                    "message": "No course title found",
                    "suggestion": "Look for the main heading or course name in the certificate",
                }
            )

        if not insights["possible_providers"]:
            flags.append(
                {
                    "field": "provider",
                    "severity": "medium",
                    "message": "No provider identified",
                    "suggestion": 'Look for company logos, "Sponsored by", or "Offered by" text',
                }
            )

        cpe_credits = [c for c in insights["possible_credits"] if c["type"] == "cpe"]
        if not cpe_credits:
            flags.append(
                {
                    "field": "cpe_credits",
                    "severity": "high",
                    "message": "No CPE credits found",
                    "suggestion": 'Look for numbers near "CPE", "Credits", or "Hours"',
                }
            )

        return flags

    # Utility methods
    def _clean_title(self, title: str) -> str:
        return re.sub(r"\s+", " ", title.strip())

    def _clean_provider(self, provider: str) -> str:
        return re.sub(r"[®™©]|\s+", " ", provider).strip()

    def _is_valid_title(self, title: str) -> bool:
        return (
            title
            and 10 < len(title) < 200
            and not re.match(r"^\d+$", title)
            and not re.match(r"^[A-Z]{2,}$", title)
        )

    def _is_valid_provider(self, provider: str) -> bool:
        return (
            provider
            and 3 < len(provider) < 100
            and bool(re.search(r"[a-zA-Z]", provider))
        )

    def _calculate_title_confidence(
        self, title: str, full_text: str, base: float
    ) -> float:
        confidence = base
        if re.search(
            r"(?:title|course|subject)",
            full_text[: full_text.find(title) + 20],
            re.IGNORECASE,
        ):
            confidence += 0.2
        if re.match(r"^[A-Z][a-z]", title):
            confidence += 0.1
        return min(confidence, 1.0)

    def _calculate_provider_confidence(
        self, provider: str, full_text: str, base: float
    ) -> float:
        confidence = base
        if provider in self.common_providers:
            confidence += 0.2
        return min(confidence, 1.0)

    def _get_best_credit_value(self, credits: List[Dict], credit_type: str) -> float:
        filtered = [c for c in credits if c["type"] == credit_type]
        return filtered[0]["value"] if filtered else 0.0

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string into date object"""
        for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y"]:
            try:
                parsed = datetime.strptime(date_str, fmt).date()
                if datetime(2000, 1, 1).date() <= parsed <= datetime.now().date():
                    return parsed
            except ValueError:
                continue
        return None

    def _calculate_date_confidence(self, parsed_date: date) -> float:
        """Calculate confidence for a parsed date"""
        # Recent dates are more likely to be completion dates
        days_ago = (datetime.now().date() - parsed_date).days
        if days_ago < 365:
            return 0.9
        elif days_ago < 1095:  # 3 years
            return 0.7
        else:
            return 0.5

    def _deduplicate_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """Remove similar candidates"""
        unique = []
        for candidate in candidates:
            if not any(self._are_similar(candidate["text"], u["text"]) for u in unique):
                unique.append(candidate)
        return unique

    def _are_similar(self, text1: str, text2: str) -> bool:
        """Check if two text strings are similar enough to be duplicates"""
        return text1.lower().strip() == text2.lower().strip()

    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            "extracted_data": {
                "course_title": None,
                "provider": None,
                "cpe_credits": 0.0,
                "ethics_credits": 0.0,
                "completion_date": None,
                "certificate_number": None,
            },
            "confidence_score": 0.0,
            "insights": {},
            "suggestions": [],
            "review_flags": [
                {"field": "all", "severity": "high", "message": "No text to process"}
            ],
            "processing_method": "smart_review",
            "raw_text_length": 0,
            "candidates_found": 0,
        }

    def _count_candidates(self, insights: Dict) -> int:
        """Count total candidates found"""
        return (
            len(insights.get("possible_titles", []))
            + len(insights.get("possible_providers", []))
            + len(insights.get("possible_credits", []))
            + len(insights.get("possible_dates", []))
        )

    def _calculate_overall_confidence(self, insights: Dict) -> float:
        """Calculate overall processing confidence"""
        scores = []

        if insights["possible_titles"]:
            scores.append(insights["possible_titles"][0]["confidence"])
        if insights["possible_providers"]:
            scores.append(insights["possible_providers"][0]["confidence"])
        if insights["possible_credits"]:
            scores.append(max(c["confidence"] for c in insights["possible_credits"]))

        return sum(scores) / len(scores) if scores else 0.0

    # Additional helper methods would go here...
    def _find_reference_numbers(self, text: str) -> List[Dict]:
        """Find possible certificate/reference numbers"""
        candidates = []
        patterns = [
            r"(?:certificate|cert|reference)\s+(?:number|#|no):\s*([A-Z0-9-]+)",
            r"(?:confirmation|ref)\s+(?:number|#|no):\s*([A-Z0-9-]+)",
            r"#([A-Z0-9-]{5,})",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                ref_num = match.group(1).strip()
                if len(ref_num) >= 5:
                    candidates.append(
                        {"text": ref_num, "confidence": 0.8, "source": "pattern_match"}
                    )

        return candidates[:3]  # Top 3

    def _identify_document_type(self, text: str) -> str:
        """Identify the type of document"""
        if "certificate" in text.lower():
            return "certificate"
        elif "completion" in text.lower():
            return "completion_record"
        else:
            return "unknown"

    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases that might be useful"""
        # This could be enhanced with NLP libraries
        phrases = []
        if "ethics" in text.lower():
            phrases.append("ethics_content")
        if "nasba" in text.lower():
            phrases.append("nasba_sponsor")
        return phrases

    def _deduplicate_dates(self, candidates: List[Dict]) -> List[Dict]:
        """Remove duplicate dates"""
        seen_dates = set()
        unique = []
        for candidate in candidates:
            if candidate["date"] not in seen_dates:
                seen_dates.add(candidate["date"])
                unique.append(candidate)
        return unique
