"""
LLM Module - 多提供商大语言模型支持

支持的提供商:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Azure OpenAI
- 本地/自定义兼容 API

提供:
- 统一的 ChatModel 接口
- 提供商工厂
- 流式响应支持
- 重试和错误处理
"""

import os
from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Optional,
    Union,
    Literal,
)
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.callbacks import CallbackManagerForLLMRun

from agent.observability import get_logger, get_tracer

logger = get_logger("llm")
tracer = get_tracer("llm")


class LLMProvider(str, Enum):
    """LLM 提供商枚举"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: int = 60
    max_retries: int = 3
    streaming: bool = False
    # Azure 特定配置
    azure_deployment: Optional[str] = None
    azure_api_version: str = "2024-02-15-preview"
    # 额外参数
    extra_params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMConfig":
        """从字典创建配置"""
        provider = data.get("provider", "openai")
        if isinstance(provider, str):
            provider = LLMProvider(provider)
        
        return cls(
            provider=provider,
            model=data.get("model", "gpt-4"),
            api_key=data.get("api_key"),
            api_base=data.get("api_base"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
            timeout=data.get("timeout", 60),
            max_retries=data.get("max_retries", 3),
            streaming=data.get("streaming", False),
            azure_deployment=data.get("azure_deployment"),
            azure_api_version=data.get("azure_api_version", "2024-02-15-preview"),
            extra_params=data.get("extra_params", {}),
        )


class LLMFactory:
    """LLM 工厂类 - 创建不同提供商的 ChatModel"""

    @staticmethod
    @tracer.trace("create_llm")
    def create(config: Union[LLMConfig, Dict[str, Any]]) -> BaseChatModel:
        """
        根据配置创建 LLM 实例
        
        Args:
            config: LLM 配置对象或字典
            
        Returns:
            BaseChatModel 实例
        """
        if isinstance(config, dict):
            config = LLMConfig.from_dict(config)

        logger.info(
            f"Creating LLM instance",
            provider=config.provider.value,
            model=config.model,
        )

        if config.provider == LLMProvider.OPENAI:
            return LLMFactory._create_openai(config)
        elif config.provider == LLMProvider.ANTHROPIC:
            return LLMFactory._create_anthropic(config)
        elif config.provider == LLMProvider.AZURE_OPENAI:
            return LLMFactory._create_azure_openai(config)
        elif config.provider == LLMProvider.CUSTOM:
            return LLMFactory._create_custom(config)
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

    @staticmethod
    def _create_openai(config: LLMConfig) -> BaseChatModel:
        """创建 OpenAI ChatModel"""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is required for OpenAI support. "
                "Install it with: pip install langchain-openai"
            )

        api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is required")

        return ChatOpenAI(
            model=config.model,
            api_key=api_key,
            base_url=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
            max_retries=config.max_retries,
            streaming=config.streaming,
            **config.extra_params,
        )

    @staticmethod
    def _create_anthropic(config: LLMConfig) -> BaseChatModel:
        """创建 Anthropic ChatModel"""
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "langchain-anthropic is required for Anthropic support. "
                "Install it with: pip install langchain-anthropic"
            )

        api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key is required")

        return ChatAnthropic(
            model=config.model,
            api_key=api_key,
            base_url=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens or 4096,
            timeout=config.timeout,
            max_retries=config.max_retries,
            streaming=config.streaming,
            **config.extra_params,
        )

    @staticmethod
    def _create_azure_openai(config: LLMConfig) -> BaseChatModel:
        """创建 Azure OpenAI ChatModel"""
        try:
            from langchain_openai import AzureChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is required for Azure OpenAI support. "
                "Install it with: pip install langchain-openai"
            )

        api_key = config.api_key or os.getenv("AZURE_OPENAI_API_KEY")
        api_base = config.api_base or os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment = config.azure_deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")

        if not api_key:
            raise ValueError("Azure OpenAI API key is required")
        if not api_base:
            raise ValueError("Azure OpenAI endpoint is required")

        return AzureChatOpenAI(
            azure_deployment=deployment or config.model,
            api_key=api_key,
            azure_endpoint=api_base,
            api_version=config.azure_api_version,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
            max_retries=config.max_retries,
            streaming=config.streaming,
            **config.extra_params,
        )

    @staticmethod
    def _create_custom(config: LLMConfig) -> BaseChatModel:
        """创建自定义/本地 ChatModel (OpenAI 兼容 API)"""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai is required for custom API support. "
                "Install it with: pip install langchain-openai"
            )

        if not config.api_base:
            raise ValueError("API base URL is required for custom provider")

        return ChatOpenAI(
            model=config.model,
            api_key=config.api_key or "not-needed",  # 某些本地 API 不需要 key
            base_url=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
            max_retries=config.max_retries,
            streaming=config.streaming,
            **config.extra_params,
        )


class LLMManager:
    """
    LLM 管理器 - 管理多个 LLM 实例
    
    支持:
    - 注册多个 LLM 配置
    - 按名称获取 LLM 实例
    - 默认 LLM 设置
    - 懒加载实例化
    """

    def __init__(self):
        self._configs: Dict[str, LLMConfig] = {}
        self._instances: Dict[str, BaseChatModel] = {}
        self._default: Optional[str] = None

    def register(
        self,
        name: str,
        config: Union[LLMConfig, Dict[str, Any]],
        set_default: bool = False,
    ) -> None:
        """
        注册 LLM 配置
        
        Args:
            name: LLM 名称
            config: LLM 配置
            set_default: 是否设为默认
        """
        if isinstance(config, dict):
            config = LLMConfig.from_dict(config)
        
        self._configs[name] = config
        
        if set_default or self._default is None:
            self._default = name

        logger.info(
            f"Registered LLM: {name}",
            provider=config.provider.value,
            model=config.model,
            is_default=set_default,
        )

    def get(self, name: Optional[str] = None) -> BaseChatModel:
        """
        获取 LLM 实例 (懒加载)
        
        Args:
            name: LLM 名称，None 则返回默认
            
        Returns:
            BaseChatModel 实例
        """
        name = name or self._default
        if not name:
            raise ValueError("No LLM registered")

        if name not in self._configs:
            raise ValueError(f"LLM not found: {name}")

        # 懒加载
        if name not in self._instances:
            self._instances[name] = LLMFactory.create(self._configs[name])

        return self._instances[name]

    def get_config(self, name: Optional[str] = None) -> LLMConfig:
        """获取 LLM 配置"""
        name = name or self._default
        if not name or name not in self._configs:
            raise ValueError(f"LLM config not found: {name}")
        return self._configs[name]

    def list_models(self) -> List[str]:
        """列出所有已注册的 LLM 名称"""
        return list(self._configs.keys())

    def set_default(self, name: str) -> None:
        """设置默认 LLM"""
        if name not in self._configs:
            raise ValueError(f"LLM not found: {name}")
        self._default = name

    def remove(self, name: str) -> None:
        """移除 LLM"""
        if name in self._configs:
            del self._configs[name]
        if name in self._instances:
            del self._instances[name]
        if self._default == name:
            self._default = next(iter(self._configs), None)


def create_chat_model(
    provider: str = "openai",
    model: str = "gpt-4",
    **kwargs,
) -> BaseChatModel:
    """
    快速创建 ChatModel 的便捷函数
    
    Args:
        provider: 提供商名称 (openai, anthropic, azure_openai, custom)
        model: 模型名称
        **kwargs: 其他配置参数
        
    Returns:
        BaseChatModel 实例
        
    Example:
        >>> llm = create_chat_model("openai", "gpt-4", temperature=0.5)
        >>> llm = create_chat_model("anthropic", "claude-3-opus-20240229")
    """
    config = LLMConfig(
        provider=LLMProvider(provider),
        model=model,
        **kwargs,
    )
    return LLMFactory.create(config)


# 全局 LLM 管理器实例
llm_manager = LLMManager()


__all__ = [
    # 枚举
    "LLMProvider",
    # 配置
    "LLMConfig",
    # 类
    "LLMFactory",
    "LLMManager",
    # 便捷函数
    "create_chat_model",
    # 全局实例
    "llm_manager",
]
