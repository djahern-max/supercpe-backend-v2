from sqlalchemy import Column, Integer, String, Date, Boolean, Text
from app.core.database import Base

class ComplianceRequirement(Base):
    __tablename__ = "compliance_requirements"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Jurisdiction
    state_code = Column(String(2), default="NH")
    state_name = Column(String(50), default="New Hampshire")
    
    # Requirements
    total_hours_required = Column(Integer, default=80)  # 2-year requirement
    ethics_hours_required = Column(Integer, default=4)
    reporting_period_months = Column(Integer, default=24)  # 2 years
    
    # Renewal info
    renewal_deadline = Column(String(50), default="June 30")
    ce_broker_required = Column(Boolean, default=True)
    
    # System
    effective_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
