# app/models/cpe_record.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class CPERecord(Base):
    __tablename__ = "cpe_records"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # User association
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Core CPE fields
    date_completed = Column(
        Date, nullable=False, comment="Date when the course was completed"
    )
    course_type = Column(
        String(100), nullable=False, comment="Type/category of the course"
    )
    subject_area = Column(
        String(200), nullable=False, comment="Subject area or field of study"
    )
    name_of_course = Column(
        String(500), nullable=False, comment="Full name/title of the course"
    )
    educational_provider = Column(
        String(300),
        nullable=False,
        comment="Institution or organization providing the course",
    )
    subject = Column(
        String(300), nullable=True, comment="Additional subject details or description"
    )

    # System fields
    is_verified = Column(
        Boolean, default=False, comment="Whether record has been verified"
    )
    verified_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        comment="User who verified this record",
    )
    verification_date = Column(
        DateTime, nullable=True, comment="When the record was verified"
    )

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="cpe_records")
    verified_by_user = relationship("User", foreign_keys=[verified_by])

    def __repr__(self):
        return f"<CPERecord(id={self.id}, course='{self.name_of_course}', provider='{self.educational_provider}')>"

    class Config:
        from_attributes = True
