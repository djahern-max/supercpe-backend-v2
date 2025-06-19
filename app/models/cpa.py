# app/models/cpa.py - Update your CPA class
from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base


class CPA(Base):
    __tablename__ = "cpas"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # OPLC Data (from monthly spreadsheet)
    license_number = Column(String(20), unique=True, index=True, nullable=False)
    full_name = Column(String(200), nullable=False)
    license_issue_date = Column(Date, nullable=False)
    license_expiration_date = Column(Date, nullable=False)
    status = Column(String(50), default="Active")

    # Contact Info (optional - user can add later)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(20), nullable=True)

    # NEW: Passcode for secure signup
    passcode = Column(String(12), unique=True, index=True, nullable=True)

    # Compliance Tracking
    is_premium = Column(Boolean, default=False)
    total_cpe_hours = Column(Integer, default=0)
    ethics_hours = Column(Integer, default=0)

    # System fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_oplc_sync = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<CPA(license_number='{self.license_number}', name='{self.full_name}')>"
