from datetime import date, datetime
from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from db.session import get_db_session
from models import EmailPreference
from models.activity_level import UserActivityLevel
from models.motivation import UserMotivation
from schemas.activity_level import ActivityLevelResponseSchema
from schemas.motivation import UserMotivationResponse
from schemas.user import EmailPreferenceResponse, UserResponse


class UserService:
    def __init__(self, db: Session = Depends(get_db_session)) -> None:  # noqa: B008
        self.db = db

    def get_user_profile(self, userinfo: dict[str, Any]) -> UserResponse:
        user_sub = userinfo["sub"]
        birthdate = self.__parse_birthdate(userinfo.get("birthdate"))
        age_range = self.__get_age_range(birthdate) if birthdate else "Out of range"
        anony_email = self.__anonymize_email(userinfo.get("email", ""))
        age = self.calculate_age(birthdate) if birthdate else 0
        latest_motivation = None
        latest = (
            self.db.query(UserMotivation)
            .filter(UserMotivation.user_id == user_sub)
            .order_by(UserMotivation.created_at.desc())
            .first()
        )
        if latest:
            latest_motivation = UserMotivationResponse(
                id=latest.id,
                user_id=latest.user_id,
                created_at=latest.created_at,
                goals=latest.goals,
            )
        activity_level = None
        latest_activity_level = (
            self.db.query(UserActivityLevel)
            .filter(UserActivityLevel.user_id == user_sub)
            .order_by(UserActivityLevel.created_at.desc())
            .first()
        )
        if latest_activity_level:
            activity_level = ActivityLevelResponseSchema(
                id=latest_activity_level.id,
                level=latest_activity_level.level,
                created_at=latest_activity_level.created_at,
                updated_at=latest_activity_level.updated_at,
            )

        return UserResponse(
            id=user_sub,
            first_name=userinfo.get("given_name") or userinfo.get("preferred_username", ""),
            email=anony_email,
            identity_level=userinfo.get("identity_proofing_level") or userinfo.get("identity_level"),
            age_range=age_range,
            age=age,
            email_preferences=[
                EmailPreferenceResponse(
                    id=ep.id,
                    name=ep.name,
                    is_active=ep.is_active,
                )
                for ep in self.db.query(EmailPreference).filter_by(user_id=user_sub).all()
            ],
            latest_motivation=latest_motivation,
            latest_activity_level=activity_level,
        )

    def __parse_birthdate(self, birthdate: str | None) -> date | None:
        if not birthdate:
            return None
        try:
            return date.fromisoformat(birthdate)
        except ValueError:
            return None

    def __get_age_range(self, date_of_birth: date) -> str:
        today = datetime.now().date()
        age = (
            today.year
            - date_of_birth.year
            - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
        )

        age_ranges = {
            (18, 24): "18 to 24",
            (25, 34): "25 to 34",
            (35, 44): "35 to 44",
            (45, 54): "45 to 54",
            (55, 64): "55 to 64",
        }
        for age_range in age_ranges:  # noqa: PLC0206
            if age_range[0] <= age <= age_range[1]:
                return age_ranges[age_range]
        if age >= 65:  # noqa: PLR2004
            return "65 or over"
        return "Out of range"

    def __anonymize_email(self, email: str):
        visible_chars = 3
        if not email or len(email) <= visible_chars:
            return email

        local_part, domain_part = email.split("@", 1)
        return f"{local_part[:visible_chars]}...@{domain_part}"

    def calculate_age(self, date_of_birth: date) -> int:
        today = datetime.today().date()

        age = today.year - date_of_birth.year

        if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
            age -= 1

        return age
