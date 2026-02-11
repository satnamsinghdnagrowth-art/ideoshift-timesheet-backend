from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.db.session import Base


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class LeaveType(str, enum.Enum):
    FULL_DAY = "FULL_DAY"
    HALF_DAY = "HALF_DAY"
    SHORT_LEAVE = "SHORT_LEAVE"


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    from_date = Column(Date, nullable=False, index=True)
    to_date = Column(Date, nullable=False, index=True)
    hours = Column(Float, nullable=False, default=8.0)  # Hours per day
    leave_type = Column(SQLEnum(LeaveType), nullable=False, default=LeaveType.FULL_DAY)
    reason = Column(String(500), nullable=False)
    status = Column(SQLEnum(LeaveStatus), nullable=False, default=LeaveStatus.PENDING)
    admin_comment = Column(String(500), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)

    # Relationships
    user = relationship("User", back_populates="leave_requests", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approved_by])
