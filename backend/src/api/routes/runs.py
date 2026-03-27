import asyncio
import json
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from src.api.deps import ApiDeps
from src.api.schemas.runs import RunCreateRequest


def build_runs_router(deps: ApiDeps):
    router = APIRouter()

    @router.post("/runs")
    async def create_run(request: RunCreateRequest):
        if not request.requirement_text:
            raise HTTPException(status_code=400, detail="Requirement text is empty")
        run = await deps.run_store.create(request.requirement_text, request.diagram_type)
        asyncio.create_task(deps.run_worker(run.run_id))
        deps.logger.info("run.created run_id=%s diagram_type=%s", run.run_id, run.diagram_type)
        return {"run_id": run.run_id, "status": run.status, "diagram_type": run.diagram_type}

    @router.get("/runs/{run_id}")
    async def get_run(run_id: str):
        run = await deps.run_store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run.snapshot()

    @router.get("/runs/{run_id}/events")
    async def run_events(run_id: str, request: Request):
        run = await deps.run_store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        q = await deps.run_store.subscribe(run_id)
        if q is None:
            raise HTTPException(status_code=404, detail="Run not found")

        initial = [{"run_id": run_id, "ts_ms": int(time.time() * 1000), "type": "run.snapshot", "payload": run.snapshot()}]
        initial.extend(list(run.events))

        async def gen():
            try:
                for ev in initial:
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        ev = await asyncio.wait_for(q.get(), timeout=1.0)
                        yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield "event: ping\ndata: {}\n\n"
            finally:
                await deps.run_store.unsubscribe(run_id, q)

        return StreamingResponse(gen(), media_type="text/event-stream")

    return router
