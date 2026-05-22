from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.responses import JSONResponse

from auth.auth_bearer import get_authenticated_user_data
from crud.subscription_crud import SubscriptionCRUD
from schemas.user import EmailPreferenceRequest, EmailPreferenceRequestPublic
from service.email_hash_service import hash_email
from service.keycloak_userinfo_service import KeycloakUserInfoService
from service.user_service import UserService
from utils.base_config import logger

router = APIRouter(prefix="/users", tags=["users"])


def get_verified_userinfo(
    user_data: dict, userinfo_service: KeycloakUserInfoService
) -> dict:
    userinfo = userinfo_service.get_userinfo(user_data["access_token"])
    if userinfo["sub"] != user_data["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token is not valid",
        )
    return userinfo


def get_user_email_hash(userinfo: dict) -> str:
    email = userinfo.get("email")
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email is not available",
        )
    return hash_email(email)


@router.get("/", response_class=JSONResponse)
async def get_user(
    user_data: Annotated[dict, Depends(get_authenticated_user_data)],
    user_service: Annotated[UserService, Depends()],
    userinfo_service: Annotated[KeycloakUserInfoService, Depends()],
):
    userinfo = get_verified_userinfo(user_data, userinfo_service)
    user_details = user_service.get_user_profile(userinfo)
    return user_details


@router.post("/email_preferences/subscribe", response_class=JSONResponse)
async def subscribe_email_preference(
    user_data: Annotated[dict, Depends(get_authenticated_user_data)],
    subscription_crud: Annotated[SubscriptionCRUD, Depends()],
    userinfo_service: Annotated[KeycloakUserInfoService, Depends()],
    payload: EmailPreferenceRequest,
):
    userinfo = get_verified_userinfo(user_data, userinfo_service)
    subscription_crud.subscribe_email_preferences(
        user_data["sub"], payload.name, get_user_email_hash(userinfo)
    )
    logger.info(f"User (id = {user_data['sub']}) is subscribed to email preferences")

    return JSONResponse(status_code=200, content={"message": "Subscribed to email preferences"})


@router.post("/email_preferences/unsubscribe", response_class=JSONResponse)
async def unsubscribe_email_preference(
    user_data: Annotated[dict, Depends(get_authenticated_user_data)],
    subscription_crud: Annotated[SubscriptionCRUD, Depends()],
    payload: EmailPreferenceRequest,
):
    subscription_crud.unsubscribe_email_preferences(user_data["sub"], payload.name)
    logger.info(f"User (id = {user_data['sub']}) is unsubscribed from email preferences")

    return JSONResponse(status_code=200, content={"message": "Unsubscribed from email preferences"})


@router.post("/public/email_preferences/unsubscribe/", response_class=JSONResponse)
async def public_unsubscribe_email_preference(
    subscription_crud: Annotated[SubscriptionCRUD, Depends()],
    payload: EmailPreferenceRequestPublic,
):
    subscription_crud.unsubscribe_email_preferences_by_email_hash(
        hash_email(str(payload.email)), payload.name
    )
    logger.info("User unsubscribed from email preferences by email hash")

    return JSONResponse(status_code=200, content={"message": "Unsubscribed successfully"})
