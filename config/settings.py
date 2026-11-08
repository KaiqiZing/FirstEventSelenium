"""统一配置中心（裁剪自参考工程，仅保留 YAML 配置源）。"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from common.exceptions import ConfigError


class Config:
    """单例配置读取器，支持点路径读取。"""

    _instance: "Config | None" = None

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.base_dir = Path(__file__).resolve().parent.parent
        self.settings_file = self.base_dir / "config" / "settings.yaml"
        self._data = self._load()
        self._initialized = True

    def _load(self) -> dict[str, Any]:
        if not self.settings_file.exists():
            raise ConfigError("配置文件不存在", config_file=str(self.settings_file))
        with self.settings_file.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}

    def reload(self) -> None:
        self._data = self._load()

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        """点路径取值；键缺失时返回 default（兼容显式传入 None 表示期望默认）。"""
        if not key:
            return self.as_dict()
        current: Any = self._data
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    @property
    def active_env(self) -> str:
        return str(self.get("env.active", "dev"))

    def get_env_config(self) -> dict[str, Any]:
        env_name = self.active_env
        env_config = self.get(f"env.{env_name}", {})
        if not isinstance(env_config, dict):
            raise ConfigError(
                "环境配置格式错误",
                config_key=f"env.{env_name}",
                config_file=str(self.settings_file),
            )
        return env_config
