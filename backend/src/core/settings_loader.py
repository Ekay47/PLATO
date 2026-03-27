import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

class Settings:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def _get_nested(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        val = self._data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val if val is not None else default

    def get(self, key: str, default: Any = None) -> Any:
        return self._get_nested(key, default)

    def get_str(self, key: str, default: str = "") -> str:
        return str(self.get(key, default))

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, default))
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key, default))
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        v = self.get(key)
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("1", "true", "yes", "on")

def _load_settings_yaml() -> Dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    config_path = os.getenv("PLATO_CONFIG_PATH")
    
    if config_path:
        path = Path(config_path)
    else:
        path = root / "config.yaml"
        if not path.exists():
            path = root / "config.example.yaml"
            
    if not path.exists():
        return {}
        
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as e:
        import logging
        logging.getLogger("plato.config").error(f"Failed to load config from {path}: {e}")
        return {}

# 暴露单例配置对象
settings = Settings(_load_settings_yaml())

