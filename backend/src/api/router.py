from src.api.routes.health import build_health_router
from src.api.routes.modeling import build_modeling_router
from src.api.routes.render import build_render_router
from src.api.routes.runs import build_runs_router


def include_all_routes(app, deps) -> None:
    app.include_router(build_health_router(deps))
    app.include_router(build_runs_router(deps))
    app.include_router(build_modeling_router(deps))
    app.include_router(build_render_router(deps))
