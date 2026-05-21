import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWKClientError

from utils.base_config import config, logger

ACCEPTED_JWT_ALGORITHM = "RS256"
IDENTITY_BROKER_JWKS_URI = config.identity_broker_jwks_uri
IDENTITY_BROKER_ISSUER = config.identity_broker_issuer
REQUIRED_API_AUDIENCE = config.api_jwt_audience
IDENTITY_BROKER_JWKS_HEADERS = {"User-Agent": "active10-backend"}
REQUIRED_REGISTERED_CLAIMS = ("exp", "iss", "aud", "sub")

identity_broker_jwks_client = PyJWKClient(
    IDENTITY_BROKER_JWKS_URI,
    headers=IDENTITY_BROKER_JWKS_HEADERS,
)


def _invalid_token_exception(detail: str = "Token is not valid") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _validate_required_claims(payload: dict) -> None:
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        logger.warning("JWT rejected: missing subject claim")
        raise _invalid_token_exception()


def decode_jwt(token: str) -> dict:
    """
    Decode a JWT token.

    Args:
        token (str): The JSON Web Token (JWT) string to decode.

    Returns:
        dict: The decoded JWT payload as a dictionary.

    Raises:
        HTTPException: If the token is expired, invalid, or an error occurs during decoding.
    """
    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
    except InvalidTokenError as exc:
        logger.warning("JWT rejected: invalid token header")
        raise _invalid_token_exception() from exc

    if algorithm != ACCEPTED_JWT_ALGORITHM:
        logger.warning("JWT rejected: unsupported algorithm %s", algorithm)
        raise _invalid_token_exception()

    try:
        signing_key = identity_broker_jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            issuer=IDENTITY_BROKER_ISSUER,
            audience=REQUIRED_API_AUDIENCE,
            algorithms=[ACCEPTED_JWT_ALGORITHM],
            options={"require": REQUIRED_REGISTERED_CLAIMS},
        )
        _validate_required_claims(payload)
        return payload
    except ExpiredSignatureError as exc:
        logger.info("JWT rejected: token expired")
        raise _invalid_token_exception("Token has expired") from exc
    except (InvalidTokenError, PyJWKClientError) as exc:
        logger.warning("JWT rejected: invalid token")
        raise _invalid_token_exception() from exc
