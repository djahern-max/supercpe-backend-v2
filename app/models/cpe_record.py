# app/models/cpe_record.py - SIMPLIFIED VERSION

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
    )  # 'google_vision', 'manual', etc.
    raw_text = Column(Text, nullable=True)  # Keep this - it's valuable for debugging
    parsing_notes = Column(Text, nullable=True)

    # ===== SYSTEM FIELDS =====
    storage_tier = Column(String(20), default="free")  # 'free', 'premium'
    is_verified = Column(Boolean, default=False)  # For manual review
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verification_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    verified_by_user = relationship("User", foreign_keys=[verified_by])

    def __repr__(self):
        return f"<CPERecord(id={self.id}, course_title='{self.course_title}', cpe_credits={self.cpe_credits})>"

    @property
    def total_credits(self):
        """Total CPE credits (regular + ethics)"""
        return (self.cpe_credits or 0.0) + (self.ethics_credits or 0.0)

    @property
    def is_premium(self):
        """Check if this is a premium record"""
        return self.storage_tier == "premium"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
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
        }
