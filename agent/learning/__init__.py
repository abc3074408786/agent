"""
渐进学习系统 - Progressive Learning System

Agent 从用户的行为和反馈中自动学习偏好，越用越懂用户：
- 观察用户修改了什么、拒绝了什么
- 提取偏好规则（命名风格、代码习惯、工作流偏好）
- 持久化存储偏好
- 自动注入到系统提示中
"""

import ast
import asyncio
import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# Preference 数据类
# =============================================================================

VALID_CATEGORIES = (
    "coding_style",
    "naming",
    "testing",
    "workflow",
    "tools",
    "communication",
)


@dataclass
class Preference:
    """用户偏好数据类"""

    category: str  # coding_style, naming, testing, workflow, tools, communication
    rule: str  # 具体规则描述
    confidence: float = 0.5  # 0.0-1.0, 越高越确定
    evidence: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_seen_at: str = field(default_factory=lambda: datetime.now().isoformat())
    occurrence_count: int = 1  # 出现次数

    def __post_init__(self):
        """验证字段"""
        if self.category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category: {self.category}. "
                f"Must be one of {VALID_CATEGORIES}"
            )
        self.confidence = max(0.0, min(1.0, self.confidence))

    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Preference":
        """从字典创建"""
        return cls(
            category=data["category"],
            rule=data["rule"],
            confidence=data.get("confidence", 0.5),
            evidence=data.get("evidence", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_seen_at=data.get("last_seen_at", datetime.now().isoformat()),
            occurrence_count=data.get("occurrence_count", 1),
        )

    def matches(self, other: "Preference") -> bool:
        """判断两个偏好是否描述同一规则"""
        return self.category == other.category and self.rule == other.rule


# =============================================================================
# PreferenceStore - 持久化存储
# =============================================================================


class PreferenceStore:
    """
    偏好持久化存储

    存储位置: ~/.agent/preferences/ (按项目分文件)
    - global.json: 全局偏好
    - {project_id}.json: 项目级偏好
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self._base_dir = Path(base_dir)
        else:
            self._base_dir = Path.home() / ".agent" / "preferences"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def save(self, project_id: str, preferences: List[Preference]) -> None:
        """保存偏好到文件"""
        file_path = self._base_dir / f"{project_id}.json"
        data = [p.to_dict() for p in preferences]
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(preferences)} preferences for '{project_id}'")
        except OSError as e:
            logger.error(f"Failed to save preferences for '{project_id}': {e}")

    def load(self, project_id: str) -> List[Preference]:
        """加载偏好"""
        file_path = self._base_dir / f"{project_id}.json"
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [Preference.from_dict(item) for item in data]
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load preferences for '{project_id}': {e}")
            return []

    def get_global(self) -> List[Preference]:
        """获取全局偏好"""
        return self.load("global")

    def get_project(self, project_id: str) -> List[Preference]:
        """获取项目偏好"""
        return self.load(project_id)

    def merge(self, project_id: str) -> List[Preference]:
        """
        合并全局偏好和项目偏好

        项目级偏好覆盖全局级偏好（相同 category+rule 时以项目级为准）
        """
        global_prefs = self.get_global()
        project_prefs = self.get_project(project_id)

        # 用项目级覆盖全局级
        merged: Dict[str, Preference] = {}
        for p in global_prefs:
            key = f"{p.category}::{p.rule}"
            merged[key] = p
        for p in project_prefs:
            key = f"{p.category}::{p.rule}"
            merged[key] = p  # 项目级覆盖

        return list(merged.values())

    def delete(self, project_id: str) -> bool:
        """删除项目偏好文件"""
        file_path = self._base_dir / f"{project_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_projects(self) -> List[str]:
        """列出所有有偏好的项目"""
        projects = []
        for f in self._base_dir.glob("*.json"):
            projects.append(f.stem)
        return projects



# =============================================================================
# 内置偏好检测器
# =============================================================================


def detect_naming_style(code: str) -> Optional[str]:
    """
    检测代码中的命名风格

    Returns:
        "snake_case" | "camelCase" | "PascalCase" | "mixed" | None
    """
    # 提取标识符
    identifiers: List[str] = []

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                identifiers.append(node.name)
            elif isinstance(node, ast.Name):
                identifiers.append(node.id)
            elif isinstance(node, ast.arg):
                identifiers.append(node.arg)
    except SyntaxError:
        # 退回到正则匹配
        identifiers = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", code)

    if not identifiers:
        return None

    # 过滤掉内置名和单字符
    filtered = [
        name
        for name in identifiers
        if len(name) > 1
        and not name.startswith("__")
        and name not in ("self", "cls", "True", "False", "None")
    ]

    if not filtered:
        return None

    snake_count = 0
    camel_count = 0
    pascal_count = 0

    for name in filtered:
        if "_" in name and name == name.lower():
            snake_count += 1
        elif name[0].islower() and any(c.isupper() for c in name[1:]):
            camel_count += 1
        elif name[0].isupper() and any(c.islower() for c in name):
            pascal_count += 1

    total = snake_count + camel_count + pascal_count
    if total == 0:
        return None

    if snake_count / total > 0.7:
        return "snake_case"
    elif camel_count / total > 0.7:
        return "camelCase"
    elif pascal_count / total > 0.7:
        return "PascalCase"
    else:
        return "mixed"


def detect_indentation(code: str) -> Optional[str]:
    """
    检测代码缩进风格

    Returns:
        "2_spaces" | "4_spaces" | "tabs" | None
    """
    lines = code.split("\n")
    indent_counts = {"2_spaces": 0, "4_spaces": 0, "tabs": 0}

    for line in lines:
        if not line or line.isspace():
            continue
        # 计算缩进
        stripped = line.lstrip()
        if stripped == line:
            continue  # 无缩进

        indent = line[: len(line) - len(stripped)]
        if "\t" in indent:
            indent_counts["tabs"] += 1
        elif len(indent) % 4 == 0:
            indent_counts["4_spaces"] += 1
        elif len(indent) % 2 == 0:
            indent_counts["2_spaces"] += 1

    total = sum(indent_counts.values())
    if total == 0:
        return None

    # 找到占比最高的
    max_style = max(indent_counts, key=indent_counts.get)
    if indent_counts[max_style] / total > 0.6:
        return max_style
    return None


def detect_docstring_style(code: str) -> Optional[str]:
    """
    检测 docstring 风格

    Returns:
        "google" | "numpy" | "restructuredtext" | "simple" | None
    """
    # 提取 docstring
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    docstrings: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            docstring = ast.get_docstring(node)
            if docstring:
                docstrings.append(docstring)

    if not docstrings:
        return None

    # 分析风格
    google_patterns = [r"^\s*(Args|Returns|Raises|Yields|Examples|Note|Attributes)\s*:", ]
    numpy_patterns = [r"^\s*(Parameters|Returns|Raises|See Also|Examples)\s*\n\s*-+"]
    rst_patterns = [r"^\s*:(param|type|returns|rtype|raises)\s+"]

    google_score = 0
    numpy_score = 0
    rst_score = 0

    for doc in docstrings:
        for pattern in google_patterns:
            if re.search(pattern, doc, re.MULTILINE):
                google_score += 1
        for pattern in numpy_patterns:
            if re.search(pattern, doc, re.MULTILINE):
                numpy_score += 1
        for pattern in rst_patterns:
            if re.search(pattern, doc, re.MULTILINE):
                rst_score += 1

    if google_score == 0 and numpy_score == 0 and rst_score == 0:
        return "simple"

    scores = {"google": google_score, "numpy": numpy_score, "restructuredtext": rst_score}
    return max(scores, key=scores.get)


def detect_import_style(code: str) -> Optional[str]:
    """
    检测 import 风格

    Returns:
        "absolute" | "relative" | "from_import" | "direct_import" | "mixed" | None
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    from_imports = 0
    direct_imports = 0
    relative_imports = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level > 0:
                relative_imports += 1
            else:
                from_imports += 1
        elif isinstance(node, ast.Import):
            direct_imports += 1

    total = from_imports + direct_imports + relative_imports
    if total == 0:
        return None

    if relative_imports / total > 0.5:
        return "relative"
    elif from_imports / total > 0.7:
        return "from_import"
    elif direct_imports / total > 0.7:
        return "direct_import"
    else:
        return "mixed"


def detect_explicit_preferences(text: str) -> List[Preference]:
    """
    从自然语言提取显式偏好

    检测模式:
    - "我喜欢..." / "I prefer..."
    - "不要用..." / "Don't use..."
    - "总是..." / "Always..."
    - "从不..." / "Never..."
    """
    preferences: List[Preference] = []

    # 中文模式
    cn_patterns = [
        (r"我喜欢(.+?)(?:[。，；\n]|$)", "positive"),
        (r"我偏好(.+?)(?:[。，；\n]|$)", "positive"),
        (r"我习惯(.+?)(?:[。，；\n]|$)", "positive"),
        (r"请用(.+?)(?:[。，；\n]|$)", "positive"),
        (r"不要用(.+?)(?:[。，；\n]|$)", "negative"),
        (r"不要(.+?)(?:[。，；\n]|$)", "negative"),
        (r"别用(.+?)(?:[。，；\n]|$)", "negative"),
        (r"总是(.+?)(?:[。，；\n]|$)", "positive"),
        (r"从不(.+?)(?:[。，；\n]|$)", "negative"),
        (r"永远不要(.+?)(?:[。，；\n]|$)", "negative"),
    ]

    # 英文模式
    en_patterns = [
        (r"I (?:like|prefer|want)\s+(.+?)(?:[.\n]|$)", "positive"),
        (r"(?:don't|do not|never)\s+use\s+(.+?)(?:[.\n]|$)", "negative"),
        (r"always\s+(.+?)(?:[.\n]|$)", "positive"),
        (r"never\s+(.+?)(?:[.\n]|$)", "negative"),
        (r"please\s+use\s+(.+?)(?:[.\n]|$)", "positive"),
    ]

    all_patterns = cn_patterns + en_patterns

    for pattern, sentiment in all_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            content = match.group(1).strip()
            if len(content) < 2 or len(content) > 200:
                continue

            # 推断 category
            category = _infer_category(content)

            if sentiment == "negative":
                rule = f"避免: {content}"
            else:
                rule = content

            pref = Preference(
                category=category,
                rule=rule,
                confidence=0.8,  # 显式声明的偏好起始信心较高
                evidence=[f"用户显式声明: '{match.group(0).strip()}'"],
            )
            preferences.append(pref)

    return preferences


def _infer_category(text: str) -> str:
    """根据文本内容推断偏好类别"""
    text_lower = text.lower()

    naming_keywords = [
        "命名", "变量名", "函数名", "snake", "camel", "pascal",
        "naming", "variable", "function name",
    ]
    coding_keywords = [
        "缩进", "空格", "tab", "格式", "风格", "indent",
        "format", "style", "space", "bracket", "brace",
        "docstring", "注释", "comment", "type hint",
    ]
    testing_keywords = [
        "测试", "test", "pytest", "unittest", "mock", "assert",
        "coverage", "tdd",
    ]
    workflow_keywords = [
        "git", "commit", "branch", "pr", "review", "deploy",
        "ci", "cd", "workflow",
    ]
    tools_keywords = [
        "工具", "编辑器", "ide", "vim", "vscode", "tool",
        "plugin", "extension", "package",
    ]

    if any(kw in text_lower for kw in naming_keywords):
        return "naming"
    elif any(kw in text_lower for kw in testing_keywords):
        return "testing"
    elif any(kw in text_lower for kw in workflow_keywords):
        return "workflow"
    elif any(kw in text_lower for kw in tools_keywords):
        return "tools"
    elif any(kw in text_lower for kw in coding_keywords):
        return "coding_style"
    else:
        return "coding_style"  # 默认归类



# =============================================================================
# PreferenceLearner - 从用户行为学习偏好
# =============================================================================


class PreferenceLearner:
    """
    偏好学习器

    从用户行为中自动提取偏好:
    - learn_from_edit: 从代码修改中学习
    - learn_from_rejection: 从拒绝中学习
    - learn_from_conversation: 从对话中学习
    """

    def __init__(self, store: Optional[PreferenceStore] = None):
        self._store = store or PreferenceStore()
        self._current_preferences: List[Preference] = []

    @property
    def store(self) -> PreferenceStore:
        return self._store

    @property
    def preferences(self) -> List[Preference]:
        return self._current_preferences

    def learn_from_edit(
        self, original_code: str, user_modified_code: str
    ) -> List[Preference]:
        """
        从用户修改中学习偏好

        检测:
        - 命名风格变化 (snake_case vs camelCase)
        - 缩进变化 (2 vs 4 spaces vs tabs)
        - import 风格变化
        - docstring 风格变化
        """
        learned: List[Preference] = []

        # 1. 检测命名风格变化
        orig_naming = detect_naming_style(original_code)
        new_naming = detect_naming_style(user_modified_code)
        if orig_naming and new_naming and orig_naming != new_naming:
            pref = Preference(
                category="naming",
                rule=f"使用 {new_naming} 命名风格",
                confidence=0.6,
                evidence=[
                    f"用户将 {orig_naming} 修改为 {new_naming}"
                ],
            )
            learned.append(pref)

        # 2. 检测缩进变化
        orig_indent = detect_indentation(original_code)
        new_indent = detect_indentation(user_modified_code)
        if orig_indent and new_indent and orig_indent != new_indent:
            pref = Preference(
                category="coding_style",
                rule=f"使用 {new_indent} 缩进",
                confidence=0.7,
                evidence=[
                    f"用户将缩进从 {orig_indent} 修改为 {new_indent}"
                ],
            )
            learned.append(pref)

        # 3. 检测 import 风格变化
        orig_import = detect_import_style(original_code)
        new_import = detect_import_style(user_modified_code)
        if orig_import and new_import and orig_import != new_import:
            pref = Preference(
                category="coding_style",
                rule=f"使用 {new_import} import 风格",
                confidence=0.5,
                evidence=[
                    f"用户将 import 风格从 {orig_import} 修改为 {new_import}"
                ],
            )
            learned.append(pref)

        # 4. 检测 docstring 风格变化
        orig_doc = detect_docstring_style(original_code)
        new_doc = detect_docstring_style(user_modified_code)
        if orig_doc and new_doc and orig_doc != new_doc:
            pref = Preference(
                category="coding_style",
                rule=f"使用 {new_doc} 风格的 docstring",
                confidence=0.6,
                evidence=[
                    f"用户将 docstring 风格从 {orig_doc} 修改为 {new_doc}"
                ],
            )
            learned.append(pref)

        # 更新到当前偏好列表
        for pref in learned:
            self._merge_preference(pref)

        logger.info(f"Learned {len(learned)} preferences from edit")
        return learned

    def learn_from_rejection(
        self, agent_output: str, user_feedback: str
    ) -> List[Preference]:
        """
        从用户拒绝中学习

        当用户说 "不对" / "别这样" / "我不喜欢这个" 时,
        记录 agent 输出的特征作为反面教材
        """
        learned: List[Preference] = []

        # 从 feedback 提取显式偏好
        explicit_prefs = detect_explicit_preferences(user_feedback)
        learned.extend(explicit_prefs)

        # 分析 agent 输出的代码风格 (作为负面例子)
        if agent_output and _looks_like_code(agent_output):
            naming = detect_naming_style(agent_output)
            if naming:
                pref = Preference(
                    category="naming",
                    rule=f"避免: {naming} 命名风格 (用户拒绝了此风格)",
                    confidence=0.4,
                    evidence=[
                        f"用户拒绝了包含 {naming} 风格的输出: '{user_feedback[:100]}'"
                    ],
                )
                learned.append(pref)

        # 更新到当前偏好列表
        for pref in learned:
            self._merge_preference(pref)

        logger.info(f"Learned {len(learned)} preferences from rejection")
        return learned

    def learn_from_conversation(
        self, messages: List[Dict[str, str]]
    ) -> List[Preference]:
        """
        从对话中提取显式偏好

        扫描用户消息, 寻找 "我喜欢..." / "不要用..." / "总是..." 等模式
        """
        learned: List[Preference] = []

        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if not content:
                continue

            explicit_prefs = detect_explicit_preferences(content)
            learned.extend(explicit_prefs)

        # 更新到当前偏好列表
        for pref in learned:
            self._merge_preference(pref)

        logger.info(f"Learned {len(learned)} preferences from conversation")
        return learned

    def update_confidence(self, preference: Preference) -> None:
        """
        每次再次观察到时增加置信度

        增长公式: confidence += 0.1 * (1 - confidence)
        确保不超过 1.0, 且增长越来越慢
        """
        preference.confidence += 0.1 * (1.0 - preference.confidence)
        preference.confidence = min(1.0, preference.confidence)
        preference.last_seen_at = datetime.now().isoformat()
        preference.occurrence_count += 1

    def decay_confidence(self, preferences: Optional[List[Preference]] = None) -> None:
        """
        长时间未见的偏好降低置信度

        衰减规则: 每天未见降低 0.01, 最低到 0.1
        """
        prefs = preferences if preferences is not None else self._current_preferences
        now = datetime.now()

        for pref in prefs:
            try:
                last_seen = datetime.fromisoformat(pref.last_seen_at)
            except (ValueError, TypeError):
                continue

            days_since = (now - last_seen).days
            if days_since > 0:
                decay = days_since * 0.01
                pref.confidence = max(0.1, pref.confidence - decay)

    def _merge_preference(self, new_pref: Preference) -> None:
        """合并新偏好到当前列表"""
        for existing in self._current_preferences:
            if existing.matches(new_pref):
                # 已存在, 增加置信度
                self.update_confidence(existing)
                # 合并证据
                for ev in new_pref.evidence:
                    if ev not in existing.evidence:
                        existing.evidence.append(ev)
                        # 限制证据数量
                        if len(existing.evidence) > 10:
                            existing.evidence = existing.evidence[-10:]
                return

        # 新偏好, 添加到列表
        self._current_preferences.append(new_pref)

    def load_project(self, project_id: str) -> None:
        """加载项目偏好"""
        self._current_preferences = self._store.merge(project_id)

    def save_project(self, project_id: str) -> None:
        """保存当前偏好到项目"""
        # 分离全局和项目偏好
        self._store.save(project_id, self._current_preferences)

    def get_high_confidence(self, threshold: float = 0.5) -> List[Preference]:
        """获取高置信度偏好"""
        return [p for p in self._current_preferences if p.confidence > threshold]


def _looks_like_code(text: str) -> bool:
    """简单判断文本是否看起来像代码"""
    code_indicators = [
        "def ", "class ", "import ", "from ",
        "if ", "for ", "while ", "return ",
        "function ", "const ", "let ", "var ",
        "{", "}", "=>", "->",
    ]
    indicator_count = sum(1 for ind in code_indicators if ind in text)
    return indicator_count >= 2



# =============================================================================
# PreferenceInjector - 偏好注入系统提示
# =============================================================================


class PreferenceInjector:
    """
    将学习到的偏好注入系统提示

    只注入 confidence > 0.5 的偏好
    格式化为 "用户偏好规则" section
    """

    DEFAULT_THRESHOLD = 0.5
    SECTION_HEADER = "\n\n## 用户偏好规则\n"
    SECTION_FOOTER = "\n"

    def __init__(self, threshold: float = 0.5):
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        self._threshold = max(0.0, min(1.0, value))

    def inject(
        self, system_prompt: str, preferences: List[Preference]
    ) -> str:
        """
        把偏好注入系统提示

        Args:
            system_prompt: 原始系统提示
            preferences: 偏好列表

        Returns:
            注入偏好后的系统提示
        """
        # 过滤低置信度偏好
        high_conf = [p for p in preferences if p.confidence > self._threshold]

        if not high_conf:
            return system_prompt

        # 按 category 分组
        grouped: Dict[str, List[Preference]] = {}
        for pref in high_conf:
            grouped.setdefault(pref.category, []).append(pref)

        # 构建偏好 section
        lines = [self.SECTION_HEADER]
        lines.append("以下是从用户行为中学习到的偏好，请在生成代码时遵循：\n")

        category_names = {
            "coding_style": "代码风格",
            "naming": "命名规范",
            "testing": "测试习惯",
            "workflow": "工作流程",
            "tools": "工具偏好",
            "communication": "沟通偏好",
        }

        for category, prefs in sorted(grouped.items()):
            display_name = category_names.get(category, category)
            lines.append(f"\n### {display_name}")
            # 按置信度降序排列
            sorted_prefs = sorted(prefs, key=lambda p: p.confidence, reverse=True)
            for pref in sorted_prefs:
                confidence_bar = self._confidence_indicator(pref.confidence)
                lines.append(f"- {confidence_bar} {pref.rule}")

        lines.append(self.SECTION_FOOTER)
        preference_section = "\n".join(lines)

        return system_prompt + preference_section

    def format_preferences_summary(self, preferences: List[Preference]) -> str:
        """格式化偏好摘要（用于调试/展示）"""
        high_conf = [p for p in preferences if p.confidence > self._threshold]
        if not high_conf:
            return "暂无学习到的偏好"

        lines = [f"已学习 {len(high_conf)} 条偏好规则:\n"]
        for pref in sorted(high_conf, key=lambda p: p.confidence, reverse=True):
            lines.append(
                f"  [{pref.category}] {pref.rule} "
                f"(置信度: {pref.confidence:.0%}, 观察: {pref.occurrence_count}次)"
            )
        return "\n".join(lines)

    @staticmethod
    def _confidence_indicator(confidence: float) -> str:
        """置信度可视化指示"""
        if confidence > 0.9:
            return "[强]"
        elif confidence > 0.7:
            return "[中]"
        else:
            return "[弱]"


# =============================================================================
# LearningHook - 自动学习钩子
# =============================================================================


class LearningHook:
    """
    学习钩子 - 注册为 HookManager 的 post_query hook

    每次对话后自动触发学习, 不阻塞主流程（后台异步执行）
    """

    def __init__(
        self,
        learner: Optional[PreferenceLearner] = None,
        project_id: str = "global",
    ):
        self._learner = learner or PreferenceLearner()
        self._project_id = project_id
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def learner(self) -> PreferenceLearner:
        return self._learner

    @property
    def project_id(self) -> str:
        return self._project_id

    @project_id.setter
    def project_id(self, value: str) -> None:
        self._project_id = value

    def register(self, hook_manager: Any) -> None:
        """
        注册到 HookManager

        尝试注册为 post_query hook
        """
        if hasattr(hook_manager, "register"):
            hook_manager.register("post_query", self._on_post_query)
            logger.info("LearningHook registered as post_query hook")
        elif hasattr(hook_manager, "add_hook"):
            hook_manager.add_hook("post_query", self._on_post_query)
            logger.info("LearningHook registered via add_hook")
        else:
            logger.warning(
                "HookManager does not support register() or add_hook(), "
                "LearningHook not registered"
            )

    async def _on_post_query(self, context: Dict[str, Any]) -> None:
        """
        post_query 回调 - 后台异步执行学习

        context 期望包含:
        - messages: List[Dict] 对话历史
        - original_code: Optional[str] 原始代码
        - modified_code: Optional[str] 修改后代码
        - rejected: Optional[bool] 是否被拒绝
        - agent_output: Optional[str] agent 输出
        - user_feedback: Optional[str] 用户反馈
        """
        # 后台执行, 不阻塞主流程
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._learn_sync, context
            )
        except Exception as e:
            logger.error(f"LearningHook background learning failed: {e}")

    def _learn_sync(self, context: Dict[str, Any]) -> None:
        """同步学习逻辑（在后台线程执行）"""
        try:
            # 1. 从对话中学习
            messages = context.get("messages", [])
            if messages:
                self._learner.learn_from_conversation(messages)

            # 2. 从编辑中学习
            original = context.get("original_code")
            modified = context.get("modified_code")
            if original and modified and original != modified:
                self._learner.learn_from_edit(original, modified)

            # 3. 从拒绝中学习
            if context.get("rejected"):
                agent_output = context.get("agent_output", "")
                feedback = context.get("user_feedback", "")
                if agent_output or feedback:
                    self._learner.learn_from_rejection(agent_output, feedback)

            # 4. 衰减置信度
            self._learner.decay_confidence()

            # 5. 保存
            self._learner.save_project(self._project_id)

            logger.debug(
                f"Background learning completed. "
                f"Total preferences: {len(self._learner.preferences)}"
            )
        except Exception as e:
            logger.error(f"Background learning error: {e}")

    def trigger_manual(self, context: Dict[str, Any]) -> List[Preference]:
        """
        手动触发学习（同步，用于测试）

        Returns:
            当前所有偏好
        """
        self._learn_sync(context)
        return self._learner.preferences

    def get_injectable_preferences(self) -> List[Preference]:
        """获取可注入的偏好（confidence > 0.5）"""
        return self._learner.get_high_confidence(threshold=0.5)


# =============================================================================
# 便捷工厂函数
# =============================================================================


def create_learning_system(
    project_id: str = "global",
    base_dir: Optional[str] = None,
) -> Tuple[PreferenceLearner, PreferenceInjector, LearningHook]:
    """
    创建完整学习系统的便捷工厂函数

    Args:
        project_id: 项目标识符
        base_dir: 偏好存储目录 (默认 ~/.agent/preferences/)

    Returns:
        (learner, injector, hook) 三元组
    """
    store = PreferenceStore(base_dir=base_dir)
    learner = PreferenceLearner(store=store)
    learner.load_project(project_id)

    injector = PreferenceInjector()
    hook = LearningHook(learner=learner, project_id=project_id)

    logger.info(
        f"Learning system created for project '{project_id}' "
        f"with {len(learner.preferences)} existing preferences"
    )

    return learner, injector, hook


# =============================================================================
# 模块导出
# =============================================================================

__all__ = [
    # 数据类
    "Preference",
    "VALID_CATEGORIES",
    # 存储
    "PreferenceStore",
    # 学习器
    "PreferenceLearner",
    # 注入器
    "PreferenceInjector",
    # 钩子
    "LearningHook",
    # 检测器
    "detect_naming_style",
    "detect_indentation",
    "detect_docstring_style",
    "detect_import_style",
    "detect_explicit_preferences",
    # 工厂
    "create_learning_system",
]
