from sqlalchemy import Column, Date, Integer, DateTime, ForeignKey, UniqueConstraint, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.db.session import Base


class WorkingSaturday(Base):
    """
    Stores admin-defined working Saturdays.
    One working Saturday per month (typically 2nd Saturday).
    All other Saturdays and Sundays are considered overtime.
    """
    __tablename__ = "working_saturdays"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_date = Column(Date, nullable=False, unique=True, index=True)
    month = Column(Integer, nullable=False)  # 1-12
    year = Column(Integer, nullable=False)   # e.g., 2026
    description = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Unique constraint: one working Saturday per month
    __table_args__ = (
        UniqueConstraint('year', 'month', name='uq_working_saturday_month'),
    )
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
