import asyncio
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.deps import ApiDeps
from src.api.routes.runs import build_runs_router
from src.domain.run.models import RunEvent
from src.infrastructure.store.run_store import RunStore


class _NoopLogger:
    def info(self, *_args, **_kwargs):
        return None

    def exception(self, *_args, **_kwargs):
        return None


async def _noop_worker(_run_id: str) -> None:
    return None


class RunsRouterContractTests(unittest.TestCase):
    def setUp(self):
        self.store = RunStore()
        self.app = FastAPI()
        deps = ApiDeps(
            settings=None,
            corenlp=None,
            corenlp_check_alive=lambda **_k: None,
            run_store=self.store,
            run_worker=_noop_worker,
            lato=None,
            generator=None,
            to_error_payload=lambda _e: {},
            render_png_with_jar=lambda *_a, **_k: b"",
            PlantUMLRenderTimeout=Exception,
            logger=_NoopLogger(),
        )
        self.app.include_router(build_runs_router(deps))
        self.client = TestClient(self.app)

    def test_create_run_and_get_run_contract(self):
        res = self.client.post("/runs", json={"requirement_text": "r", "diagram_type": "activity"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("run_id", body)
        self.assertEqual(body["status"], "pending")

        run = self.client.get(f"/runs/{body['run_id']}")
        self.assertEqual(run.status_code, 200)
        snap = run.json()
        self.assertEqual(snap["run_id"], body["run_id"])
        self.assertEqual(snap["diagram_type"], "activity")

    def test_sse_endpoint_contract(self):
        run = asyncio.run(self.store.create("r", "activity"))
        asyncio.run(
            self.store.publish(
                run.run_id,
                RunEvent(run_id=run.run_id, ts_ms=1, type="step.started", step="activity_identification", status="active"),
            )
        )
        event_paths = [route.path for route in self.app.routes]
        self.assertIn("/runs/{run_id}/events", event_paths)
        self.assertEqual(run.events[0]["type"], "step.started")


if __name__ == "__main__":
    unittest.main()
