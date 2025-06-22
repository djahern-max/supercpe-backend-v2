# app/services/vision_service.py - Enhanced for CE Broker Integration

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
from app.models.cpe_record import CEBrokerMappings

logger = logging.getLogger(__name__)


class EnhancedVisionService:
    """Enhanced vision service with CE Broker field extraction"""
    
    def __init__(self):
        self.confidence_threshold = 0.7
        
    def extract_ce_broker_fields(self, raw_text: str, parsed_data: Dict) -> Dict:
        """Extract CE Broker specific fields from certificate text"""
        
        # Get basic extracted data
        course_title = parsed_data.get('course_title', '')
        field_of_study = parsed_data.get('field_of_study', '')
        instructional_method = self.extract_instructional_method(raw_text)
        
        # Auto-detect CE Broker fields
        subject_areas = CEBrokerMappings.detect_subject_areas(
            course_title, field_of_study, raw_text
        )
        
        course_type = CEBrokerMappings.detect_course_type(raw_text, instructional_method)
        
        delivery_method = CEBrokerMappings.detect_delivery_method(
            course_type, instructional_method, raw_text
        )
        
        # Extract additional fields
        nasba_sponsor = self.extract_nasba_sponsor(raw_text)
        course_code = self.extract_course_code(raw_text)
        program_level = self.extract_program_level(raw_text)
        
        return {
            'course_type': course_type,
            'delivery_method': delivery_method,
            'instructional_method': instructional_method,
            'subject_areas': subject_areas,
            'nasba_sponsor_number': nasba_sponsor,
            'course_code': course_code,
            'program_level': program_level,
            'ce_category': self.determine_ce_category(subject_areas, course_title),
            'ce_broker_ready': self.check_ce_broker_readiness(parsed_data, {
                'course_type': course_type,
                'delivery_method': delivery_method,
                'subject_areas': subject_areas
            })
        }
    
    def extract_instructional_method(self, raw_text: str) -> Optional[str]:
        """Extract instructional method from certificate text"""
        if not raw_text:
            return None
            
        # Common patterns for instructional methods
        patterns = [
            r'Instructional Method:\s*([^\n]+)',
            r'Method:\s*([^\n]+)',
            r'Delivery:\s*([^\n]+)',
            r'Format:\s*([^\n]+)',
            r'(QAS Self-Study)',
            r'(Group Study)',
            r'(Individual Study)',
            r'(Self-Study)',
            r'(Online)',
            r'(Webinar)',
            r'(Classroom)',
            r'(Seminar)'
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
            r'NASBA\s*#?\s*(\d+)',
            r'Sponsor\s*#?\s*(\d+)', 
            r'NASBA\s+Sponsor\s*#?\s*(\d+)',
            r'Registry\s*#?\s*(\d+)',
            r'#(\d{6})',  # 6-digit numbers often NASBA
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
            r'Course Code:\s*([^\n]+)',
            r'Code:\s*([A-Z0-9\-_]+)',
            r'Course\s*#:\s*([^\n]+)',
            r'Program Code:\s*([^\n]+)',
            r'([A-Z]\d{3}-\d{4}-\d{2}-[A-Z]+)',  # Pattern like M290-2024-01-SSDL
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
            r'Level:\s*(Basic|Intermediate|Advanced)',
            r'Program Level:\s*(Basic|Intermediate|Advanced)',
            r'\b(Basic|Intermediate|Advanced)\s+Level',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()
                
        return None
    
    def determine_ce_category(self, subject_areas: List[str], course_title: str) -> str:
        """Determine CE category for CE Broker"""
        
        # Check for ethics-related content
        ethics_keywords = ['ethics', 'professional responsibility', 'conduct', 'integrity']
        ethics_subjects = ['Administrative practices', 'Business law']
        
        course_title_lower = (course_title or '').lower()
        
        # Check if this is an ethics course
        if (any(keyword in course_title_lower for keyword in ethics_keywords) or
            any(subject in subject_areas for subject in ethics_subjects)):
            return 'Professional Ethics CPE'
            
        # Check for other specialized categories
        if 'Governmental accounting' in subject_areas or 'Governmental auditing' in subject_areas:
            return 'General CPE'  # Could be more specific if needed
            
        return 'General CPE'  # Default
    
    def check_ce_broker_readiness(self, parsed_data: Dict, ce_broker_data: Dict) -> bool:
        """Check if record has all required fields for CE Broker export"""
        required_fields = [
            parsed_data.get('course_title'),
            parsed_data.get('provider'),
            parsed_data.get('completion_date'),
            parsed_data.get('cpe_credits'),
            ce_broker_data.get('course_type'),
            ce_broker_data.get('delivery_method'),
            ce_broker_data.get('subject_areas')
        ]
        
        return all(field is not None and field != '' and field != [] for field in required_fields)
    
    def enhance_parsed_data(self, raw_text: str, basic_parsed_data: Dict) -> Dict:
        """Main method to enhance basic parsed data with CE Broker fields"""
        
        # Extract CE Broker specific fields
        ce_broker_fields = self.extract_ce_broker_fields(raw_text, basic_parsed_data)
        
        # Combine with basic data
        enhanced_data = {**basic_parsed_data, **ce_broker_fields}
        
        # Add metadata
        enhanced_data['parsing_enhanced'] = True
        enhanced_data['enhancement_timestamp'] = datetime.now().isoformat()
        
        logger.info(f"Enhanced parsing completed. CE Broker ready: {ce_broker_fields['ce_broker_ready']}")
        
        return enhanced_data


# Update the existing create_cpe_record_from_parsing function
def create_enhanced_cpe_record_from_parsing(
    parsing_result: Dict,
    file,
    license_number: str,
    current_user,
    upload_result: Dict,
    storage_tier: str = "free"
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