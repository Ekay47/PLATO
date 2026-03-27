import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from src.core.settings_loader import settings


class PlantUMLRenderTimeout(Exception):
    def __init__(self, timeout_s: float) -> None:
        super().__init__(f"PlantUML render timed out after {timeout_s}s")
        self.timeout_s = timeout_s


@dataclass(frozen=True)
class PlantUMLJarConfig:
    jar_path: str
    java_cmd: str
    timeout_s: float

    @staticmethod
    def from_env() -> "PlantUMLJarConfig":
        default_jar = ""
        try:
            utils_dir = Path(__file__).resolve().parents[1] / "utils"
            candidates = sorted(utils_dir.glob("plantuml-*.jar"))
            if candidates:
                default_jar = str(candidates[-1])
        except Exception:
            default_jar = ""
        return PlantUMLJarConfig(
            jar_path=(settings.get_str("plantuml.jar_path", "") or default_jar or "").strip(),
            java_cmd=settings.get_str("java.cmd", "java").strip(),
            timeout_s=settings.get_float("plantuml.jar_timeout_s", 8.0),
        )


def validate_with_jar(code: str, *, cfg: Optional[PlantUMLJarConfig] = None) -> Optional[List[str]]:
    cfg = cfg or PlantUMLJarConfig.from_env()
    if not cfg.jar_path:
        return None
    if not os.path.exists(cfg.jar_path):
        return None

    cmd = [cfg.java_cmd, "-jar", cfg.jar_path, "-syntax"]
    try:
        p = subprocess.run(
            cmd,
            input=(code or "").encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=cfg.timeout_s,
            check=False,
        )
    except Exception:
        return ["PlantUML jar syntax check failed to execute"]

    out = (p.stdout or b"").decode("utf-8", errors="replace").strip()
    err = (p.stderr or b"").decode("utf-8", errors="replace").strip()

    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if not lines:
        if p.returncode == 0:
            return []
        if err:
            return [err[:400]]
        return ["PlantUML jar returned non-zero without output"]

    head = lines[0].split()[0].upper()
    if head == "ERROR":
        return lines[:6]
    if p.returncode != 0:
        return (lines[:4] + ([err[:200]] if err else []))[:6]
    return []


def render_png_with_jar(
    code: str, *, cfg: Optional[PlantUMLJarConfig] = None, timeout_s: Optional[float] = None
) -> Optional[bytes]:
    cfg = cfg or PlantUMLJarConfig.from_env()
    if not cfg.jar_path:
        return None
    if not os.path.exists(cfg.jar_path):
        return None

    cmd = [cfg.java_cmd, "-jar", cfg.jar_path, "-tpng", "-pipe", "-charset", "UTF-8"]
    try:
        p = subprocess.run(
            cmd,
            input=(code or "").encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=float(timeout_s) if timeout_s is not None else cfg.timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise PlantUMLRenderTimeout(float(timeout_s) if timeout_s is not None else cfg.timeout_s)
    except Exception:
        return None

    out = p.stdout or b""
    if p.returncode != 0:
        return None
    if len(out) < 8 or out[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return out
