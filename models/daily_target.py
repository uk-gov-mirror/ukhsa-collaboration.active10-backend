from uuid import uuid4

from sqlalchemy import UUID, Column, Integer, String

from db.session import Base


class UserDailyTarget(Base):
    __tablename__ = "user_daily_target"

    id = Column(UUID(as_uuid=True), default=uuid4, primary_key=True, index=True)
    date = Column(Integer, nullable=True)
    daily_target = Column(Integer, nullable=False)
    user_id = Column(String(length=255), nullable=False, index=True)
