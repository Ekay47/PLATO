from dataclasses import dataclass
from typing import Type

from src.api.types import (
    AppLoggerProtocol,
    CoreNLPHealthCheckFn,
    CoreNLPServiceProtocol,
    ErrorPayloadFn,
    LatoWorkflowProtocol,
    ModelGeneratorProtocol,
    RenderPngFn,
    RunStoreProtocol,
    RunWorkerFn,
    SettingsProtocol,
)


@dataclass(frozen=True)
class ApiDeps:
    settings: SettingsProtocol
    corenlp: CoreNLPServiceProtocol
    corenlp_check_alive: CoreNLPHealthCheckFn
    run_store: RunStoreProtocol
    run_worker: RunWorkerFn
    lato: LatoWorkflowProtocol
    generator: ModelGeneratorProtocol
    to_error_payload: ErrorPayloadFn
    render_png_with_jar: RenderPngFn
    PlantUMLRenderTimeout: Type[Exception]
    logger: AppLoggerProtocol
