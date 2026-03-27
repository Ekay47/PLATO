import json
import logging
import time
import sys
import types
import os
import uuid
from contextvars import ContextVar, Token
from typing import Dict, Optional, Tuple

from src.core.settings_loader import settings

logger = logging.getLogger("plato.llm")

# --- 立即安装 uuid_utils 补丁，防止 langchain 导入失败 ---
def _install_uuid_utils_shim():
    if "uuid_utils" in sys.modules and not isinstance(sys.modules["uuid_utils"], types.ModuleType):
        # 如果已经存在但不是我们想要的 mock，或者导入失败留下的残骸
        pass
    
    try:
        import uuid_utils
        return # 已经正常安装
    except ImportError:
        pass

    def uuid7() -> uuid.UUID:
        ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
        rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
        rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)

        b = bytearray(16)
        b[0:6] = ts_ms.to_bytes(6, "big")
        b[6] = 0x70 | ((rand_a >> 8) & 0x0F)
        b[7] = rand_a & 0xFF
        rb = rand_b.to_bytes(8, "big")
        b[8] = (rb[0] & 0x3F) | 0x80
        b[9:16] = rb[1:8]
        return uuid.UUID(bytes=bytes(b))

    compat = types.ModuleType("uuid_utils.compat")
    compat.uuid7 = uuid7

    pkg = types.ModuleType("uuid_utils")
    pkg.compat = compat

    sys.modules["uuid_utils"] = pkg
    sys.modules["uuid_utils.compat"] = compat
    logger.info("uuid_utils shim installed successfully to bypass Windows DLL issue")

_install_uuid_utils_shim()
# ------------------------------------------------------

_token_usage: ContextVar[Optional[Dict[str, int]]] = ContextVar("plato.token_usage", default=None)


def start_token_usage() -> Token:
    return _token_usage.set({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})


def stop_token_usage(token: Token) -> Optional[Dict[str, int]]:
    usage = _token_usage.get()
    _token_usage.reset(token)
    return dict(usage) if usage else None


def _add_token_usage(*, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: Optional[int] = None) -> None:
    usage = _token_usage.get()
    if usage is None:
        return
    usage["prompt_tokens"] = int(usage.get("prompt_tokens", 0)) + int(prompt_tokens or 0)
    usage["completion_tokens"] = int(usage.get("completion_tokens", 0)) + int(completion_tokens or 0)
    if total_tokens is None:
        total_tokens = int(prompt_tokens or 0) + int(completion_tokens or 0)
    usage["total_tokens"] = int(usage.get("total_tokens", 0)) + int(total_tokens or 0)


def _extract_usage(message: object) -> Optional[Tuple[int, int, int]]:
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict):
        prompt = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        completion = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        total = usage.get("total_tokens")
        if total is None:
            total = int(prompt or 0) + int(completion or 0)
        return int(prompt or 0), int(completion or 0), int(total or 0)

    resp = getattr(message, "response_metadata", None)
    if isinstance(resp, dict):
        token_usage = resp.get("token_usage") or resp.get("usage") or resp.get("usage_metadata")
        if isinstance(token_usage, dict):
            prompt = token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0
            completion = token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0
            total = token_usage.get("total_tokens")
            if total is None:
                total = int(prompt or 0) + int(completion or 0)
            return int(prompt or 0), int(completion or 0), int(total or 0)

    return None


class LLMClient:
    def __init__(self) -> None:
        self.api_url = settings.get_str("llm.api_url", "https://api.deepseek.com/v1").rstrip("/")
        self.api_key = settings.get_str("llm.api_key", "")
        self.model = settings.get_str("llm.model", "deepseek-chat")
        self.mock = settings.get_bool("llm.mock", False)

    async def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        if self.mock:
            logger.info("llm.chat mock=1 model=%s", self.model)
            return self._mock_response(system=system, user=user)

        if not self.api_key:
            logger.warning("llm.chat missing_api_key=1 api_url=%s model=%s", self.api_url, self.model)

        t0 = time.perf_counter()
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = ChatOpenAI(
                model=self.model,
                temperature=float(temperature),
                openai_api_key=self.api_key or "sk-dummy", # Provide dummy if empty to avoid pydantic error
                openai_api_base=self.api_url,
            )
            msg = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
            out = getattr(msg, "content", "") or ""

            usage = _extract_usage(msg)
            if usage is not None:
                prompt_tokens, completion_tokens, total_tokens = usage
                _add_token_usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )

            logger.info(
                "llm.chat ok=1 model=%s api_url=%s temp=%.2f sys_chars=%d user_chars=%d out_chars=%d ms=%d",
                self.model,
                self.api_url,
                float(temperature),
                len(system or ""),
                len(user or ""),
                len(out or ""),
                int((time.perf_counter() - t0) * 1000),
            )
            return out
        except Exception:
            logger.error(
                "llm.chat ok=0 model=%s api_url=%s ms=%d",
                self.model,
                self.api_url,
                int((time.perf_counter() - t0) * 1000),
                exc_info=True,
            )
            raise

    def _mock_response(self, *, system: str, user: str) -> str:
        lower = (system + "\n" + user).lower()
        if "respond with: **[valid]**" in lower or "respond with: [valid]" in lower:
            return "[Valid]"
        if "output only a json array" in lower or "json array" in lower:
            return json.dumps(
                ["Check inventory", "Reserve items", "Send confirmation email", "Handle back-order", "Ship order"],
                ensure_ascii=False,
            )
        if "structured format" in lower and "integrat" in lower:
            return "\n".join(
                [
                    "Check inventory",
                    "if in stock",
                    "  Reserve items",
                    "  Send confirmation email",
                    "else",
                    "  Handle back-order",
                    "Ship order",
                ]
            )
        if "layer" in lower and "decomposition" in lower:
            return "Level 1{\n**Check inventory** triggers a conditional structure with 2 branches:\n  Branch **in stock**: Reserve items -> Send confirmation email -> Ship order\n  Branch **out of stock**: Handle back-order -> Ship order}\n"
        if "plantuml" in lower:
            return "\n".join(
                [
                    "@startuml",
                    "start",
                    ":Check inventory;",
                    "if (In stock?) then (yes)",
                    "  :Reserve items;",
                    "  :Send confirmation email;",
                    "else (no)",
                    "  :Handle back-order;",
                    "endif",
                    ":Ship order;",
                    "stop",
                    "@enduml",
                ]
            )
        return "OK"
