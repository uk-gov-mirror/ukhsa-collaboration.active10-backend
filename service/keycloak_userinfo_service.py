from typing import Any

import httpx
from fastapi import HTTPException, status

from utils.base_config import config, logger


class KeycloakUserInfoService:
    def get_userinfo(self, access_token: str) -> dict[str, Any]:
        try:
            response = httpx.get(
                config.identity_broker_userinfo_uri,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
                verify=not config.debug,
            )
            response.raise_for_status()
            userinfo = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Keycloak userinfo request failed: status=%s",
                exc.response.status_code,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to fetch user info",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Keycloak userinfo request failed: %s", str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to fetch user info",
            ) from exc

        subject = userinfo.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            logger.warning("Keycloak userinfo response missing subject")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unable to fetch user info",
            )

        return userinfo
