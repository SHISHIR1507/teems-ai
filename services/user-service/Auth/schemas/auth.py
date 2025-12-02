from datetime import datetime

from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    sub: str = Field(..., description="Auth0 subject identifier")
    email: str | None = None
    name: str | None = None
    permissions: list[str] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)     # roles
    tenant_id: str | None = Field(None, description="User's tenant identifier")    #tenant_id

    expires_at: datetime


class AuthConfigResponse(BaseModel):
    domain: str
    audience: str
    client_id: str


class LogoutRequest(BaseModel):
    return_to: str | None = Field(
        default=None, description="URL to redirect users to after Auth0 logout"
    )


class LogoutResponse(BaseModel):
    logout_url: str

