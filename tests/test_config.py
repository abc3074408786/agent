"""配置管理模块单元测试"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from agent.config import (
    ConfigManager,
    LLMProviderConfig,
    _substitute_env_vars,
)


class TestSubstituteEnvVars:
    """环境变量替换函数测试"""

    def test_simple_string_substitution(self, monkeypatch):
        """测试简单字符串中的环境变量替换"""
        monkeypatch.setenv("TEST_KEY", "my-secret")
        result = _substitute_env_vars("${TEST_KEY}")
        assert result == "my-secret"

    def test_string_with_prefix_suffix(self, monkeypatch):
        """测试带前后缀的字符串中的环境变量替换"""
        monkeypatch.setenv("HOST", "localhost")
        result = _substitute_env_vars("http://${HOST}:8000/v1")
        assert result == "http://localhost:8000/v1"

    def test_multiple_vars_in_string(self, monkeypatch):
        """测试一个字符串中多个环境变量替换"""
        monkeypatch.setenv("USER", "admin")
        monkeypatch.setenv("PASS", "secret")
        result = _substitute_env_vars("${USER}:${PASS}")
        assert result == "admin:secret"

    def test_unset_env_var_preserved(self):
        """测试未设置的环境变量保留原始占位符"""
        # 确保变量不存在
        os.environ.pop("NONEXISTENT_VAR_XYZ", None)
        result = _substitute_env_vars("${NONEXISTENT_VAR_XYZ}")
        assert result == "${NONEXISTENT_VAR_XYZ}"

    def test_dict_substitution(self, monkeypatch):
        """测试字典中的环境变量替换"""
        monkeypatch.setenv("API_KEY", "key123")
        data = {"api_key": "${API_KEY}", "name": "test"}
        result = _substitute_env_vars(data)
        assert result == {"api_key": "key123", "name": "test"}

    def test_list_substitution(self, monkeypatch):
        """测试列表中的环境变量替换"""
        monkeypatch.setenv("VAL", "replaced")
        data = ["${VAL}", "static"]
        result = _substitute_env_vars(data)
        assert result == ["replaced", "static"]

    def test_nested_structure(self, monkeypatch):
        """测试嵌套结构中的环境变量替换"""
        monkeypatch.setenv("NESTED_KEY", "value")
        data = {"outer": [{"inner": "${NESTED_KEY}"}]}
        result = _substitute_env_vars(data)
        assert result == {"outer": [{"inner": "value"}]}

    def test_non_string_values_unchanged(self):
        """测试非字符串值不被修改"""
        assert _substitute_env_vars(42) == 42
        assert _substitute_env_vars(3.14) == 3.14
        assert _substitute_env_vars(True) is True
        assert _substitute_env_vars(None) is None


class TestLLMProviderConfig:
    """LLMProviderConfig 模型测试"""

    def test_minimal_config(self):
        """测试最小必填字段"""
        config = LLMProviderConfig(
            name="test",
            endpoint_url="http://localhost:8000/v1",
            default_model="test-model",
        )
        assert config.name == "test"
        assert config.endpoint_url == "http://localhost:8000/v1"
        assert config.default_model == "test-model"
        assert config.api_key is None
        assert config.max_retries == 3
        assert config.timeout_seconds == 30.0

    def test_full_config(self):
        """测试所有字段"""
        config = LLMProviderConfig(
            name="openai",
            endpoint_url="https://api.openai.com/v1",
            api_key="sk-xxx",
            default_model="gpt-4o",
            max_retries=5,
            timeout_seconds=60.0,
        )
        assert config.name == "openai"
        assert config.api_key == "sk-xxx"
        assert config.max_retries == 5
        assert config.timeout_seconds == 60.0


class TestConfigManager:
    """ConfigManager 类测试"""

    @pytest.fixture
    def sample_config(self, tmp_path, monkeypatch):
        """创建临时配置文件"""
        monkeypatch.setenv("TEST_API_KEY", "test-key-123")
        config_data = {
            "llm_providers": [
                {
                    "name": "local",
                    "endpoint_url": "http://localhost:8000/v1",
                    "api_key": "not-needed",
                    "default_model": "qwen-7b",
                },
                {
                    "name": "openai",
                    "endpoint_url": "https://api.openai.com/v1",
                    "api_key": "${TEST_API_KEY}",
                    "default_model": "gpt-4o",
                },
            ],
            "default_provider": "local",
            "agent": {"max_iterations": 5},
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True)
        return str(config_file)

    def test_load_config(self, sample_config):
        """测试从 YAML 文件加载配置"""
        manager = ConfigManager(config_path=sample_config)
        assert len(manager.providers) == 2
        assert manager.default_provider_name == "local"

    def test_env_var_substitution(self, sample_config):
        """测试环境变量替换"""
        manager = ConfigManager(config_path=sample_config)
        openai = manager.get_provider("openai")
        assert openai.api_key == "test-key-123"

    def test_get_provider_by_name(self, sample_config):
        """测试按名称获取提供商"""
        manager = ConfigManager(config_path=sample_config)
        local = manager.get_provider("local")
        assert local.name == "local"
        assert local.endpoint_url == "http://localhost:8000/v1"

    def test_get_default_provider(self, sample_config):
        """测试获取默认提供商"""
        manager = ConfigManager(config_path=sample_config)
        default = manager.get_provider()
        assert default.name == "local"

    def test_get_nonexistent_provider_raises(self, sample_config):
        """测试获取不存在的提供商抛出异常"""
        manager = ConfigManager(config_path=sample_config)
        with pytest.raises(ValueError, match="不存在"):
            manager.get_provider("nonexistent")

    def test_get_provider_no_default_raises(self, tmp_path):
        """测试无默认提供商时获取默认抛出异常"""
        config_data = {
            "llm_providers": [
                {
                    "name": "test",
                    "endpoint_url": "http://localhost/v1",
                    "default_model": "model",
                }
            ]
        }
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        manager = ConfigManager(config_path=str(config_file))
        with pytest.raises(ValueError, match="未指定提供商名称"):
            manager.get_provider()

    def test_add_provider(self, sample_config):
        """测试添加提供商"""
        manager = ConfigManager(config_path=sample_config)
        new_provider = LLMProviderConfig(
            name="anthropic",
            endpoint_url="https://api.anthropic.com/v1",
            api_key="sk-ant-xxx",
            default_model="claude-sonnet-4-20250514",
        )
        manager.add_provider(new_provider)
        assert len(manager.providers) == 3
        retrieved = manager.get_provider("anthropic")
        assert retrieved.default_model == "claude-sonnet-4-20250514"

    def test_add_duplicate_provider_raises(self, sample_config):
        """测试添加重复名称的提供商抛出异常"""
        manager = ConfigManager(config_path=sample_config)
        duplicate = LLMProviderConfig(
            name="local",
            endpoint_url="http://other/v1",
            default_model="other-model",
        )
        with pytest.raises(ValueError, match="已存在"):
            manager.add_provider(duplicate)

    def test_update_provider(self, sample_config):
        """测试更新提供商配置"""
        manager = ConfigManager(config_path=sample_config)
        updated = LLMProviderConfig(
            name="local",
            endpoint_url="http://localhost:9000/v1",
            api_key="new-key",
            default_model="qwen-14b",
        )
        manager.update_provider("local", updated)
        retrieved = manager.get_provider("local")
        assert retrieved.endpoint_url == "http://localhost:9000/v1"
        assert retrieved.default_model == "qwen-14b"

    def test_update_nonexistent_provider_raises(self, sample_config):
        """测试更新不存在的提供商抛出异常"""
        manager = ConfigManager(config_path=sample_config)
        config = LLMProviderConfig(
            name="ghost",
            endpoint_url="http://x/v1",
            default_model="m",
        )
        with pytest.raises(ValueError, match="不存在"):
            manager.update_provider("ghost", config)

    def test_delete_provider(self, sample_config):
        """测试删除提供商"""
        manager = ConfigManager(config_path=sample_config)
        manager.delete_provider("openai")
        assert len(manager.providers) == 1
        with pytest.raises(ValueError):
            manager.get_provider("openai")

    def test_delete_nonexistent_provider_raises(self, sample_config):
        """测试删除不存在的提供商抛出异常"""
        manager = ConfigManager(config_path=sample_config)
        with pytest.raises(ValueError, match="不存在"):
            manager.delete_provider("nonexistent")

    def test_save_and_reload(self, sample_config):
        """测试保存配置到文件并重新加载"""
        manager = ConfigManager(config_path=sample_config)
        new_provider = LLMProviderConfig(
            name="new-provider",
            endpoint_url="http://new/v1",
            default_model="new-model",
        )
        manager.add_provider(new_provider)
        manager.save()

        # 重新加载验证持久化
        manager2 = ConfigManager(config_path=sample_config)
        assert len(manager2.providers) == 3
        retrieved = manager2.get_provider("new-provider")
        assert retrieved.default_model == "new-model"

    def test_set_default_provider(self, sample_config):
        """测试设置默认提供商"""
        manager = ConfigManager(config_path=sample_config)
        manager.set_default_provider("openai")
        assert manager.default_provider_name == "openai"

    def test_set_default_nonexistent_raises(self, sample_config):
        """测试设置不存在的提供商为默认抛出异常"""
        manager = ConfigManager(config_path=sample_config)
        with pytest.raises(ValueError, match="不存在"):
            manager.set_default_provider("nonexistent")

    def test_file_not_found_raises(self, tmp_path):
        """测试配置文件不存在时抛出异常"""
        with pytest.raises(FileNotFoundError, match="配置文件不存在"):
            ConfigManager(config_path=str(tmp_path / "missing.yaml"))

    def test_load_actual_config(self):
        """测试加载项目实际配置文件"""
        config_path = Path(__file__).parent.parent / "config" / "agent_config.yaml"
        if config_path.exists():
            manager = ConfigManager(config_path=str(config_path))
            assert len(manager.providers) == 10
            assert manager.default_provider_name == "vllm-local"
            vllm = manager.get_provider("vllm-local")
            assert vllm.endpoint_url == "http://localhost:8000/v1"
            assert vllm.default_model == "Qwen/Qwen2.5-7B-Instruct"
