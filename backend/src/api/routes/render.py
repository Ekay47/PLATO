from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from src.api.deps import ApiDeps
from src.api.schemas.render import PlantUMLRenderRequest


def build_render_router(deps: ApiDeps):
    router = APIRouter()

    @router.post("/plantuml/png")
    async def plantuml_png(request: PlantUMLRenderRequest):
        code = (request.code or "").strip()
        if not code:
            raise HTTPException(status_code=400, detail="PlantUML code is empty")
        if len(code) > 200_000:
            raise HTTPException(status_code=413, detail="PlantUML code too large")
        timeout_s = deps.settings.get_float("plantuml.render_timeout_s", 10.0)
        if request.timeout_s is not None:
            timeout_s = float(request.timeout_s)
        if timeout_s < 0.5:
            timeout_s = 0.5
        if timeout_s > 30:
            timeout_s = 30
        try:
            png = deps.render_png_with_jar(code, timeout_s=timeout_s)
        except deps.PlantUMLRenderTimeout:
            raise HTTPException(status_code=504, detail=f"PlantUML render timeout ({timeout_s}s)")
        if not png:
            raise HTTPException(status_code=500, detail="Failed to render PNG with PlantUML jar")
        return Response(content=png, media_type="image/png")

    return router
