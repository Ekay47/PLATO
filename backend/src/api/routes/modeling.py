from fastapi import APIRouter, HTTPException
from src.api.deps import ApiDeps
from src.api.schemas.modeling import ModelingRequest


def build_modeling_router(deps: ApiDeps):
    router = APIRouter()

    @router.post("/generate-model")
    async def generate_model(request: ModelingRequest):
        try:
            if not request.requirement_text:
                raise HTTPException(status_code=400, detail="Requirement text is empty")

            if (request.diagram_type or "activity").lower() == "activity":
                res = await deps.lato.run(request.requirement_text)
                return {
                    "identification": res.activities,
                    "decomposition": res.decomposition,
                    "integration": res.integration,
                    "plantuml": res.plantuml,
                    "activities": res.activities,
                }

            result = await deps.generator.generate_model(request.requirement_text, request.diagram_type)
            return result
        except Exception as e:
            payload = deps.to_error_payload(e)
            deps.logger.exception("generate_model.failed code=%s detail=%s", payload.get("error_code"), payload.get("detail"))
            raise HTTPException(status_code=500, detail=payload)

    return router
