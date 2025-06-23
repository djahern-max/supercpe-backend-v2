# app/services/vision_service.py - SIMPLIFIED VERSION

import logging
import re
from typing import Dict, Optional, List
from datetime import datetime, date
from google.cloud import vision

logger = logging.getLogger(__name__)


class SimplifiedVisionService:
    """Simplified vision service focused on core CPE data extraction"""
    
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
    
    def parse_cpe_certificate(self, raw_text: str) -> Dict:
        """
        Parse core CPE data from raw text.
        Focus on reliability over completeness.
        """
        if not raw_text:
            return self._empty_result()
        
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
            
            # Only return fields where we have reasonable confidence
            filtered_result = {}
            for key, value in result.items():
                if value is not None and value != "" and value != 0.0:
                    filtered_result[key] = value
            
            return filtered_result
            
        except Exception as e:
            logger.error(f"Error parsing certificate: {e}")
            return self._empty_result()
    
    def _extract_course_title(self, text: str) -> Optional[str]:
        """Extract course title - look for common patterns"""
        patterns = [
            r"(?:course title|title|course|subject):\s*([^\n\r]+)",
            r"(?:successfully completing|completion of)\s+([^\n\r]+)",
            r"certificate of completion\s+(?:for|awarded to).*?(?:for|in)\s+([^\n\r]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                title = match.group(1).strip()
                # Clean up common artifacts
                title = re.sub(r"^(for|in|of)\s+", "", title, flags=re.IGNORECASE)
                title = re.sub(r"\s+", " ", title)  # Normalize whitespace
                if len(title) > 10 and len(title) < 200:  # Reasonable length
                    return title
        
        return None
    
    def _extract_provider(self, text: str) -> Optional[str]:
        """Extract provider/sponsor name"""
        patterns = [
            r"(?:provider|sponsor|sponsored by|offered by):\s*([^\n\r]+)",
            r"^([A-Z][^\n\r]*(?:CPE|Education|Institute|University|College|Academy))",
            r"NASBA\s+Sponsor[^\n\r]*\n([^\n\r]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                provider = match.group(1).strip()
                # Clean up
                provider = re.sub(r"[®™©]", "", provider)
                provider = re.sub(r"\s+", " ", provider)
                if len(provider) > 3 and len(provider) < 100:
                    return provider
        
        return None
    
    def _extract_cpe_credits(self, text: str) -> float:
        """Extract CPE credits - be very precise about this"""
        patterns = [
            r"CPE\s+Credits?:\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s+CPE\s+Credits?",
            r"Credits?:\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s+(?:hours?|credits?)\s+(?:of\s+)?CPE",
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
    
    def _extract_ethics_credits(self, text: str) -> float:
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
    
    def _extract_completion_date(self, text: str) -> Optional[date]:
        """Extract completion date"""
        patterns = [
            r"(?:completion date|completed on|date):\s*(\w+,?\s+\w+\s+\d{1,2},?\s+\d{4})",
            r"(?:date|completed):\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
            r"(\w+\s+\d{1,2},?\s+\d{4})",  # "June 6, 2025"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    # Try different date parsing approaches
                    parsed_date = self._parse_date_string(match)
                    if parsed_date:
                        return parsed_date
                except:
                    continue
        
        return None
    
    def _parse_date_string(self, date_str: str) -> Optional[date]:
        """Parse various date string formats"""
        date_str = date_str.strip()
        
        formats = [
            "%B %d, %Y",     # "June 6, 2025"
            "%b %d, %Y",     # "Jun 6, 2025"
            "%m/%d/%Y",      # "6/6/2025"
            "%m-%d-%Y",      # "6-6-2025"
            "%Y-%m-%d",      # "2025-06-06"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None
    
    def _extract_certificate_number(self, text: str) -> Optional[str]:
        """Extract certificate number if present"""
        patterns = [
            r"Certificate\s+(?:Number|#):\s*([A-Z0-9-]+)",
            r"Certificate\s+ID:\s*([A-Z0-9-]+)",
            r"(?:ID|Number):\s*([A-Z0-9-]{5,20})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                cert_num = match.group(1).strip()
                if len(cert_num) >= 3:
                    return cert_num
        
        return None
    
    def _calculate_confidence(self, text: str) -> float:
        """Calculate parsing confidence based on data found"""
        confidence = 0.0
        
        # Key indicators of a valid CPE certificate
        indicators = [
            r"CPE|Continuing Professional Education",
            r"Certificate of Completion",
            r"Credits?",
            r"NASBA",
            r"CPA",
        ]
        
        for indicator in indicators:
            if re.search(indicator, text, re.IGNORECASE):
                confidence += 0.2
        
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