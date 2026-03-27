from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Protocol

from src.domain.run.models import RunState


class WorkflowOrchestratorContext(Protocol):
    lato: Any
    generator: Any

    def _step_emitter(self, run_id: str, step: str) -> Callable[[str], Awaitable[None]]:
        ...

    async def _run_with_heartbeat(self, run_id: str, step: str, awaitable: Awaitable[Any]) -> Any:
        ...

    async def _start_step(self, run_id: str, step: str, step_started_at: Dict[str, float], *, set_status: bool) -> None:
        ...

    async def _finish_step(
        self,
        run_id: str,
        step: str,
        step_started_at: Dict[str, float],
        run_started: float,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        ...

    async def _publish_artifact(self, run_id: str, step: str, key: str, value: Any) -> None:
        ...

    async def _publish_token_usage(self, run_id: str, step: str, token_usage_token: Optional[object]) -> None:
        ...


@dataclass
class WorkflowRunContext:
    run: RunState
    run_id: str
    run_started: float
    step_started_at: Dict[str, float]
    token_usage_token: Optional[object]
