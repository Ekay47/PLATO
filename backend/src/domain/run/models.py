import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


def now_ms() -> int:
    return int(time.time() * 1000)


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


@dataclass
class RunEvent:
    run_id: str
    ts_ms: int
    type: str
    step: Optional[str] = None
    status: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"run_id": self.run_id, "ts_ms": self.ts_ms, "type": self.type}
        if self.step is not None:
            data["step"] = self.step
        if self.status is not None:
            data["status"] = self.status
        if self.payload is not None:
            data["payload"] = self.payload
        return data


@dataclass
class RunState:
    run_id: str
    diagram_type: str
    requirement_text: str
    status: str = "pending"
    current_step: Optional[str] = None
    created_ts_ms: int = field(default_factory=now_ms)
    updated_ts_ms: int = field(default_factory=now_ms)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    subscribers: Set[asyncio.Queue] = field(default_factory=set)
    error: Optional[str] = None

    def snapshot(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "diagram_type": self.diagram_type,
            "status": self.status,
            "current_step": self.current_step,
            "created_ts_ms": self.created_ts_ms,
            "updated_ts_ms": self.updated_ts_ms,
            "artifacts": self.artifacts,
            "error": self.error,
        }
