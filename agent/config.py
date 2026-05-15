"""配置管理模块

提供 LLM 提供商配置模型和配置管理器，支持从 YAML 文件加载配置，
并支持环境变量替换（${ENV_VAR} 语法）。
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class LLMProviderConfig(BaseModel):
    """LLM 提供商配置模型"""

    name: str = Field(..., description="提供商名称标识")
    endpoint_url: str = Field(..., description="API端点URL")
    api_key: Optional[str] = Field(None, description="API密钥")
    default_model: str = Field(..., description="默认模型名称")
    max_retries: int = Field(3, description="最大重试次数")
    timeout_seconds: float = Field(30.0, description="请求超时秒数")


# 匹配 ${ENV_VAR} 格式的环境变量占位符
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _substitute_env_vars(value: Any) -> Any:
    """递归替换值中的环境变量占位符。

    支持 ${ENV_VAR} 语法，将占位符替换为对应环境变量的值。
    如果环境变量未设置，保留原始占位符字符串。

    Args:
        value: 需要处理的值，可以是字符串、字典或列表。

    Returns:
        替换环境变量后的值。
    """
    if isinstance(value, str):
        def _replace_match(match: re.Match) -> str:
            env_name = match.group(1)
            return os.environ.get(env_name, match.group(0))
        return _ENV_VAR_PATTERN.sub(_replace_match, value)
    elif isinstance(value, dict):
        return {k: _substitute_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_substitute_env_vars(item) for item in value]
    return value


class ConfigManager:
    """配置管理器

    从 YAML 文件加载 Agent 配置，支持环境变量替换，
    并提供 LLM 提供商配置的 CRUD 操作。
    """

    def __init__(self, config_path: Optional[str] = None):
        """初始化配置管理器。

        Args:
            config_path: YAML 配置文件路径。默认为项目根目录下的
                         config/agent_config.yaml。
        """
        if config_path is None:
            # 默认配置文件路径：项目根目录/config/agent_config.yaml
            project_root = Path(__file__).parent.parent
            config_path = str(project_root / "config" / "agent_config.yaml")
        self._config_path = Path(config_path)
        self._raw_config: Dict[str, Any] = {}
        self._providers: List[LLMProviderConfig] = []
        self._default_provider: Optional[str] = None
        self._load()

    def _load(self) -> None:
        """从 YAML 文件加载配置。"""
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {self._config_path}"
            )
        with open(self._config_path, "r", encoding="utf-8") as f:
            self._raw_config = yaml.safe_load(f) or {}
        self._parse_providers()

    def _parse_providers(self) -> None:
        """解析 LLM 提供商配置列表。"""
        self._providers = []
        raw_providers = self._raw_config.get("llm_providers", [])
        for provider_data in raw_providers:
            # 对每个提供商配置执行环境变量替换
            resolved = _substitute_env_vars(provider_data)
            self._providers.append(LLMProviderConfig(**resolved))
        self._default_provider = self._raw_config.get("default_provider")

    @property
    def providers(self) -> List[LLMProviderConfig]:
        """获取所有已配置的 LLM 提供商列表。"""
        return list(self._providers)

    @property
    def default_provider_name(self) -> Optional[str]:
        """获取默认提供商名称。"""
        return self._default_provider

    @property
    def raw_config(self) -> Dict[str, Any]:
        """获取原始配置字典（未经环境变量替换）。"""
        return dict(self._raw_config)

    def get_provider(self, name: Optional[str] = None) -> LLMProviderConfig:
        """获取指定名称的提供商配置。

        Args:
            name: 提供商名称。为 None 时返回默认提供商。

        Returns:
            对应的 LLMProviderConfig 实例。

        Raises:
            ValueError: 提供商名称不存在或未配置默认提供商。
        """
        if name is None:
            name = self._default_provider
        if name is None:
            raise ValueError("未指定提供商名称且未配置默认提供商")
        for provider in self._providers:
            if provider.name == name:
                return provider
        raise ValueError(f"提供商 '{name}' 不存在")

    def add_provider(self, config: LLMProviderConfig) -> None:
        """添加新的提供商配置。

        Args:
            config: 要添加的提供商配置。

        Raises:
            ValueError: 同名提供商已存在。
        """
        for provider in self._providers:
            if provider.name == config.name:
                raise ValueError(f"提供商 '{config.name}' 已存在")
        self._providers.append(config)
        self._sync_raw_config()

    def update_provider(self, name: str, config: LLMProviderConfig) -> None:
        """更新已有的提供商配置。

        Args:
            name: 要更新的提供商名称。
            config: 新的提供商配置。

        Raises:
            ValueError: 指定名称的提供商不存在。
        """
        for i, provider in enumerate(self._providers):
            if provider.name == name:
                self._providers[i] = config
                self._sync_raw_config()
                return
        raise ValueError(f"提供商 '{name}' 不存在")

    def delete_provider(self, name: str) -> None:
        """删除指定名称的提供商配置。

        Args:
            name: 要删除的提供商名称。

        Raises:
            ValueError: 指定名称的提供商不存在。
        """
        for i, provider in enumerate(self._providers):
            if provider.name == name:
                self._providers.pop(i)
                self._sync_raw_config()
                return
        raise ValueError(f"提供商 '{name}' 不存在")

    def set_default_provider(self, name: str) -> None:
        """设置默认提供商。

        Args:
            name: 提供商名称。

        Raises:
            ValueError: 指定名称的提供商不存在。
        """
        # 验证提供商存在
        self.get_provider(name)
        self._default_provider = name
        self._raw_config["default_provider"] = name

    def _sync_raw_config(self) -> None:
        """将当前提供商列表同步到原始配置字典。"""
        self._raw_config["llm_providers"] = [
            provider.model_dump(exclude_none=False)
            for provider in self._providers
        ]

    def save(self) -> None:
        """将当前配置持久化到 YAML 文件。"""
        self._sync_raw_config()
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                self._raw_config,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

    def reload(self) -> None:
        """重新从文件加载配置。"""
        self._load()
