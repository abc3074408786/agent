"""
插件系统

提供:
- Plugin 基类: 定义插件接口 (name, version, setup, teardown)
- PluginManager: 插件生命周期管理 (load, register, unregister)
- 插件可以注册 tools, skills, hooks
- 从 ~/.agent/plugins/ 或项目 .agent/plugins/ 加载
"""

import os
import sys
import importlib
import importlib.util
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, field


# ============ 数据模型 ============

@dataclass
class PluginHook:
    """插件钩子"""
    name: str
    callback: Callable
    priority: int = 0  # 优先级，数字越小优先级越高


@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    version: str
    description: str = ""
    author: str = ""
    enabled: bool = True
    source_path: Optional[str] = None


# ============ Plugin 基类 ============

class Plugin(ABC):
    """
    插件基类
    
    所有插件必须继承此类并实现必要方法。
    
    示例:
        class MyPlugin(Plugin):
            name = "my_plugin"
            version = "1.0.0"
            description = "我的自定义插件"
            
            def setup(self, context):
                # 初始化逻辑
                context.register_tool(my_tool)
                
            def teardown(self):
                # 清理逻辑
                pass
    """

    # 插件元数据（子类必须覆盖）
    name: str = "base_plugin"
    version: str = "0.0.0"
    description: str = ""
    author: str = ""

    def __init__(self):
        self._enabled = True
        self._tools: List[Any] = []
        self._skills: List[Any] = []
        self._hooks: List[PluginHook] = []

    @property
    def enabled(self) -> bool:
        """插件是否启用"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def info(self) -> PluginInfo:
        """获取插件信息"""
        return PluginInfo(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            enabled=self._enabled,
        )

    @abstractmethod
    def setup(self, context: "PluginContext") -> None:
        """
        插件初始化
        
        在此方法中注册工具、技能和钩子。
        
        Args:
            context: 插件上下文，用于注册能力
        """
        pass

    def teardown(self) -> None:
        """
        插件卸载清理
        
        可选实现。在插件被卸载时调用。
        """
        pass

    def on_enable(self) -> None:
        """插件被启用时调用"""
        self._enabled = True

    def on_disable(self) -> None:
        """插件被禁用时调用"""
        self._enabled = False


# ============ PluginContext ============

class PluginContext:
    """
    插件上下文
    
    提供给插件在 setup() 期间使用，用于注册工具、技能和钩子。
    """

    def __init__(self, plugin_name: str, manager: "PluginManager"):
        self._plugin_name = plugin_name
        self._manager = manager
        self._registered_tools: List[str] = []
        self._registered_skills: List[str] = []
        self._registered_hooks: List[str] = []

    @property
    def plugin_name(self) -> str:
        return self._plugin_name

    def register_tool(self, tool: Any, category: str = "plugin") -> None:
        """
        注册工具
        
        Args:
            tool: LangChain BaseTool 实例
            category: 工具分类
        """
        tool_name = getattr(tool, "name", str(tool))
        self._manager._plugin_tools[f"{self._plugin_name}.{tool_name}"] = tool
        self._registered_tools.append(tool_name)

    def register_skill(self, skill: Any) -> None:
        """
        注册技能
        
        Args:
            skill: 技能配置对象
        """
        skill_name = getattr(skill, "name", str(skill))
        self._manager._plugin_skills[f"{self._plugin_name}.{skill_name}"] = skill
        self._registered_skills.append(skill_name)

    def register_hook(self, hook_name: str, callback: Callable, priority: int = 0) -> None:
        """
        注册钩子
        
        Args:
            hook_name: 钩子名称 (如 "before_chat", "after_tool_call")
            callback: 回调函数
            priority: 优先级 (数字越小优先级越高)
        """
        hook = PluginHook(name=hook_name, callback=callback, priority=priority)
        if hook_name not in self._manager._hooks:
            self._manager._hooks[hook_name] = []
        self._manager._hooks[hook_name].append(hook)
        self._manager._hooks[hook_name].sort(key=lambda h: h.priority)
        self._registered_hooks.append(hook_name)

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取插件配置
        
        Args:
            key: 配置键
            default: 默认值
        """
        plugin_config = self._manager._plugin_configs.get(self._plugin_name, {})
        return plugin_config.get(key, default)


# ============ PluginManager ============

class PluginManager:
    """
    插件管理器
    
    负责插件的加载、注册、卸载和生命周期管理。
    
    插件加载路径:
    - 全局: ~/.agent/plugins/
    - 项目: .agent/plugins/
    """

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._plugin_tools: Dict[str, Any] = {}
        self._plugin_skills: Dict[str, Any] = {}
        self._hooks: Dict[str, List[PluginHook]] = {}
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}

    @property
    def plugins(self) -> Dict[str, Plugin]:
        """获取所有已注册的插件"""
        return self._plugins.copy()

    @property
    def tools(self) -> Dict[str, Any]:
        """获取所有插件注册的工具"""
        return self._plugin_tools.copy()

    @property
    def skills(self) -> Dict[str, Any]:
        """获取所有插件注册的技能"""
        return self._plugin_skills.copy()

    def register(self, plugin: Plugin, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        注册插件
        
        Args:
            plugin: Plugin 实例
            config: 插件配置
            
        Returns:
            是否注册成功
        """
        if plugin.name in self._plugins:
            return False
        
        # 保存配置
        if config:
            self._plugin_configs[plugin.name] = config
        
        # 创建上下文并执行 setup
        context = PluginContext(plugin.name, self)
        try:
            plugin.setup(context)
        except Exception as e:
            # setup 失败，清理已注册的内容
            self._cleanup_plugin_resources(plugin.name)
            raise RuntimeError(f"插件 '{plugin.name}' 初始化失败: {str(e)}") from e
        
        self._plugins[plugin.name] = plugin
        return True

    def unregister(self, plugin_name: str) -> bool:
        """
        注销插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            是否注销成功
        """
        if plugin_name not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_name]
        
        # 调用 teardown
        try:
            plugin.teardown()
        except Exception:
            pass  # teardown 错误不阻止注销
        
        # 清理资源
        self._cleanup_plugin_resources(plugin_name)
        
        del self._plugins[plugin_name]
        return True

    def _cleanup_plugin_resources(self, plugin_name: str) -> None:
        """清理插件注册的资源"""
        # 清理工具
        tool_keys = [k for k in self._plugin_tools if k.startswith(f"{plugin_name}.")]
        for key in tool_keys:
            del self._plugin_tools[key]
        
        # 清理技能
        skill_keys = [k for k in self._plugin_skills if k.startswith(f"{plugin_name}.")]
        for key in skill_keys:
            del self._plugin_skills[key]
        
        # 清理钩子
        for hook_name in list(self._hooks.keys()):
            # 注意：钩子中没有存储 plugin_name 所以无法精确清理
            # 在完整实现中应该在 PluginHook 中存储 plugin_name
            pass
        
        # 清理配置
        self._plugin_configs.pop(plugin_name, None)

    def load_from_directory(self, directory: str) -> List[str]:
        """
        从目录加载插件
        
        扫描目录中的 Python 文件，查找 Plugin 子类并加载。
        
        Args:
            directory: 插件目录路径
            
        Returns:
            成功加载的插件名称列表
        """
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return []
        
        loaded = []
        
        for filepath in dir_path.glob("*.py"):
            if filepath.name.startswith("_"):
                continue
            
            try:
                plugin_class = self._load_plugin_from_file(filepath)
                if plugin_class:
                    plugin = plugin_class()
                    
                    # 尝试加载配置文件
                    config = self._load_plugin_config(filepath)
                    
                    self.register(plugin, config=config)
                    loaded.append(plugin.name)
            except Exception as e:
                # 记录错误但继续加载其他插件
                print(f"警告: 加载插件 '{filepath.name}' 失败: {str(e)}")
                continue
        
        return loaded

    def _load_plugin_from_file(self, filepath: Path) -> Optional[Type[Plugin]]:
        """从文件加载插件类"""
        module_name = f"agent_plugin_{filepath.stem}"
        
        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # 查找 Plugin 子类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Plugin)
                    and attr is not Plugin
                ):
                    return attr
            
            return None
            
        except Exception:
            # 清理可能部分加载的模块
            sys.modules.pop(module_name, None)
            raise

    def _load_plugin_config(self, plugin_filepath: Path) -> Optional[Dict[str, Any]]:
        """加载插件配置文件 (同名 .json 文件)"""
        import json
        
        config_path = plugin_filepath.with_suffix(".json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def load_default_directories(self) -> List[str]:
        """
        从默认目录加载插件
        
        加载路径:
        - ~/.agent/plugins/ (全局插件)
        - .agent/plugins/ (项目插件)
        
        Returns:
            成功加载的插件名称列表
        """
        loaded = []
        
        # 全局插件目录
        global_dir = Path.home() / ".agent" / "plugins"
        if global_dir.exists():
            loaded.extend(self.load_from_directory(str(global_dir)))
        
        # 项目插件目录
        project_dir = Path(".agent") / "plugins"
        if project_dir.exists():
            loaded.extend(self.load_from_directory(str(project_dir)))
        
        return loaded

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """获取插件实例"""
        return self._plugins.get(name)

    def list_plugins(self) -> List[PluginInfo]:
        """列出所有已注册的插件信息"""
        return [plugin.info for plugin in self._plugins.values()]

    def enable_plugin(self, name: str) -> bool:
        """启用插件"""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.on_enable()
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        """禁用插件"""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.on_disable()
            return True
        return False

    def trigger_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """
        触发钩子
        
        按优先级顺序调用所有注册到指定钩子的回调。
        
        Args:
            hook_name: 钩子名称
            *args, **kwargs: 传递给回调的参数
            
        Returns:
            所有回调的返回值列表
        """
        hooks = self._hooks.get(hook_name, [])
        results = []
        
        for hook in hooks:
            try:
                result = hook.callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                print(f"警告: 钩子 '{hook_name}' 回调执行失败: {str(e)}")
                results.append(None)
        
        return results


# ============ 全局实例 ============

# 全局插件管理器
plugin_manager = PluginManager()


__all__ = [
    "Plugin",
    "PluginContext",
    "PluginManager",
    "PluginHook",
    "PluginInfo",
    "plugin_manager",
]
