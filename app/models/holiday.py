"""
Holiday Model

Represents company holidays, national holidays, and other non-working days.
Work performed on holidays is considered overtime and requires approval.
"""

from sqlalchemy import Column, String, Date, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import date

from app.db.session import Base


class Holiday(Base):
    """Holiday model for tracking non-working days"""
    
    __tablename__ = "holidays"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    holiday_date = Column(Date, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_mandatory = Column(Boolean, default=True, nullable=False)  # Mandatory vs optional
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(Date, default=date.today, nullable=False)
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_holidays_year_month', 'holiday_date'),
    )
    
    def __repr__(self):
        return f"<Holiday(date={self.holiday_date}, name={self.name})>"
