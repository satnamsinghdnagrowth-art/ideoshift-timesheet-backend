from sqlalchemy import Column, Date, Integer, DateTime, ForeignKey, UniqueConstraint, String
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

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    work_date = Column(Date, nullable=False, unique=True, index=True)
    month = Column(Integer, nullable=False)  # 1-12
    year = Column(Integer, nullable=False)   # e.g., 2026
    description = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Unique constraint: one working Saturday per month
    __table_args__ = (
        UniqueConstraint('year', 'month', name='uq_working_saturday_month'),
    )
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
