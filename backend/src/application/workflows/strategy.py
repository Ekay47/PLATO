from typing import Protocol

from src.application.workflows.contracts import WorkflowOrchestratorContext, WorkflowRunContext
from src.application.workflows.activity_flow import run_activity_flow
from src.application.workflows.non_activity_flow import run_non_activity_flow


class WorkflowStrategy(Protocol):
    def supports(self, diagram_type: str) -> bool:
        ...

    async def run(
        self,
        orchestrator: WorkflowOrchestratorContext,
        ctx: WorkflowRunContext,
    ) -> None:
        ...


class ActivityWorkflowStrategy:
    def supports(self, diagram_type: str) -> bool:
        return (diagram_type or "activity").lower() == "activity"

    async def run(
        self,
        orchestrator: WorkflowOrchestratorContext,
        ctx: WorkflowRunContext,
    ) -> None:
        await run_activity_flow(orchestrator, ctx)


class NonActivityWorkflowStrategy:
    def supports(self, diagram_type: str) -> bool:
        return (diagram_type or "activity").lower() != "activity"

    async def run(
        self,
        orchestrator: WorkflowOrchestratorContext,
        ctx: WorkflowRunContext,
    ) -> None:
        await run_non_activity_flow(orchestrator, ctx)
