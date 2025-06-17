from google.cloud import vision
import io
import re
import json
from datetime import datetime, date
from typing import Dict, List, Optional
import logging
from PIL import Image
from pdf2image import convert_from_path
import tempfile
import os
from app.core.config import settings

logger = logging.getLogger(__name__)

class CPEParsingService:
    def __init__(self):
        if settings.gcv_enabled:
            try:
                self.vision_client = vision.ImageAnnotatorClient()
            except Exception as e:
                logger.error(f"Failed to initialize Google Cloud Vision client: {e}")
                self.vision_client = None
        else:
            self.vision_client = None
    
    async def parse_document(self, file_path: str, file_type: str) -> Dict:
        """Parse CPE document - make best guesses for user to review"""
        
        if not self.vision_client:
            return {"success": False, "error": "Vision API not enabled or failed to initialize"}
        
        try:
            # Extract text from document
            images = await self._prepare_document_for_ocr(file_path, file_type)
            
            full_text = ""
            for image_data in images:
                text = await self._extract_text_from_image(image_data)
                full_text += text + "\n"
            
            # Make best guesses with confidence scores
            parsed_fields = self._extract_fields_with_confidence(full_text)
            
            return {
                "success": True,
                "raw_text": full_text,
                "parsed_data": parsed_fields,
                "confidence_score": parsed_fields.get("overall_confidence", 0.0),
                "requires_review": True  # Always require human review
            }
            
        except Exception as e:
            logger.error(f"Error parsing document: {e}")
            return {"success": False, "error": str(e)}
    
    def _extract_fields_with_confidence(self, text: str) -> Dict:
        """Extract fields with individual confidence scores"""
        
        fields = {
            "cpe_hours": {"value": 0.0, "confidence": 0.0, "suggestions": []},
            "ethics_hours": {"value": 0.0, "confidence": 0.0, "suggestions": []},
            "course_title": {"value": "", "confidence": 0.0, "suggestions": []},
            "provider": {"value": "", "confidence": 0.0, "suggestions": []},
            "completion_date": {"value": "", "confidence": 0.0, "suggestions": []},
            "certificate_number": {"value": "", "confidence": 0.0, "suggestions": []},
            "overall_confidence": 0.0,
            "parsing_notes": []
        }
        
        # Extract CPE hours with multiple patterns and suggestions
        hour_patterns = [
            (r'CPE\s+Credits?\s*:?\s*(\d+(?:\.\d+)?)', 0.9),
            (r'(\d+(?:\.\d+)?)\s*CPE\s+Credits?', 0.8),
            (r'(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)', 0.6),
            (r'Credits?\s*:?\s*(\d+(?:\.\d+)?)', 0.5),
        ]
        
        for pattern, confidence in hour_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    hours = float(match)
                    if 0.5 <= hours <= 80:  # Reasonable range
                        fields["cpe_hours"]["suggestions"].append({
                            "value": hours, 
                            "confidence": confidence,
                            "context": f"Found in: {self._get_context(text, match)}"
                        })
                except ValueError:
                    continue
        
        # Pick best suggestion for each field
        if fields["cpe_hours"]["suggestions"]:
            best = max(fields["cpe_hours"]["suggestions"], key=lambda x: x["confidence"])
            fields["cpe_hours"]["value"] = best["value"]
            fields["cpe_hours"]["confidence"] = best["confidence"]
        
        # Extract course titles - look for likely candidates
        title_patterns = [
            (r'for\s+successfully\s+completing\s*\n([^\n]+)', 0.8),
            (r'(?:course|title|subject)(?:\s*:?\s*)([A-Z][^.!?\n]*)', 0.7),
            (r'([A-Z][A-Za-z\s&]{10,80})\s*\n', 0.5),
        ]
        
        for pattern, confidence in title_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                title = match.strip()
                if len(title) > 5 and not any(word in title.lower() for word in ['certificate', 'completion', 'awarded']):
                    fields["course_title"]["suggestions"].append({
                        "value": title,
                        "confidence": confidence,
                        "context": f"Found in context: {self._get_context(text, title)}"
                    })
        
        if fields["course_title"]["suggestions"]:
            best = max(fields["course_title"]["suggestions"], key=lambda x: x["confidence"])
            fields["course_title"]["value"] = best["value"]
            fields["course_title"]["confidence"] = best["confidence"]
        
        # Extract dates - find all possible dates
        date_patterns = [
            (r'Date\s*:?\s*([A-Za-z]+,?\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4})', 0.9),
            (r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})', 0.7),
            (r'([A-Za-z]+\s+\d{1,2},?\s+\d{4})', 0.6),
        ]
        
        for pattern, confidence in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                parsed_date = self._parse_date(match)
                if parsed_date:
                    fields["completion_date"]["suggestions"].append({
                        "value": parsed_date.isoformat(),
                        "confidence": confidence,
                        "context": f"Found: {match}"
                    })
        
        if fields["completion_date"]["suggestions"]:
            best = max(fields["completion_date"]["suggestions"], key=lambda x: x["confidence"])
            fields["completion_date"]["value"] = best["value"]
            fields["completion_date"]["confidence"] = best["confidence"]
        
        # Extract provider - first few lines often contain organization
        provider_patterns = [
            (r'^([A-Z][A-Za-z\s®&]+)\n', 0.8),
            (r'([A-Z][A-Za-z\s&®]{10,50})\s*(?:Professional|Education|Training|Institute)', 0.9),
        ]
        
        for pattern, confidence in provider_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                provider = match.strip()
                if len(provider) > 3:
                    fields["provider"]["suggestions"].append({
                        "value": provider,
                        "confidence": confidence,
                        "context": "Found at document header"
                    })
        
        if fields["provider"]["suggestions"]:
            best = max(fields["provider"]["suggestions"], key=lambda x: x["confidence"])
            fields["provider"]["value"] = best["value"]
            fields["provider"]["confidence"] = best["confidence"]
        
        # Calculate overall confidence
        confidence_values = [
            fields["cpe_hours"]["confidence"],
            fields["course_title"]["confidence"],
            fields["completion_date"]["confidence"],
            fields["provider"]["confidence"]
        ]
        fields["overall_confidence"] = sum(confidence_values) / len(confidence_values)
        
        # Add summary notes
        fields["parsing_notes"] = [
            f"✅ Found {len(fields['cpe_hours']['suggestions'])} possible CPE hour values",
            f"✅ Found {len(fields['course_title']['suggestions'])} possible course titles",
            f"✅ Found {len(fields['completion_date']['suggestions'])} possible dates",
            f"✅ Found {len(fields['provider']['suggestions'])} possible providers",
            f"📝 Overall confidence: {fields['overall_confidence']:.1%} - Review recommended"
        ]
        
        return fields
    
    def _get_context(self, text: str, match: str, context_length: int = 50) -> str:
        """Get surrounding context for a match"""
        try:
            index = text.find(str(match))
            if index != -1:
                start = max(0, index - context_length)
                end = min(len(text), index + len(str(match)) + context_length)
                return text[start:end].replace('\n', ' ')
        except:
            pass
        return str(match)
    
    # ... (keep the existing helper methods for image processing and date parsing)
    
    async def _prepare_document_for_ocr(self, file_path: str, file_type: str) -> List[bytes]:
        """Convert document to images for OCR processing"""
        images = []
        
        if file_type.lower() == '.pdf':
            try:
                pdf_images = convert_from_path(file_path, dpi=300)
                for pdf_image in pdf_images:
                    img_byte_arr = io.BytesIO()
                    pdf_image.save(img_byte_arr, format='PNG')
                    images.append(img_byte_arr.getvalue())
            except Exception as e:
                logger.error(f"Error converting PDF: {e}")
                raise
        elif file_type.lower() in ['.jpg', '.jpeg', '.png', '.tiff']:
            with open(file_path, 'rb') as image_file:
                images.append(image_file.read())
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        return images
    
    async def _extract_text_from_image(self, image_data: bytes) -> str:
        """Extract text from image using Google Cloud Vision"""
        image = vision.Image(content=image_data)
        response = self.vision_client.text_detection(image=image)
        texts = response.text_annotations
        return texts[0].description if texts else ""
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats"""
        date_formats = [
            "%A, %B %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%m-%d-%Y", 
            "%m/%d/%y", "%m-%d-%y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
            "%b %d, %Y", "%B %d %Y"
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None
