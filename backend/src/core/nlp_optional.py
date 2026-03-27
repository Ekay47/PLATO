import json
import os
from dataclasses import dataclass
from typing import List, Optional

import httpx

from src.core.settings_loader import settings


_FASTCOREF_INSTANCE = None
_FASTCOREF_INSTANCE_KEY = None
_FASTCOREF_LOCK = None


@dataclass(frozen=True)
class NLPConfig:
    coref_provider: str = "fastcoref"
    dependency_provider: str = "corenlp"
    corenlp_url: str = "http://127.0.0.1:9000"
    corenlp_timeout_s: float = 3.0
    max_prompt_chars: int = 4000

    @staticmethod
    def from_env() -> "NLPConfig":
        return NLPConfig(
            coref_provider=settings.get_str("nlp.coref_provider", "fastcoref").strip().lower(),
            dependency_provider=settings.get_str("nlp.dependency_provider", "corenlp").strip().lower(),
            corenlp_url=settings.get_str("corenlp.url", "http://127.0.0.1:9000").strip().rstrip("/"),
            corenlp_timeout_s=settings.get_float("corenlp.timeout_s", 3.0),
            max_prompt_chars=settings.get_int("nlp.max_prompt_chars", 4000),
        )

# 设置 fastcoref 的环境变量
os.environ.setdefault("PLATO_FASTCOREF_DEVICE", settings.get_str("nlp.fastcoref_device", "cpu"))
os.environ.setdefault("PLATO_FASTCOREF_MODEL_PATH", settings.get_str("nlp.fastcoref_model_path", ""))
os.environ.setdefault("PLATO_FASTCOREF_CACHE_DIR", settings.get_str("nlp.fastcoref_cache_dir", ""))


def _truncate(s: str, *, max_chars: int) -> str:
    if not s:
        return ""
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 3] + "..."


def _format_exc(e: Exception) -> str:
    detail = str(e).strip()
    if detail:
        return f"{type(e).__name__}: {detail}"
    return type(e).__name__


async def dependency_tree_for_prompt(text: str, *, cfg: Optional[NLPConfig] = None) -> str:
    cfg = cfg or NLPConfig.from_env()
    if cfg.dependency_provider != "corenlp":
        return ""
    if not cfg.corenlp_url:
        raise RuntimeError("nlp.dependency_provider is corenlp but corenlp.url is empty")

    props = {"annotators": "tokenize,ssplit,pos,depparse", "outputFormat": "json"}
    url = cfg.corenlp_url.rstrip("/") + "/"
    headers = {"Content-Type": "text/plain; charset=utf-8"}
    params = {"properties": json.dumps(props)}

    try:
        request_text = _truncate(text or "", max_chars=max(200, cfg.max_prompt_chars))
        async with httpx.AsyncClient(timeout=cfg.corenlp_timeout_s) as client:
            r = await client.post(url, params=params, headers=headers, content=request_text.encode("utf-8"))
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        raise RuntimeError(f"CoreNLP dependency parse request failed: {_format_exc(e)}") from e

    lines: List[str] = []
    for sent in (data or {}).get("sentences", []) or []:
        for dep in sent.get("basicDependencies", []) or []:
            if not isinstance(dep, dict):
                continue
            rel = dep.get("dep")
            if rel == "ROOT":
                continue
            gov = dep.get("governorGloss") or ""
            child = dep.get("dependentGloss") or ""
            if gov and child and rel:
                lines.append(f"{gov} -[{rel}]-> {child}")

    return _truncate("\n".join(lines), max_chars=cfg.max_prompt_chars)


def _fastcoref_defaults() -> tuple:
    base_dir = os.path.dirname(os.path.dirname(__file__))  # backend/src
    backend_dir = os.path.dirname(base_dir)  # backend
    default_cache_dir = os.path.join(backend_dir, "cache", "fastcoref")
    default_model_path = os.path.join(base_dir, "utils", "f-coref")
    return default_cache_dir, default_model_path


def _get_fastcoref() -> Optional[object]:
    global _FASTCOREF_INSTANCE, _FASTCOREF_INSTANCE_KEY
    global _FASTCOREF_LOCK

    from fastcoref import FCoref

    if _FASTCOREF_LOCK is None:
        import threading

        _FASTCOREF_LOCK = threading.Lock()

    device = settings.get_str("nlp.fastcoref_device", "cpu").strip()
    default_cache_dir, default_model_path = _fastcoref_defaults()
    cache_dir = (settings.get_str("nlp.fastcoref_cache_dir", "") or default_cache_dir).strip()
    model_path = (settings.get_str("nlp.fastcoref_model_path", "") or default_model_path).strip()

    try:
        import spacy

        spacy.load("en_core_web_sm", exclude=("tagger", "parser", "lemmatizer", "ner", "textcat"))
    except Exception as e:
        raise RuntimeError(f"spaCy model en_core_web_sm is unavailable: {e}") from e

    key = (device, cache_dir, model_path)
    with _FASTCOREF_LOCK:
        if _FASTCOREF_INSTANCE is not None and _FASTCOREF_INSTANCE_KEY == key:
            return _FASTCOREF_INSTANCE

        if cache_dir:
            os.environ["HF_HOME"] = cache_dir
            os.environ["TRANSFORMERS_CACHE"] = cache_dir

        kwargs = {"device": device}
        if model_path:
            kwargs["model_name_or_path"] = model_path

        _FASTCOREF_INSTANCE = FCoref(**kwargs)
        _FASTCOREF_INSTANCE_KEY = key
        return _FASTCOREF_INSTANCE


def _try_fastcoref(text: str) -> str:
    model = _get_fastcoref()
    if model is None:
        return ""
    res = model.predict(texts=[text])
    return str(res)


async def coref_info_for_prompt(text: str, *, cfg: Optional[NLPConfig] = None) -> str:
    cfg = cfg or NLPConfig.from_env()
    if cfg.coref_provider != "fastcoref":
        return ""
    import asyncio

    raw = await asyncio.to_thread(_try_fastcoref, text or "")
    return _truncate(raw, max_chars=cfg.max_prompt_chars)


async def validate_nlp_runtime(*, cfg: Optional[NLPConfig] = None) -> None:
    cfg = cfg or NLPConfig.from_env()
    errors: List[str] = []

    if cfg.coref_provider == "fastcoref":
        try:
            import fastcoref  # noqa: F401
            import spacy  # noqa: F401
            import torch  # noqa: F401
            spacy.load("en_core_web_sm", exclude=("tagger", "parser", "lemmatizer", "ner", "textcat"))
        except Exception as e:
            errors.append(f"coref unavailable: {e}")

    if cfg.dependency_provider == "corenlp":
        if not cfg.corenlp_url:
            errors.append("dependency unavailable: corenlp.url is empty")
        else:
            props = {"annotators": "tokenize,ssplit,pos", "outputFormat": "json"}
            try:
                async with httpx.AsyncClient(timeout=cfg.corenlp_timeout_s) as client:
                    r = await client.post(
                        cfg.corenlp_url.rstrip("/") + "/",
                        params={"properties": json.dumps(props)},
                        headers={"Content-Type": "text/plain; charset=utf-8"},
                        content=b"ping",
                    )
                    if r.status_code != 200:
                        errors.append(f"dependency unavailable: CoreNLP status={r.status_code}")
            except Exception as e:
                errors.append(f"dependency unavailable: CoreNLP request failed: {e}")

    if errors:
        raise RuntimeError("; ".join(errors))
