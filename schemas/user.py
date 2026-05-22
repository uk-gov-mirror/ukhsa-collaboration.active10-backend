from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from schemas.activity_level import ActivityLevelResponseSchema
from schemas.motivation import UserMotivationResponse


class EmailPreferenceRequest(BaseModel):
    name: str = Field(..., examples=["active10_mailing_list"])

    @field_validator("name")
    def validate_name(cls, name: str) -> str:
        if name != "active10_mailing_list":
            raise ValueError("Invalid name")

        return name


class EmailPreferenceRequestPublic(EmailPreferenceRequest):
    email: EmailStr


class EmailPreferenceResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool


class UserResponse(BaseModel):
    id: str
    first_name: str
    email: str
    age: int
    age_range: str
    identity_level: str | None
    email_preferences: list[EmailPreferenceResponse] | None = []
    latest_motivation: UserMotivationResponse | None = None
    latest_activity_level: ActivityLevelResponseSchema | None = None
