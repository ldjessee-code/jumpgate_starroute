"""RFC 7807 problem+json for the v1 sub-app only."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class Problem(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        detail: str,
        *,
        instance: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.instance = instance
        self.extra = extra or {}


def problem_json(
    *,
    status: int,
    code: str,
    detail: str,
    instance: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://jumpgate.local/problems/{code}",
        "title": code,
        "status": status,
        "detail": detail,
        "code": code,
    }
    if instance:
        body["instance"] = instance
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


async def problem_handler(_request: Request, exc: Problem) -> JSONResponse:
    return problem_json(
        status=exc.status,
        code=exc.code,
        detail=exc.detail,
        instance=exc.instance,
        extra=exc.extra,
    )


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return problem_json(
        status=400,
        code="validation_error",
        detail="Request failed validation",
        instance=str(request.url.path),
        extra={"errors": exc.errors()},
    )
