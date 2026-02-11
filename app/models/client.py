from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.db.session import Base


class ClientStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BACKLOG = "BACKLOG"
    DEMO = "DEMO"


class Client(Base):
    __tablename__ = "clients"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True)
    contact_name = Column(String(255), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(100), nullable=True)
    address = Column(String(500), nullable=True)
    status = Column(SQLEnum(ClientStatus), default=ClientStatus.ACTIVE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)

    # Relationships
    task_entries = relationship("TaskEntry", back_populates="client")
