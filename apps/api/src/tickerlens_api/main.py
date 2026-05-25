from fastapi import FastAPI

from tickerlens_api.api.routes.chunking import router as chunking_router
from tickerlens_api.api.routes.chat import router as chat_router
from tickerlens_api.api.routes.documents import router as documents_router
from tickerlens_api.api.routes.embeddings import router as embeddings_router
from tickerlens_api.api.routes.health import router as health_router
from tickerlens_api.api.routes.indexing import router as indexing_router
from tickerlens_api.api.routes.parsing import router as parsing_router
from tickerlens_api.api.routes.pipeline import router as pipeline_router
from tickerlens_api.api.routes.search import router as search_router
from tickerlens_api.api.routes.tickers import router as tickers_router
from tickerlens_api.api.routes.version import router as version_router
from tickerlens_api.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.api_title, version=settings.api_version)
    app.include_router(health_router)
    app.include_router(version_router)
    app.include_router(documents_router)
    app.include_router(parsing_router)
    app.include_router(chunking_router)
    app.include_router(indexing_router)
    app.include_router(embeddings_router)
    app.include_router(pipeline_router)
    app.include_router(search_router)
    app.include_router(tickers_router)
    app.include_router(chat_router)
    return app


app = create_app()
