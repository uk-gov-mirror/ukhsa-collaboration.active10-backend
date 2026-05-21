from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .jwt_handler import decode_jwt

security = HTTPBearer()


def get_authenticated_user_data(
    token: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict[str, Any]:
    """
    Validate a JWT bearer token and return its decoded claims.

    Args:
        token: Authorization token extracted from request.

    Returns:
        A dict containing validated JWT claims.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    return decode_jwt(token.credentials)
