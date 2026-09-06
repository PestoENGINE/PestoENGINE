"""GET /v1/config public runtime configuration."""

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.core.config import Settings

router = APIRouter(tags=["config"])


@router.get("/config")
def runtime_config(settings: Settings = Depends(get_app_settings)) -> dict[str, list[str]]:
    return {"base_currencies": settings.base_currency}
