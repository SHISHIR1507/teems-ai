from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings
from .schemas.auth import AuthenticatedUser
from .services.auth0 import Auth0Client

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth0_client(settings: Settings = Depends(get_settings)) -> Auth0Client:
    return Auth0Client(settings=settings)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    client: Auth0Client = Depends(get_auth0_client),
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    token = credentials.credentials
    try:
        return await client.verify_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

