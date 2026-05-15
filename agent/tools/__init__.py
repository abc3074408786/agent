"""
Tools Module - 工具注册和基础工具集

提供:
- 工具注册器
- 工具装饰器
- 内置基础工具 (搜索、计算、时间等)
- LangChain Tool 兼容
"""

import json
import math
import httpx
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type, Union
from datetime import datetime, timezone
from functools import wraps
from dataclasses import dataclass, field

from langchain_core.tools import BaseTool, StructuredTool, tool
from pydantic import BaseModel, Field

from agent.observability import get_logger, get_tracer

logger = get_logger("tools")
tracer = get_tracer("tools")


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    category: str = "general"
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)


class ToolRegistry:
    """
    工具注册器
    
    管理所有可用工具的注册、获取和分类
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
        self._categories: Dict[str, List[str]] = {}

    def register(
        self,
        tool: BaseTool,
        category: str = "general",
        version: str = "1.0.0",
        author: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """
        注册工具
        
        Args:
            tool: LangChain 工具实例
            category: 工具分类
            version: 版本号
            author: 作者
            tags: 标签列表
        """
        name = tool.name
        
        self._tools[name] = tool
        self._metadata[name] = ToolMetadata(
            name=name,
            description=tool.description,
            category=category,
            version=version,
            author=author,
            tags=tags or [],
        )
        
        # 更新分类索引
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)
        
        logger.info(
            f"Registered tool: {name}",
            category=category,
            version=version,
        )

    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)

    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """获取工具元数据"""
        return self._metadata.get(name)

    def get_by_category(self, category: str) -> List[BaseTool]:
        """按分类获取工具"""
        names = self._categories.get(category, [])
        return [self._tools[name] for name in names if name in self._tools]

    def get_by_tags(self, tags: List[str]) -> List[BaseTool]:
        """按标签获取工具"""
        result = []
        for name, metadata in self._metadata.items():
            if any(tag in metadata.tags for tag in tags):
                result.append(self._tools[name])
        return result

    def list_tools(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())

    def list_categories(self) -> List[str]:
        """列出所有分类"""
        return list(self._categories.keys())

    def get_all(self) -> List[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())

    def remove(self, name: str) -> bool:
        """移除工具"""
        if name not in self._tools:
            return False
        
        # 从分类中移除
        metadata = self._metadata.get(name)
        if metadata and metadata.category in self._categories:
            self._categories[metadata.category].remove(name)
        
        del self._tools[name]
        del self._metadata[name]
        
        logger.info(f"Removed tool: {name}")
        return True

    def clear(self) -> None:
        """清除所有工具"""
        self._tools.clear()
        self._metadata.clear()
        self._categories.clear()


def create_tool(
    name: str,
    description: str,
    func: Callable,
    args_schema: Optional[Type[BaseModel]] = None,
    return_direct: bool = False,
) -> BaseTool:
    """
    创建工具的便捷函数
    
    Args:
        name: 工具名称
        description: 工具描述
        func: 工具函数
        args_schema: Pydantic 参数模型
        return_direct: 是否直接返回结果给用户
        
    Returns:
        BaseTool 实例
    """
    # 添加追踪
    @wraps(func)
    def traced_func(*args, **kwargs):
        with tracer.start_span(f"tool.{name}") as span:
            span.set_attribute("tool_name", name)
            span.set_attribute("args", str(kwargs))
            try:
                result = func(*args, **kwargs)
                span.set_attribute("result_length", len(str(result)))
                return result
            except Exception as e:
                span.set_status("ERROR", str(e))
                raise

    @wraps(func)
    async def traced_async_func(*args, **kwargs):
        with tracer.start_span(f"tool.{name}") as span:
            span.set_attribute("tool_name", name)
            span.set_attribute("args", str(kwargs))
            try:
                result = await func(*args, **kwargs)
                span.set_attribute("result_length", len(str(result)))
                return result
            except Exception as e:
                span.set_status("ERROR", str(e))
                raise

    if asyncio.iscoroutinefunction(func):
        wrapped_func = traced_async_func
    else:
        wrapped_func = traced_func

    return StructuredTool.from_function(
        func=wrapped_func,
        name=name,
        description=description,
        args_schema=args_schema,
        return_direct=return_direct,
    )


# ============ 内置工具 ============

# --- 计算器工具 ---

class CalculatorInput(BaseModel):
    """计算器输入"""
    expression: str = Field(description="数学表达式，如 '2 + 2' 或 'sqrt(16)'")


def calculator(expression: str) -> str:
    """
    执行数学计算
    
    支持: +, -, *, /, **, sqrt, sin, cos, tan, log, abs, round 等
    """
    # 安全的数学函数
    safe_dict = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
    }
    
    try:
        # 清理表达式
        expression = expression.strip()
        
        # 安全执行
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return str(result)
    except Exception as e:
        return f"计算错误: {str(e)}"


calculator_tool = create_tool(
    name="calculator",
    description="执行数学计算。支持基本运算和数学函数如 sqrt, sin, cos, log 等。",
    func=calculator,
    args_schema=CalculatorInput,
)


# --- 时间工具 ---

class DateTimeInput(BaseModel):
    """日期时间输入"""
    timezone: str = Field(default="UTC", description="时区名称，如 'UTC', 'Asia/Shanghai'")
    format: str = Field(default="%Y-%m-%d %H:%M:%S", description="日期格式")


def get_current_datetime(timezone: str = "UTC", format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前日期时间"""
    from datetime import timezone as tz
    import zoneinfo
    
    try:
        if timezone == "UTC":
            tz_obj = tz.utc
        else:
            tz_obj = zoneinfo.ZoneInfo(timezone)
        
        now = datetime.now(tz_obj)
        return now.strftime(format)
    except Exception as e:
        return f"获取时间错误: {str(e)}"


datetime_tool = create_tool(
    name="get_current_datetime",
    description="获取当前日期和时间。可以指定时区和输出格式。",
    func=get_current_datetime,
    args_schema=DateTimeInput,
)


# --- Web 搜索工具 (模拟) ---

class WebSearchInput(BaseModel):
    """Web 搜索输入"""
    query: str = Field(description="搜索查询词")
    num_results: int = Field(default=5, description="返回结果数量")


async def web_search(query: str, num_results: int = 5) -> str:
    """
    Web 搜索 (需要配置搜索 API)
    
    注意: 这是一个示例实现，实际使用需要配置搜索 API
    """
    # 这里可以集成真实的搜索 API，如 Google, Bing, DuckDuckGo 等
    # 当前返回模拟结果
    return json.dumps({
        "query": query,
        "message": "Web 搜索功能需要配置搜索 API。请在配置中设置 SEARCH_API_KEY。",
        "results": [],
    }, ensure_ascii=False)


web_search_tool = create_tool(
    name="web_search",
    description="在互联网上搜索信息。需要配置搜索 API 才能使用。",
    func=web_search,
    args_schema=WebSearchInput,
)


# --- HTTP 请求工具 ---

class HttpRequestInput(BaseModel):
    """HTTP 请求输入"""
    url: str = Field(description="请求 URL")
    method: str = Field(default="GET", description="HTTP 方法 (GET, POST, PUT, DELETE)")
    headers: Optional[Dict[str, str]] = Field(default=None, description="请求头")
    body: Optional[str] = Field(default=None, description="请求体 (JSON 字符串)")
    timeout: int = Field(default=30, description="超时时间（秒）")


async def http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
    timeout: int = 30,
) -> str:
    """执行 HTTP 请求"""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            kwargs = {
                "method": method.upper(),
                "url": url,
                "headers": headers or {},
            }
            
            if body and method.upper() in ["POST", "PUT", "PATCH"]:
                kwargs["content"] = body
                if "Content-Type" not in (headers or {}):
                    kwargs["headers"]["Content-Type"] = "application/json"
            
            response = await client.request(**kwargs)
            
            return json.dumps({
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text[:5000],  # 限制响应长度
            }, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "error_type": type(e).__name__,
        }, ensure_ascii=False)


http_request_tool = create_tool(
    name="http_request",
    description="执行 HTTP 请求。支持 GET, POST, PUT, DELETE 方法。",
    func=http_request,
    args_schema=HttpRequestInput,
)


# --- JSON 处理工具 ---

class JsonParseInput(BaseModel):
    """JSON 解析输入"""
    json_string: str = Field(description="JSON 字符串")
    path: Optional[str] = Field(default=None, description="JSONPath 表达式，如 '$.data.items[0].name'")


def json_parse(json_string: str, path: Optional[str] = None) -> str:
    """解析 JSON 并可选地提取特定路径的值"""
    try:
        data = json.loads(json_string)
        
        if path:
            # 简单的路径解析 (不使用完整的 JSONPath 库)
            parts = path.replace("$.", "").split(".")
            result = data
            
            for part in parts:
                # 处理数组索引 [0]
                if "[" in part:
                    key = part[:part.index("[")]
                    index = int(part[part.index("[") + 1 : part.index("]")])
                    if key:
                        result = result[key]
                    result = result[index]
                else:
                    result = result[part]
            
            return json.dumps(result, ensure_ascii=False, indent=2)
        
        return json.dumps(data, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"JSON 解析错误: {str(e)}"


json_parse_tool = create_tool(
    name="json_parse",
    description="解析 JSON 字符串，可选地使用简单路径提取特定值。",
    func=json_parse,
    args_schema=JsonParseInput,
)


# --- 文本处理工具 ---

class TextProcessInput(BaseModel):
    """文本处理输入"""
    text: str = Field(description="要处理的文本")
    operation: str = Field(
        description="操作类型: 'word_count' (字数统计), 'char_count' (字符统计), "
                    "'summarize_stats' (统计摘要), 'extract_urls' (提取URL), "
                    "'extract_emails' (提取邮箱)"
    )


def text_process(text: str, operation: str) -> str:
    """文本处理"""
    import re
    
    try:
        if operation == "word_count":
            # 英文按空格分，中文按字符
            words = len(text.split())
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            return f"英文单词数: {words}, 中文字符数: {chinese_chars}"
        
        elif operation == "char_count":
            return f"总字符数: {len(text)}, 不含空格: {len(text.replace(' ', ''))}"
        
        elif operation == "summarize_stats":
            lines = text.count('\n') + 1
            words = len(text.split())
            chars = len(text)
            return f"行数: {lines}, 单词数: {words}, 字符数: {chars}"
        
        elif operation == "extract_urls":
            urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
            return json.dumps(urls, ensure_ascii=False)
        
        elif operation == "extract_emails":
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            return json.dumps(emails, ensure_ascii=False)
        
        else:
            return f"未知操作: {operation}"
            
    except Exception as e:
        return f"文本处理错误: {str(e)}"


text_process_tool = create_tool(
    name="text_process",
    description="文本处理工具。支持字数统计、提取URL、提取邮箱等操作。",
    func=text_process,
    args_schema=TextProcessInput,
)


# ============ 全局注册器和便捷函数 ============

# 全局工具注册器
tool_registry = ToolRegistry()


def register_builtin_tools(registry: Optional[ToolRegistry] = None) -> None:
    """注册所有内置工具"""
    reg = registry or tool_registry
    
    reg.register(calculator_tool, category="math", tags=["calculation", "math"])
    reg.register(datetime_tool, category="utility", tags=["time", "date"])
    reg.register(web_search_tool, category="search", tags=["web", "search"])
    reg.register(http_request_tool, category="network", tags=["http", "api"])
    reg.register(json_parse_tool, category="utility", tags=["json", "parse"])
    reg.register(text_process_tool, category="utility", tags=["text", "process"])
    
    logger.info(f"Registered {len(reg.list_tools())} builtin tools")


def get_tools(
    names: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    registry: Optional[ToolRegistry] = None,
) -> List[BaseTool]:
    """
    获取工具列表
    
    Args:
        names: 按名称筛选
        categories: 按分类筛选
        tags: 按标签筛选
        registry: 使用指定注册器，默认为全局注册器
        
    Returns:
        工具列表
    """
    reg = registry or tool_registry
    
    if names:
        return [reg.get(name) for name in names if reg.get(name)]
    
    if categories:
        tools = []
        for category in categories:
            tools.extend(reg.get_by_category(category))
        return tools
    
    if tags:
        return reg.get_by_tags(tags)
    
    return reg.get_all()


__all__ = [
    # 元数据
    "ToolMetadata",
    # 注册器
    "ToolRegistry",
    # 工具创建
    "create_tool",
    # 内置工具
    "calculator_tool",
    "datetime_tool",
    "web_search_tool",
    "http_request_tool",
    "json_parse_tool",
    "text_process_tool",
    # 便捷函数
    "register_builtin_tools",
    "get_tools",
    # 全局实例
    "tool_registry",
]
