import uuid

from sqlalchemy import ARRAY, JSON, UUID, BigInteger, Column, String

from db.session import Base


class UserMotivation(Base):
    __tablename__ = "user_motivations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goals = Column(ARRAY(JSON), nullable=False)
    user_id = Column(String(length=255), nullable=False, index=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
