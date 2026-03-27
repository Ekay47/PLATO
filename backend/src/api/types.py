from typing import Any, Awaitable, Callable, Dict, Optional, Protocol


class SettingsProtocol(Protocol):
    def get_str(self, key: str, default: str = "") -> str:
        ...

    def get_bool(self, key: str, default: bool = False) -> bool:
        ...

    def get_float(self, key: str, default: float = 0.0) -> float:
        ...


class CoreNLPCfgProtocol(Protocol):
    mode: str
    url: str


class CoreNLPServiceProtocol(Protocol):
    cfg: Optional[CoreNLPCfgProtocol]

    async def ensure_started(self) -> None:
        ...

    async def shutdown(self) -> None:
        ...


class RunStateProtocol(Protocol):
    run_id: str
    status: str
    diagram_type: str
    events: list

    def snapshot(self) -> Dict[str, Any]:
        ...


class RunStoreProtocol(Protocol):
    async def create(self, requirement_text: str, diagram_type: str) -> RunStateProtocol:
        ...

    async def get(self, run_id: str) -> Optional[RunStateProtocol]:
        ...

    async def subscribe(self, run_id: str):
        ...

    async def unsubscribe(self, run_id: str, q) -> None:
        ...


class LatoWorkflowProtocol(Protocol):
    async def run(self, requirement_text: str):
        ...


class ModelGeneratorProtocol(Protocol):
    async def generate_model(self, text: str, diagram_type: str = "activity"):
        ...


class AppLoggerProtocol(Protocol):
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...


ErrorPayloadFn = Callable[[Exception], Dict[str, Any]]
CoreNLPHealthCheckFn = Callable[..., Awaitable[bool]]
RunWorkerFn = Callable[[str], Awaitable[None]]
RenderPngFn = Callable[..., bytes]
