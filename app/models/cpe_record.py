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
    __tablename__ = "cpe_records"  # Fixed: Added missing underscores

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # CPA association
    cpa_license_number = Column(String(20), nullable=False, index=True)

    # Document reference
    document_filename = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=True)

    # CPE details
    cpe_credits = Column(Float, default=0.0)
    ethics_credits = Column(Float, default=0.0)
    course_title = Column(String(500), nullable=True)
    provider = Column(String(255), nullable=True)
    completion_date = Column(Date, nullable=True)
    certificate_number = Column(String(100), nullable=True)

    # Parsing metadata
    confidence_score = Column(Float, default=0.0)
    parsing_method = Column(String(50), default="google_vision")
    raw_text = Column(Text, nullable=True)
    parsing_notes = Column(Text, nullable=True)

    # Verification status
    is_verified = Column(Boolean, default=False)
    verified_by = Column(String(100), nullable=True)
    verification_date = Column(DateTime(timezone=True), nullable=True)

    # ADD THIS FIELD for free tier tracking
    storage_tier = Column(String(20), default="free")  # "free" or "premium"

    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):  # Fixed: Added missing underscores
        return f"<CPERecord(cpa={self.cpa_license_number}, credits={self.cpe_credits}, course='{self.course_title}')>"


class CPEUploadSession(Base):
    __tablename__ = "cpe_upload_sessions"  # Fixed: Added missing underscores

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

    def __repr__(self):  # Fixed: Added missing underscores
        return (
            f"<CPEUploadSession(cpa={self.cpa_license_number}, status={self.status})>"
        )
