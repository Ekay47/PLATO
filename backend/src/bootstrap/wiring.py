import logging
from dataclasses import dataclass
from typing import Any

from src.api.deps import ApiDeps
from src.application.orchestrators.run_orchestrator import RunOrchestrator
from src.core.corenlp_service import ManagedCoreNLP, check_alive as corenlp_check_alive
from src.core.errors import to_error_payload
from src.core.lato_workflow import LATOWorkflow
from src.core.modeling import BehaviorModelGenerator
from src.core.plantuml_validator import PlantUMLRenderTimeout, render_png_with_jar
from src.infrastructure.store.run_store import RunStore


@dataclass(frozen=True)
class AppContainer:
    generator: BehaviorModelGenerator
    lato: LATOWorkflow
    run_store: RunStore
    corenlp: ManagedCoreNLP
    run_orchestrator: RunOrchestrator
    api_deps: ApiDeps


def setup_logger(settings) -> logging.Logger:
    logger = logging.getLogger("plato")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    logger.setLevel(settings.get_str("server.log_level", "INFO").upper())
    return logger


def build_container(*, settings, logger: logging.Logger) -> AppContainer:
    generator = BehaviorModelGenerator()
    lato = LATOWorkflow()
    run_store = RunStore()
    corenlp = ManagedCoreNLP()
    run_orchestrator = RunOrchestrator(run_store=run_store, generator=generator, lato=lato, logger=logger)
    logger.info("llm.config mock=%s api_url=%s model=%s", getattr(lato.llm, "mock", None), getattr(lato.llm, "api_url", None), getattr(lato.llm, "model", None))

    async def run_worker(run_id: str) -> None:
        await run_orchestrator.run(run_id)

    api_deps = ApiDeps(
        settings=settings,
        corenlp=corenlp,
        corenlp_check_alive=corenlp_check_alive,
        run_store=run_store,
        run_worker=run_worker,
        lato=lato,
        generator=generator,
        to_error_payload=to_error_payload,
        render_png_with_jar=render_png_with_jar,
        PlantUMLRenderTimeout=PlantUMLRenderTimeout,
        logger=logger,
    )
    return AppContainer(
        generator=generator,
        lato=lato,
        run_store=run_store,
        corenlp=corenlp,
        run_orchestrator=run_orchestrator,
        api_deps=api_deps,
    )
