from src.application.workflows.contracts import WorkflowOrchestratorContext, WorkflowRunContext


async def run_activity_flow(orchestrator: WorkflowOrchestratorContext, ctx: WorkflowRunContext) -> None:
    run = ctx.run
    run_id = ctx.run_id
    run_started = ctx.run_started
    step_started_at = ctx.step_started_at
    token_usage_token = ctx.token_usage_token
    step = "activity_identification"
    await orchestrator._start_step(run_id, step, step_started_at, set_status=False)
    activities = await orchestrator._run_with_heartbeat(
        run_id,
        step,
        orchestrator.lato.identify(run.requirement_text, emit=orchestrator._step_emitter(run_id, step)),
    )
    await orchestrator._publish_artifact(run_id, step, "identification", activities)
    await orchestrator._finish_step(run_id, step, step_started_at, run_started, payload={"count": len(activities)})

    step = "structure_decomposition"
    await orchestrator._start_step(run_id, step, step_started_at, set_status=True)
    decomposition = await orchestrator.lato.decompose(run.requirement_text, activities=activities, emit=orchestrator._step_emitter(run_id, step))
    await orchestrator._publish_artifact(run_id, step, "decomposition", decomposition)
    await orchestrator._finish_step(run_id, step, step_started_at, run_started)

    step = "information_integration"
    await orchestrator._start_step(run_id, step, step_started_at, set_status=True)
    integration = await orchestrator.lato.reconstruct(
        run.requirement_text,
        activities=activities,
        decomposition=decomposition,
        emit=orchestrator._step_emitter(run_id, step),
    )
    await orchestrator._publish_artifact(run_id, step, "integration", integration)
    await orchestrator._finish_step(run_id, step, step_started_at, run_started)

    step = "plantuml_generation"
    await orchestrator._start_step(run_id, step, step_started_at, set_status=True)
    plantuml = await orchestrator._run_with_heartbeat(
        run_id,
        step,
        orchestrator.lato.generate(run.requirement_text, integration=integration, emit=orchestrator._step_emitter(run_id, step)),
    )
    await orchestrator._publish_artifact(run_id, step, "plantuml", plantuml)
    await orchestrator._publish_token_usage(run_id, step, token_usage_token)
    await orchestrator._finish_step(run_id, step, step_started_at, run_started)
