# app/models/cpe_record.py - FIXED VERSION with explicit foreign key relationships

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

    # ===== CORE CPE DATA =====
    cpe_credits = Column(Float, default=0.0, nullable=False)
    ethics_credits = Column(Float, default=0.0, nullable=False)
    course_title = Column(String(500), nullable=True)
    provider = Column(String(255), nullable=True)
    completion_date = Column(Date, nullable=True)
    certificate_number = Column(String(100), nullable=True)

    # ===== AI PARSING METADATA =====
    confidence_score = Column(Float, default=0.0)
    parsing_method = Column(String(50), default="manual")
    raw_text = Column(Text, nullable=True)
    parsing_notes = Column(Text, nullable=True)

    # ===== SMART REVIEW FIELDS =====
    smart_insights = Column(
        Text, nullable=True, comment="JSON string of smart extraction insights"
    )
    suggestions = Column(
        Text, nullable=True, comment="JSON string of review suggestions"
    )
    review_flags = Column(
        Text, nullable=True, comment="JSON string of fields needing attention"
    )
    needs_review = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether record needs human review",
    )
    review_started_at = Column(
        DateTime, nullable=True, comment="When user started reviewing"
    )
    review_completed_at = Column(
        DateTime, nullable=True, comment="When user completed review"
    )

    # ===== SYSTEM FIELDS =====
    storage_tier = Column(String(20), default="free")
    is_verified = Column(Boolean, default=False)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verification_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # ===== FIXED RELATIONSHIPS with explicit foreign_keys =====
    user = relationship("User", foreign_keys=[user_id], back_populates="cpe_records")
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

    @property
    def has_smart_data(self):
        """Check if record has smart extraction data"""
        return bool(self.smart_insights or self.suggestions or self.review_flags)

    def get_smart_insights(self) -> Optional[Dict]:
        """Get smart insights as dictionary"""
        if self.smart_insights:
            try:
                return json.loads(self.smart_insights)
            except:
                return None
        return None

    def get_suggestions(self) -> Optional[List]:
        """Get suggestions as list"""
        if self.suggestions:
            try:
                return json.loads(self.suggestions)
            except:
                return None
        return None

    def get_review_flags(self) -> Optional[List]:
        """Get review flags as list"""
        if self.review_flags:
            try:
                return json.loads(self.review_flags)
            except:
                return None
        return None
