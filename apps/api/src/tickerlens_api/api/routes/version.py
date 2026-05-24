from fastapi import APIRouter

from tickerlens_api.settings import settings

router = APIRouter(tags=["system"])


@router.get("/version")
def version() -> dict:
    return {"name": settings.api_title, "version": settings.api_version, "environment": settings.environment}

