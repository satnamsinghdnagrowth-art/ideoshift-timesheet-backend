from sqlalchemy import Column, String, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import uuid
from ..db.session import Base
from datetime import datetime


class TaskMaster(Base):
    __tablename__ = "task_masters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    is_profitable = Column(Boolean, default=True, nullable=False)  # New field
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(36), ForeignKey("users.id"))
    updated_by = Column(String(36), ForeignKey("users.id"))

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
