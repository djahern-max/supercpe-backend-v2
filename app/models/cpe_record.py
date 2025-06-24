# app/models/cpe_record.py - ENHANCED VERSION with Smart Review Support

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
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import json
from typing import Dict, List, Optional


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

    # ===== CORE CPE DATA (Keep these - they work) =====
    cpe_credits = Column(Float, default=0.0, nullable=False)
    ethics_credits = Column(Float, default=0.0, nullable=False)
    course_title = Column(String(500), nullable=True)
    provider = Column(String(255), nullable=True)
    completion_date = Column(Date, nullable=True)
    certificate_number = Column(String(100), nullable=True)

    # ===== AI PARSING METADATA (Keep for debugging) =====
    confidence_score = Column(Float, default=0.0)
    parsing_method = Column(
        String(50), default="manual"
    )  # 'google_vision', 'manual', 'smart_review', 'human_verified', etc.
    raw_text = Column(Text, nullable=True)  # Keep this - it's valuable for debugging
    parsing_notes = Column(Text, nullable=True)

    # ===== NEW: SMART REVIEW FIELDS =====
    # Store smart insights as JSON text (multiple candidates for each field)
    smart_insights = Column(
        Text,
        nullable=True,
        comment="JSON string of smart extraction insights with multiple candidates",
    )

    # Store suggestions for user review as JSON text
    suggestions = Column(
        Text,
        nullable=True,
        comment="JSON string of review suggestions for user interface",
    )

    # Store review flags as JSON text
    review_flags = Column(
        Text, nullable=True, comment="JSON string of fields needing attention"
    )

    # Enhanced status tracking
    needs_review = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether record needs human review",
    )

    # Review workflow tracking
    review_started_at = Column(
        DateTime, nullable=True, comment="When user started reviewing this certificate"
    )
    review_completed_at = Column(
        DateTime, nullable=True, comment="When user completed review"
    )

    # ===== SYSTEM FIELDS =====
    storage_tier = Column(String(20), default="free")  # 'free', 'premium'
    is_verified = Column(Boolean, default=False)  # For manual review
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verification_date = Column(DateTime, nullable=True)

    # Timestamps - Enhanced
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    verified_by_user = relationship("User", foreign_keys=[verified_by])

    def __repr__(self):
        return f"<CPERecord(id={self.id}, course_title='{self.course_title}', cpe_credits={self.cpe_credits}, needs_review={self.needs_review})>"

    @property
    def total_credits(self):
        """Total CPE credits (regular + ethics)"""
        return (self.cpe_credits or 0.0) + (self.ethics_credits or 0.0)

    @property
    def is_premium(self):
        """Check if this is a premium record"""
        return self.storage_tier == "premium"

    @property
    def has_smart_data(self):
        """Check if this record has smart review data available"""
        return bool(self.smart_insights or self.suggestions or self.review_flags)

    @property
    def is_complete(self):
        """Check if record has all required fields for reporting"""
        return bool(
            self.course_title
            and self.provider
            and self.cpe_credits > 0
            and self.completion_date
        )

    @property
    def review_status(self):
        """Get current review status"""
        if self.is_verified:
            return "verified"
        elif self.needs_review:
            if self.review_started_at:
                return "in_review"
            else:
                return "needs_review"
        elif self.is_complete:
            return "complete"
        else:
            return "incomplete"

    def get_smart_insights(self) -> Dict:
        """Parse and return smart insights data"""
        if not self.smart_insights:
            return {}
        try:
            return json.loads(self.smart_insights)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_suggestions(self) -> List[Dict]:
        """Parse and return suggestions data"""
        if not self.suggestions:
            return []
        try:
            return json.loads(self.suggestions)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_review_flags(self) -> List[Dict]:
        """Parse and return review flags data"""
        if not self.review_flags:
            return []
        try:
            return json.loads(self.review_flags)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_smart_insights(self, insights: Dict):
        """Store smart insights data as JSON"""
        if insights:
            self.smart_insights = json.dumps(insights)
        else:
            self.smart_insights = None

    def set_suggestions(self, suggestions: List[Dict]):
        """Store suggestions data as JSON"""
        if suggestions:
            self.suggestions = json.dumps(suggestions)
        else:
            self.suggestions = None

    def set_review_flags(self, flags: List[Dict]):
        """Store review flags data as JSON"""
        if flags:
            self.review_flags = json.dumps(flags)
            self.needs_review = True  # Auto-set needs_review if there are flags
        else:
            self.review_flags = None

    def start_review(self):
        """Mark that user has started reviewing this certificate"""
        self.review_started_at = func.now()
        self.updated_at = func.now()

    def complete_review(self, verified_by_user_id: Optional[int] = None):
        """Mark review as complete and verified"""
        self.review_completed_at = func.now()
        self.needs_review = False
        self.is_verified = True
        if verified_by_user_id:
            self.verified_by = verified_by_user_id
            self.verification_date = func.now()

        # Clear suggestions and flags since they've been addressed
        self.suggestions = None
        self.review_flags = None

        # Boost confidence to 1.0 since human verified
        self.confidence_score = 1.0
        self.parsing_method = "human_verified"
        self.updated_at = func.now()

    def clear_smart_data(self):
        """Clear all smart review data (useful after manual edits)"""
        self.smart_insights = None
        self.suggestions = None
        self.review_flags = None
        self.needs_review = False

    def to_dict(self, include_smart_data: bool = False):
        """Convert to dictionary for API responses"""
        base_dict = {
            "id": self.id,
            "cpa_license_number": self.cpa_license_number,
            "course_title": self.course_title,
            "provider": self.provider,
            "cpe_credits": self.cpe_credits,
            "ethics_credits": self.ethics_credits,
            "total_credits": self.total_credits,
            "completion_date": (
                self.completion_date.isoformat() if self.completion_date else None
            ),
            "certificate_number": self.certificate_number,
            "storage_tier": self.storage_tier,
            "is_verified": self.is_verified,
            "confidence_score": self.confidence_score,
            "parsing_method": self.parsing_method,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # Enhanced status fields
            "needs_review": self.needs_review,
            "is_complete": self.is_complete,
            "review_status": self.review_status,
            "has_smart_data": self.has_smart_data,
        }

        # Include smart review data if requested
        if include_smart_data:
            base_dict.update(
                {
                    "smart_insights": self.get_smart_insights(),
                    "suggestions": self.get_suggestions(),
                    "review_flags": self.get_review_flags(),
                    "review_started_at": (
                        self.review_started_at.isoformat()
                        if self.review_started_at
                        else None
                    ),
                    "review_completed_at": (
                        self.review_completed_at.isoformat()
                        if self.review_completed_at
                        else None
                    ),
                    "raw_text_preview": (
                        (
                            self.raw_text[:200] + "..."
                            if self.raw_text and len(self.raw_text) > 200
                            else self.raw_text
                        )
                        if self.raw_text
                        else None
                    ),
                }
            )

        return base_dict

    def to_csv_row(self) -> Dict:
        """Convert to CSV-ready format for compliance reporting"""
        return {
            "License_Number": self.cpa_license_number,
            "Course_Title": self.course_title or "",
            "Provider": self.provider or "",
            "CPE_Credits": self.cpe_credits or 0.0,
            "Ethics_Credits": self.ethics_credits or 0.0,
            "Total_Credits": self.total_credits,
            "Completion_Date": (
                self.completion_date.strftime("%m/%d/%Y")
                if self.completion_date
                else ""
            ),
            "Certificate_Number": self.certificate_number or "",
            "Verified": "Yes" if self.is_verified else "No",
            "Upload_Date": (
                self.created_at.strftime("%m/%d/%Y") if self.created_at else ""
            ),
        }

    def get_review_summary(self) -> Dict:
        """Get a summary of what needs review"""
        summary = {
            "certificate_id": self.id,
            "filename": self.original_filename,
            "status": self.review_status,
            "confidence": self.confidence_score,
            "missing_fields": [],
            "suggestions_count": len(self.get_suggestions()),
            "flags_count": len(self.get_review_flags()),
            "priority": "low",
        }

        # Check for missing critical fields
        if not self.course_title:
            summary["missing_fields"].append("course_title")
        if not self.provider:
            summary["missing_fields"].append("provider")
        if not self.cpe_credits or self.cpe_credits <= 0:
            summary["missing_fields"].append("cpe_credits")
        if not self.completion_date:
            summary["missing_fields"].append("completion_date")

        # Determine priority
        if len(summary["missing_fields"]) >= 2:
            summary["priority"] = "high"
        elif len(summary["missing_fields"]) == 1 or summary["flags_count"] > 0:
            summary["priority"] = "medium"

        return summary

    @classmethod
    def get_records_needing_review(cls, session, user_id: int):
        """Class method to get all records needing review for a user"""
        return (
            session.query(cls)
            .filter(cls.user_id == user_id, cls.needs_review == True)
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def get_review_stats(cls, session, user_id: int) -> Dict:
        """Get review statistics for a user"""
        total = session.query(cls).filter(cls.user_id == user_id).count()
        needs_review = (
            session.query(cls)
            .filter(cls.user_id == user_id, cls.needs_review == True)
            .count()
        )
        verified = (
            session.query(cls)
            .filter(cls.user_id == user_id, cls.is_verified == True)
            .count()
        )
        complete = session.query(cls).filter(cls.user_id == user_id).all()
        complete_count = sum(1 for record in complete if record.is_complete)

        return {
            "total_certificates": total,
            "needs_review": needs_review,
            "verified": verified,
            "complete": complete_count,
            "incomplete": total - complete_count,
            "review_percentage": round((verified / total * 100) if total > 0 else 0, 1),
        }
