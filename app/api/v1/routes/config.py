"""GET /v1/config public runtime configuration."""

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

router = APIRouter(tags=["config"])


@router.get("/config")
def runtime_config(settings: Settings = Depends(get_settings)) -> dict[str, list[str]]:
    return {"base_currencies": settings.base_currency}
