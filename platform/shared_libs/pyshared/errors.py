"""
Standardized error response schemas and helpers for all services.
"""
from typing import Optional
from fastapi import HTTPException, status
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Standardized error detail structure"""
    code: str = Field(..., description="Error code (e.g., VALIDATION_ERROR, NOT_FOUND)")
    message: str = Field(..., description="Human-readable error message")
    detail: Optional[str] = Field(None, description="Optional detailed error information")
    field: Optional[str] = Field(None, description="Field name for validation errors")


class StandardErrorResponse(BaseModel):
    """Standardized error response format"""
    error: ErrorDetail


# Error code mappings
ERROR_CODES = {
    status.HTTP_400_BAD_REQUEST: "VALIDATION_ERROR",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMIT_EXCEEDED",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
    status.HTTP_502_BAD_GATEWAY: "BAD_GATEWAY",
    status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
    status.HTTP_504_GATEWAY_TIMEOUT: "GATEWAY_TIMEOUT",
}


def raise_standard_error(
    status_code: int,
    message: str,
    detail: Optional[str] = None,
    field: Optional[str] = None
) -> None:
    """
    Raise a standardized HTTPException with consistent error format.
    
    Args:
        status_code: HTTP status code
        message: Human-readable error message
        detail: Optional detailed error information
        field: Optional field name for validation errors
    
    Raises:
        HTTPException with standardized error format
    """
    error_code = ERROR_CODES.get(status_code, "INTERNAL_ERROR")
    
    error_detail = ErrorDetail(
        code=error_code,
        message=message,
        detail=detail,
        field=field
    )
    
    raise HTTPException(
        status_code=status_code,
        detail=error_detail.model_dump()
    )


def create_error_response(
    status_code: int,
    message: str,
    detail: Optional[str] = None,
    field: Optional[str] = None
) -> dict:
    """
    Create a standardized error response dictionary (for use in responses).
    
    Args:
        status_code: HTTP status code
        message: Human-readable error message
        detail: Optional detailed error information
        field: Optional field name for validation errors
    
    Returns:
        Dictionary with standardized error format
    """
    error_code = ERROR_CODES.get(status_code, "INTERNAL_ERROR")
    
    return {
        "error": {
            "code": error_code,
            "message": message,
            "detail": detail,
            "field": field
        }
    }
