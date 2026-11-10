from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import liquidity, platform
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    settings.check_production_safety()
    app = FastAPI(title="SD Treasury API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["ops"])
    def health():
        return {"status": "ok", "env": settings.env}

    app.include_router(platform.router, prefix="/api/v1")
    app.include_router(liquidity.router, prefix="/api/v1")
    return app


app = create_app()
