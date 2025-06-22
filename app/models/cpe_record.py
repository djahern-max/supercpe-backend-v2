# app/models/cpe_record.py - Enhanced for CE Broker Integration

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    Date,
    ForeignKey,
    ARRAY,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class CPERecord(Base):
    __tablename__ = "cpe_records"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # CPA association
    cpa_license_number = Column(String(20), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Document reference
    document_filename = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=True)

    # Core CPE details
    cpe_credits = Column(Float, default=0.0)
    ethics_credits = Column(Float, default=0.0)
    course_title = Column(String(500), nullable=True)
    provider = Column(String(255), nullable=True)
    completion_date = Column(Date, nullable=True)
    certificate_number = Column(String(100), nullable=True)

    # NEW: CE Broker Required Fields
    course_type = Column(String(50), nullable=True)  # 'live' or 'anytime'
    delivery_method = Column(
        String(100), nullable=True
    )  # 'Computer-Based Training', 'Prerecorded Broadcast', 'Correspondence'
    instructional_method = Column(
        String(100), nullable=True
    )  # 'QAS Self-Study', 'Group Study', etc.

    # Subject areas (multiple selections possible)
    subject_areas = Column(
        ARRAY(String), nullable=True
    )  # ['Taxes', 'Finance', 'Business law']
    field_of_study = Column(
        String(100), nullable=True
    )  # Original field from certificate

    # CE Broker categorization
    ce_category = Column(
        String(50), nullable=True
    )  # 'General CPE', 'Professional Ethics CPE', etc.

    # NASBA/Sponsor information
    nasba_sponsor_number = Column(String(20), nullable=True)
    sponsor_name = Column(String(255), nullable=True)

    # Course details for CE Broker
    course_code = Column(String(50), nullable=True)
    program_level = Column(
        String(50), nullable=True
    )  # 'Basic', 'Intermediate', 'Advanced'

    # CE Broker export tracking
    ce_broker_exported = Column(Boolean, default=False)
    ce_broker_export_date = Column(DateTime(timezone=True), nullable=True)
    ce_broker_ready = Column(Boolean, default=False)  # All required fields present

    # Parsing metadata
    confidence_score = Column(Float, default=0.0)
    parsing_method = Column(String(50), default="google_vision")
    raw_text = Column(Text, nullable=True)
    parsing_notes = Column(Text, nullable=True)

    # Verification status
    is_verified = Column(Boolean, default=False)
    verified_by = Column(String(100), nullable=True)
    verification_date = Column(DateTime(timezone=True), nullable=True)

    # Storage tier tracking
    storage_tier = Column(String(20), default="free")  # "free" or "premium"

    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="cpe_records")

    def __repr__(self):
        return f"<CPERecord(cpa={self.cpa_license_number}, credits={self.cpe_credits}, course='{self.course_title}')>"

    def to_ce_broker_format(self):
        """Convert record to CE Broker export format"""
        return {
            "course_name": self.course_title,
            "provider_name": self.provider,
            "completion_date": (
                self.completion_date.isoformat() if self.completion_date else None
            ),
            "cpe_hours": self.cpe_credits,
            "ethics_hours": self.ethics_credits,
            "course_type": self.course_type or "anytime",
            "delivery_method": self.delivery_method or "Computer-Based Training",
            "subject_areas": self.subject_areas or [],
            "instructional_method": self.instructional_method,
            "nasba_sponsor": self.nasba_sponsor_number,
            "course_code": self.course_code,
            "ce_broker_ready": self.ce_broker_ready,
            "certificate_id": self.id,
        }

    def update_ce_broker_fields(self, **kwargs):
        """Update CE Broker specific fields and check if ready for export"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        # Check if all required fields are present
        self.ce_broker_ready = all(
            [
                self.course_title,
                self.provider,
                self.completion_date,
                self.cpe_credits,
                self.course_type,
                self.delivery_method,
                self.subject_areas,
            ]
        )


# CE Broker Field Mappings and Helpers
class CEBrokerMappings:
    """Static mappings for CE Broker field values"""

    COURSE_TYPES = {
        "live": "Live (involves live interaction with presenter/host)",
        "anytime": "Anytime (is not date, time or location specific)",
    }

    DELIVERY_METHODS = [
        "Computer-Based Training (ie: online courses)",
        "Prerecorded Broadcast",
        "Correspondence",
    ]

    SUBJECT_AREAS = [
        "Public accounting",
        "Governmental accounting",
        "Public auditing",
        "Governmental auditing",
        "Administrative practices",
        "Social environment of business",
        "Business law",
        "Business management and organization",
        "Finance",
        "Management advisory services",
        "Marketing",
        "Communications",
        "Personal development",
        "Personnel and human resources",
        "Computer science",
        "Economics",
        "Mathematics",
        "Production",
        "Specialized knowledge and its application",
        "Statistics",
        "Taxes",
    ]

    # Auto-mapping keywords to subject areas
    SUBJECT_KEYWORDS = {
        "tax": ["Taxes"],
        "taxation": ["Taxes"],
        "audit": ["Public auditing"],
        "auditing": ["Public auditing"],
        "finance": ["Finance"],
        "financial": ["Finance"],
        "accounting": ["Public accounting"],
        "ethics": ["Administrative practices"],
        "law": ["Business law"],
        "legal": ["Business law"],
        "management": ["Business management and organization"],
        "marketing": ["Marketing"],
        "communication": ["Communications"],
        "computer": ["Computer science"],
        "technology": ["Computer science"],
        "statistics": ["Statistics"],
        "economics": ["Economics"],
        "government": ["Governmental accounting", "Governmental auditing"],
    }

    @classmethod
    def detect_subject_areas(cls, course_title, field_of_study, raw_text):
        """Auto-detect subject areas from certificate content"""
        detected = set()

        # Combine all text for analysis
        text_to_analyze = " ".join(
            filter(None, [course_title or "", field_of_study or "", raw_text or ""])
        ).lower()

        # Check for keyword matches
        for keyword, subjects in cls.SUBJECT_KEYWORDS.items():
            if keyword in text_to_analyze:
                detected.update(subjects)

        # If nothing detected, try direct field mapping
        if not detected and field_of_study:
            field_lower = field_of_study.lower()
            if field_lower in cls.SUBJECT_KEYWORDS:
                detected.update(cls.SUBJECT_KEYWORDS[field_lower])

        # Default to appropriate subject if still nothing
        if not detected:
            detected.add("Specialized knowledge and its application")

        return list(detected)

    @classmethod
    def detect_course_type(cls, raw_text, instructional_method):
        """Auto-detect course type from certificate content"""
        if not raw_text:
            return "anytime"

        text_lower = (raw_text + " " + (instructional_method or "")).lower()

        # Live indicators
        live_keywords = [
            "webinar",
            "live",
            "virtual",
            "instructor-led",
            "classroom",
            "seminar",
        ]
        if any(keyword in text_lower for keyword in live_keywords):
            return "live"

        # Anytime indicators
        anytime_keywords = [
            "self-study",
            "self-paced",
            "online",
            "correspondence",
            "on-demand",
        ]
        if any(keyword in text_lower for keyword in anytime_keywords):
            return "anytime"

        return "anytime"  # Default

    @classmethod
    def detect_delivery_method(cls, course_type, instructional_method, raw_text):
        """Auto-detect delivery method"""
        if course_type == "live":
            return "Computer-Based Training (ie: online courses)"  # Most common for live online

        # For anytime courses, check instructional method
        text_to_check = (instructional_method or "") + " " + (raw_text or "")
        text_lower = text_to_check.lower()

        if "correspondence" in text_lower or "mail" in text_lower:
            return "Correspondence"
        elif "broadcast" in text_lower or "recorded" in text_lower:
            return "Prerecorded Broadcast"
        else:
            return "Computer-Based Training (ie: online courses)"


class CPEUploadSession(Base):
    __tablename__ = "cpe_upload_sessions"

    id = Column(Integer, primary_key=True, index=True)
    cpa_license_number = Column(String(20), nullable=False, index=True)

    # Payment tracking
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    session_type = Column(String(50), nullable=False)

    # Processing status
    status = Column(String(50), default="pending")
    documents_uploaded = Column(Integer, default=0)
    documents_processed = Column(Integer, default=0)
    total_credits_found = Column(Float, default=0.0)

    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return (
            f"<CPEUploadSession(cpa={self.cpa_license_number}, status={self.status})>"
        )
