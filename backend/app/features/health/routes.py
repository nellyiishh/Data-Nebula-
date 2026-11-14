from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    status: Literal["ok"]


@router.get(
    "/health",
    summary="Liveness check",
    description="Returns ok when the API process is up. Used by the hosting platform.",
    response_model=HealthStatus,
)
def health() -> HealthStatus:
    return HealthStatus(status="ok")
