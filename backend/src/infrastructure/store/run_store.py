import asyncio
from typing import Any, Dict, Optional

from src.domain.run.models import RunEvent, RunState, new_run_id, now_ms


class RunStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._runs: Dict[str, RunState] = {}

    async def create(self, requirement_text: str, diagram_type: str) -> RunState:
        async with self._lock:
            run_id = new_run_id()
            run = RunState(run_id=run_id, requirement_text=requirement_text, diagram_type=diagram_type)
            self._runs[run_id] = run
            return run

    async def get(self, run_id: str) -> Optional[RunState]:
        async with self._lock:
            return self._runs.get(run_id)

    async def publish(self, run_id: str, event: RunEvent) -> None:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            data = event.to_dict()
            run.events.append(data)
            run.updated_ts_ms = now_ms()
            queues = list(run.subscribers)

        for q in queues:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, run_id: str) -> Optional[asyncio.Queue]:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return None
            q: asyncio.Queue = asyncio.Queue(maxsize=200)
            run.subscribers.add(q)
            return q

    async def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            run.subscribers.discard(q)

    async def set_status(self, run_id: str, status: str, current_step: Optional[str] = None) -> None:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            run.status = status
            run.current_step = current_step
            run.updated_ts_ms = now_ms()

    async def set_artifact(self, run_id: str, key: str, value: Any) -> None:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            run.artifacts[key] = value
            run.updated_ts_ms = now_ms()

    async def set_error(self, run_id: str, error: str) -> None:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            run.error = error
            run.status = "failed"
            run.updated_ts_ms = now_ms()
