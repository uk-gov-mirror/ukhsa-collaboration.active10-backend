from datetime import datetime
from uuid import uuid4

from sqlalchemy import UUID, Boolean, Column, DateTime, String

from db.session import Base


class EmailPreference(Base):
    __tablename__ = "email_preferences"

    id = Column(UUID(as_uuid=True), default=uuid4, primary_key=True)
    user_id = Column(String(length=255), nullable=False, index=True)
    email_hash = Column(String(length=64), nullable=True, index=True)
    name = Column(String(length=200), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
