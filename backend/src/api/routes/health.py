from fastapi import APIRouter
from src.api.deps import ApiDeps


def build_health_router(deps: ApiDeps):
    router = APIRouter()

    @router.get("/")
    async def root():
        return {"message": "P-LATO API is running"}

    @router.get("/health")
    async def health():
        version = deps.settings.get_str("server.version", "v2.4.0").strip()
        corenlp_mode = getattr(deps.corenlp, "cfg", None).mode if getattr(deps.corenlp, "cfg", None) else "unknown"
        if corenlp_mode == "off":
            corenlp_status = "disabled"
        else:
            corenlp_ok = await deps.corenlp_check_alive(
                getattr(deps.corenlp, "cfg", None).url if getattr(deps.corenlp, "cfg", None) else "http://127.0.0.1:9000",
                timeout_s=0.8,
            )
            corenlp_status = "online" if corenlp_ok else "offline"
        return {
            "status": "online",
            "version": version,
            "services": {
                "corenlp": corenlp_status,
                "corenlp_mode": corenlp_mode,
            },
        }

    return router
