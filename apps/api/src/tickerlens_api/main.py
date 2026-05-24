from fastapi import FastAPI

from tickerlens_api.api.routes.documents import router as documents_router
from tickerlens_api.api.routes.health import router as health_router
from tickerlens_api.api.routes.parsing import router as parsing_router
from tickerlens_api.api.routes.version import router as version_router
from tickerlens_api.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.api_title, version=settings.api_version)
    app.include_router(health_router)
    app.include_router(version_router)
    app.include_router(documents_router)
    app.include_router(parsing_router)
    return app


app = create_app()
