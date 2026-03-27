import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import httpx

from src.core.settings_loader import settings

logger = logging.getLogger("plato.corenlp")


@dataclass(frozen=True)
class CoreNLPConfig:
    mode: str
    host: str
    port: int
    url: str
    java_cmd: str
    heap: str
    threads: int
    timeout_ms: int
    max_char_length: int
    corenlp_dir: str
    models_english_jar: str
    startup_timeout_s: float

    @staticmethod
    def from_env() -> "CoreNLPConfig":
        host = settings.get_str("corenlp.host", "127.0.0.1").strip()
        port = settings.get_int("corenlp.port", 9000)
        url = settings.get_str("corenlp.url", f"http://{host}:{port}").strip()
        default_dir = str(Path(__file__).resolve().parents[1] / "utils" / "stanford-corenlp-4.5.10")
        default_models = str(Path(__file__).resolve().parents[1] / "utils" / "stanford-corenlp-4.5.10-models-english.jar")
        return CoreNLPConfig(
            mode=settings.get_str("corenlp.mode", "managed").strip().lower(),
            host=host,
            port=port,
            url=url,
            java_cmd=settings.get_str("java.cmd", "java").strip(),
            heap=settings.get_str("corenlp.heap", "2g").strip().lower(),
            threads=settings.get_int("corenlp.threads", 2),
            timeout_ms=settings.get_int("corenlp.server_timeout_ms", 600000),
            max_char_length=settings.get_int("corenlp.max_char_length", 50000),
            corenlp_dir=settings.get_str("corenlp.dir", default_dir).strip(),
            models_english_jar=settings.get_str("corenlp.models_en_jar", default_models).strip(),
            startup_timeout_s=settings.get_float("corenlp.startup_timeout_s", 20.0),
        )

    def annotate_url(self) -> str:
        return self.url.rstrip("/") + "/"


def _classpath(corenlp_dir: str, models_english_jar: str) -> str:
    sep = ";" if os.name == "nt" else ":"
    parts = []
    d = Path(corenlp_dir)
    if d.exists():
        parts.append(str(d / "*"))
    if models_english_jar:
        parts.append(models_english_jar)
    return sep.join(parts)


async def check_alive(url: str, *, timeout_s: float = 2.0) -> bool:
    props = {"annotators": "tokenize,ssplit,pos", "outputFormat": "json"}
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(url.rstrip("/") + "/", params={"properties": json.dumps(props)}, content=b"ping")
            return r.status_code == 200
    except Exception:
        return False


class ManagedCoreNLP:
    def __init__(self, *, cfg: Optional[CoreNLPConfig] = None) -> None:
        self.cfg = cfg or CoreNLPConfig.from_env()
        self.proc: Optional[subprocess.Popen] = None

    async def ensure_started(self) -> None:
        if self.cfg.mode != "managed":
            return
        if await check_alive(self.cfg.url, timeout_s=1.0):
            return
        if self.proc and self.proc.poll() is None:
            return

        cp = _classpath(self.cfg.corenlp_dir, self.cfg.models_english_jar)
        if not cp:
            logger.warning("corenlp.start skipped reason=no_classpath")
            return

        heap = self.cfg.heap
        if not heap.endswith("g") and not heap.endswith("m"):
            heap = heap + "g"

        cmd: Sequence[str] = [
            self.cfg.java_cmd,
            f"-Xmx{heap}",
            "-cp",
            cp,
            "edu.stanford.nlp.pipeline.StanfordCoreNLPServer",
            "-host",
            self.cfg.host,
            "-port",
            str(self.cfg.port),
            "-timeout",
            str(self.cfg.timeout_ms),
            "-threads",
            str(self.cfg.threads),
            "-maxCharLength",
            str(self.cfg.max_char_length),
            "-quiet",
        ]

        try:
            self.proc = subprocess.Popen(
                list(cmd),
                cwd=self.cfg.corenlp_dir if self.cfg.corenlp_dir else None,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.warning("corenlp.start failed error=%s", str(e))
            self.proc = None
            return

        t0 = time.perf_counter()
        while time.perf_counter() - t0 < self.cfg.startup_timeout_s:
            if await check_alive(self.cfg.url, timeout_s=1.0):
                logger.info("corenlp.started url=%s", self.cfg.url)
                return
            await asyncio.sleep(0.5)

        logger.warning("corenlp.start timeout url=%s", self.cfg.url)

    async def shutdown(self) -> None:
        if self.cfg.mode != "managed":
            return
        if not self.proc:
            return
        if self.proc.poll() is not None:
            self.proc = None
            return
        try:
            self.proc.terminate()
        except Exception:
            pass
        self.proc = None
