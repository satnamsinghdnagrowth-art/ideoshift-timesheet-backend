from sqlalchemy import Column, String, Date, Numeric, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.db.session import Base


class TaskEntryStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TaskEntry(Base):
    __tablename__ = "task_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=True)  # Now optional - clients tracked per sub-entry
    work_date = Column(Date, nullable=False, index=True)
    task_name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    total_hours = Column(Numeric(4, 2), nullable=False)
    status = Column(SQLEnum(TaskEntryStatus), nullable=False, default=TaskEntryStatus.DRAFT)
    admin_comment = Column(String(500), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # New fields for overtime tracking
    is_overtime = Column(Boolean, default=False, nullable=False)
    overtime_hours = Column(Numeric(4, 2), default=0, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)

    # Unique constraint: one task entry per user per day
    __table_args__ = (
        UniqueConstraint('user_id', 'work_date', name='uq_user_work_date'),
    )

    # Relationships
    user = relationship("User", back_populates="task_entries", foreign_keys=[user_id])
    client = relationship("Client", back_populates="task_entries")
    sub_entries = relationship("TaskSubEntry", back_populates="task_entry", cascade="all, delete-orphan")
    approver = relationship("User", foreign_keys=[approved_by])


class TaskSubEntry(Base):
    __tablename__ = "task_sub_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_entry_id = Column(String(36), ForeignKey("task_entries.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=True)  # Nullable for leave tasks
    task_master_id = Column(String(36), ForeignKey("task_masters.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    hours = Column(Numeric(4, 2), nullable=False)
    productive = Column(Boolean, default=True, nullable=False)
    production = Column(Numeric(10, 2), default=0.0, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    task_entry = relationship("TaskEntry", back_populates="sub_entries")
    client = relationship("Client")  # NEW: Direct relationship to client
    task_master = relationship("TaskMaster")
