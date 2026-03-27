from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import include_all_routes
from src.bootstrap.lifecycle import build_lifespan
from src.bootstrap.wiring import build_container, setup_logger
from src.core.settings_loader import settings


def create_app() -> FastAPI:
    logger = setup_logger(settings)
    container = build_container(settings=settings, logger=logger)
    app = FastAPI(title="P-LATO Backend API", lifespan=build_lifespan(settings=settings, corenlp=container.corenlp))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.container = container
    include_all_routes(app, container.api_deps)
    return app
