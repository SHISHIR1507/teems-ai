from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..dependencies import get_auth0_client, get_current_user, require_roles
from ..schemas.auth import (
    AuthConfigResponse,
    AuthenticatedUser,
    LogoutRequest,
    LogoutResponse,
)
from ..services.auth0 import Auth0Client

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfigResponse, summary="Public Auth0 config")
async def get_auth_config(settings: Settings = Depends(get_settings)) -> AuthConfigResponse:
    return AuthConfigResponse(
        domain=settings.auth0_domain,
        audience=settings.auth0_audience,
        client_id=settings.auth0_client_id,
    )


@router.get(
    "/me",
    response_model=AuthenticatedUser,
    summary="Return profile derived from the access token",
)
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    return current_user


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Return a logout URL that clears the Auth0 session",
)
async def logout(
    payload: LogoutRequest,
    client: Auth0Client = Depends(get_auth0_client),
) -> LogoutResponse:
    logout_url = client.build_logout_url(payload.return_to)
    return LogoutResponse(logout_url=logout_url)

@router.get("/admin-only", summary="Admin-only test route")
async def admin_only(
    user: AuthenticatedUser = Depends(require_roles(["admin"]))
):
    return {"message": "You are an admin!", "user": user}

