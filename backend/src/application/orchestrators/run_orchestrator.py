import asyncio
import os
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from src.application.workflows import ActivityWorkflowStrategy, NonActivityWorkflowStrategy, WorkflowStrategy
from src.application.workflows.contracts import WorkflowRunContext
from src.core.errors import classify_error, to_error_payload
from src.core.lato_workflow import LATOWorkflow
from src.core.llm_client import start_token_usage, stop_token_usage
from src.core.modeling import BehaviorModelGenerator
from src.core.nlp_optional import coref_info_for_prompt, validate_nlp_runtime
from src.core.plantuml_validator import PlantUMLJarConfig, validate_with_jar
from src.domain.run.models import RunEvent
from src.infrastructure.store.run_store import RunStore


class RunOrchestrator:
    def __init__(self, *, run_store: RunStore, generator: BehaviorModelGenerator, lato: LATOWorkflow, logger: Any) -> None:
        self.run_store = run_store
        self.generator = generator
        self.lato = lato
        self.logger = logger
        self.workflow_strategies: List[WorkflowStrategy] = [
            ActivityWorkflowStrategy(),
            NonActivityWorkflowStrategy(),
        ]

    def _select_strategy(self, diagram_type: str) -> Optional[WorkflowStrategy]:
        return next((x for x in self.workflow_strategies if x.supports(diagram_type)), None)

    async def _emit(
        self,
        run_id: str,
        type: str,
        step: Optional[str] = None,
        status: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self.run_store.publish(
            run_id,
            RunEvent(
                run_id=run_id,
                ts_ms=int(time.time() * 1000),
                type=type,
                step=step,
                status=status,
                payload=payload,
            ),
        )

    async def _heartbeat(self, run_id: str, step: str, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await self._emit(run_id, type="step.progress", step=step, status="active", payload={"message": "Waiting for LLM response..."})
            try:
                await asyncio.wait_for(stop.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    def _step_emitter(self, run_id: str, step: str) -> Callable[[str], Awaitable[None]]:
        async def emit(msg: str) -> None:
            await self._emit(run_id, type="step.progress", step=step, status="active", payload={"message": msg})

        return emit

    async def _run_with_heartbeat(self, run_id: str, step: str, awaitable: Awaitable[Any]) -> Any:
        hb_stop = asyncio.Event()
        hb_task = asyncio.create_task(self._heartbeat(run_id, step, hb_stop))
        try:
            return await awaitable
        finally:
            hb_stop.set()
            await hb_task

    async def _start_step(self, run_id: str, step: str, step_started_at: Dict[str, float], *, set_status: bool) -> None:
        step_started_at[step] = time.perf_counter()
        if set_status:
            await self.run_store.set_status(run_id, status="running", current_step=step)
        await self._emit(run_id, type="step.started", step=step, status="active")
        self.logger.info("step.started run_id=%s step=%s", run_id, step)

    async def _finish_step(
        self,
        run_id: str,
        step: str,
        step_started_at: Dict[str, float],
        run_started: float,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._emit(run_id, type="step.completed", step=step, status="completed", payload=payload)
        self.logger.info(
            "step.completed run_id=%s step=%s status=completed ms=%d",
            run_id,
            step,
            int((time.perf_counter() - step_started_at.get(step, run_started)) * 1000),
        )

    async def _publish_artifact(self, run_id: str, step: str, key: str, value: Any) -> None:
        await self.run_store.set_artifact(run_id, key, value)
        await self._emit(run_id, type="artifact.created", step=step, status="completed", payload={"key": key, "value": value})

    async def _publish_token_usage(self, run_id: str, step: str, token_usage_token: Optional[object]) -> None:
        usage = stop_token_usage(token_usage_token) if token_usage_token is not None else None
        usage = usage or {"message": "Token usage unavailable from provider."}
        await self._publish_artifact(run_id, step, "token_usage", usage)

    async def _preflight_runtime_dependencies(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        nlp_cfg = self.lato.nlp_cfg
        await validate_nlp_runtime(cfg=nlp_cfg)
        result["corenlp"] = "ok" if nlp_cfg.dependency_provider == "corenlp" else "disabled"
        if nlp_cfg.coref_provider == "fastcoref":
            try:
                await coref_info_for_prompt("runtime dependency check", cfg=nlp_cfg)
            except Exception as e:
                raise RuntimeError(f"fastcoref dependency unavailable: {e}") from e
            result["coref"] = "ok"
        else:
            result["coref"] = "disabled"

        jar_cfg = PlantUMLJarConfig.from_env()
        if not jar_cfg.jar_path:
            raise RuntimeError("plantuml dependency unavailable: plantuml jar path is empty")
        if not os.path.exists(jar_cfg.jar_path):
            raise RuntimeError(f"plantuml dependency unavailable: jar not found at {jar_cfg.jar_path}")
        syntax_errors = validate_with_jar("@startuml\nAlice -> Bob: ping\n@enduml", cfg=jar_cfg)
        if syntax_errors is None:
            raise RuntimeError("plantuml dependency unavailable: unable to execute syntax check")
        if syntax_errors:
            raise RuntimeError(f"plantuml dependency unavailable: {'; '.join(syntax_errors[:2])}")
        result["plantuml"] = "ok"
        return result

    async def run(self, run_id: str) -> None:
        run = await self.run_store.get(run_id)
        if run is None:
            return

        run_started = time.perf_counter()
        step_started_at: Dict[str, float] = {}
        current_step: Optional[str] = None
        token_usage_token: Optional[object] = start_token_usage()

        await self.run_store.set_status(run_id, status="running", current_step="workflow_initialization")
        await self._emit(run_id, type="run.started", status="running")
        self.logger.info("run.started run_id=%s diagram_type=%s", run_id, run.diagram_type)

        try:
            step = "workflow_initialization"
            await self._start_step(run_id, step, step_started_at, set_status=False)
            preflight = await self._run_with_heartbeat(run_id, step, self._preflight_runtime_dependencies())
            await self._finish_step(run_id, step, step_started_at, run_started, payload=preflight)
            strategy = self._select_strategy(run.diagram_type)
            if strategy is None:
                raise ValueError(f"No workflow strategy for diagram_type={run.diagram_type}")
            ctx = WorkflowRunContext(
                run=run,
                run_id=run_id,
                run_started=run_started,
                step_started_at=step_started_at,
                token_usage_token=token_usage_token,
            )
            await strategy.run(self, ctx)

            token_usage_token = None
            await self.run_store.set_status(run_id, status="completed", current_step=None)
            await self._emit(run_id, type="run.completed", status="completed", payload={"artifacts": run.artifacts})
            self.logger.info("run.completed run_id=%s status=completed ms=%d", run_id, int((time.perf_counter() - run_started) * 1000))
        except Exception as e:
            if token_usage_token is not None:
                try:
                    stop_token_usage(token_usage_token)
                except Exception:
                    pass
            err = classify_error(e)
            if step_started_at:
                current_step = max(step_started_at, key=step_started_at.get)
            await self.run_store.set_error(run_id, f"[{err.code}] {err.user_message}")
            await self._emit(run_id, type="run.failed", status="failed", payload=to_error_payload(e))
            self.logger.exception("run.failed run_id=%s step=%s code=%s detail=%s", run_id, current_step, err.code, err.detail)
