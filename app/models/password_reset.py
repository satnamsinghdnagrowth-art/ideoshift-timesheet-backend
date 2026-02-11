from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from datetime import datetime, timedelta
import uuid
from app.db.session import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def is_valid(self) -> bool:
        """Check if token is still valid"""
        return not self.used and datetime.utcnow() < self.expires_at

    @staticmethod
    def create_token(user_id: str, expire_minutes: int = 60) -> str:
        """Generate a secure token"""
        return str(uuid.uuid4())
