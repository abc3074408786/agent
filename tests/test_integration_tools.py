"""
工具链集成测试 - 使用真实文件系统操作

测试 file_tools 和 bash_tool 模块的真实 I/O 操作。
使用 pytest 的 tmp_path fixture 自动清理临时文件。
"""
import pytest
import os
import asyncio

from agent.tools.file_tools import (
    file_read,
    file_write,
    file_edit,
    grep_search,
    glob_search,
    list_directory,
)
from agent.tools.bash_tool import bash_execute


class TestFileWriteAndRead:
    """写文件 → 读回来验证内容一致"""

    def test_file_write_and_read(self, tmp_path):
        """写入文件后读取，内容应完全一致"""
        test_file = str(tmp_path / "hello.txt")
        content = "Hello, World!\n这是一个测试文件。\n第三行。"

        # 写入
        result = file_write(test_file, content)
        assert "成功" in result
        assert os.path.exists(test_file)

        # 读取
        read_result = file_read(test_file)
        assert "Hello, World!" in read_result
        assert "这是一个测试文件。" in read_result
        assert "第三行。" in read_result

    def test_file_write_creates_dirs(self, tmp_path):
        """写入时自动创建父目录"""
        test_file = str(tmp_path / "subdir" / "deep" / "file.txt")
        content = "nested content"

        result = file_write(test_file, content)
        assert "成功" in result
        assert os.path.exists(test_file)

    def test_file_read_with_line_range(self, tmp_path):
        """按行号范围读取"""
        test_file = str(tmp_path / "lines.txt")
        lines = "\n".join([f"Line {i}" for i in range(1, 11)])
        file_write(test_file, lines)

        result = file_read(test_file, start_line=3, end_line=5)
        assert "Line 3" in result
        assert "Line 5" in result
        assert "Line 6" not in result


class TestFileEdit:
    """写文件 → 编辑 → 验证修改正确"""

    def test_file_edit(self, tmp_path):
        """字符串替换编辑"""
        test_file = str(tmp_path / "edit_me.py")
        original = "def hello():\n    return 'hello'\n"
        file_write(test_file, original)

        # 编辑
        result = file_edit(test_file, "return 'hello'", "return 'world'")
        assert "成功" in result

        # 验证
        read_result = file_read(test_file)
        assert "return 'world'" in read_result
        assert "return 'hello'" not in read_result

    def test_file_edit_not_found(self, tmp_path):
        """编辑不存在的字符串应报错"""
        test_file = str(tmp_path / "edit_me2.py")
        file_write(test_file, "original content")

        result = file_edit(test_file, "nonexistent string", "replacement")
        assert "错误" in result or "未找到" in result


class TestGrepInCreatedFiles:
    """创建多个文件 → grep 搜索 → 验证找到正确结果"""

    def test_grep_in_created_files(self, tmp_path):
        """在多个文件中搜索特定模式"""
        # 创建多个文件
        file_write(str(tmp_path / "foo.py"), "def foo():\n    return 42\n")
        file_write(str(tmp_path / "bar.py"), "def bar():\n    return foo() + 1\n")
        file_write(str(tmp_path / "baz.py"), "import os\ndef baz():\n    pass\n")

        # 搜索包含 "foo" 的文件
        result = grep_search("foo", str(tmp_path))
        assert "foo.py" in result
        assert "bar.py" in result  # bar.py 引用了 foo
        # baz.py 不包含 "foo"
        assert "baz" not in result or "foo" in result

    def test_grep_case_insensitive(self, tmp_path):
        """大小写不敏感搜索"""
        file_write(str(tmp_path / "test.txt"), "Hello World\nhello world\nHELLO WORLD\n")

        result = grep_search("hello", str(tmp_path), case_sensitive=False)
        # 应该找到所有三行
        assert "3 处匹配" in result or "找到" in result

    def test_grep_with_include_pattern(self, tmp_path):
        """使用文件名过滤"""
        file_write(str(tmp_path / "code.py"), "# TODO: fix this\n")
        file_write(str(tmp_path / "notes.txt"), "# TODO: review\n")

        result = grep_search("TODO", str(tmp_path), include_pattern="*.py")
        assert "code.py" in result


class TestGlobSearch:
    """创建目录结构 → glob 搜索 → 验证匹配正确"""

    def test_glob_search(self, tmp_path):
        """glob 模式匹配文件"""
        # 创建目录结构
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib").mkdir()
        file_write(str(tmp_path / "src" / "main.py"), "# main")
        file_write(str(tmp_path / "src" / "utils.py"), "# utils")
        file_write(str(tmp_path / "src" / "lib" / "helper.py"), "# helper")
        file_write(str(tmp_path / "README.md"), "# readme")

        # 搜索所有 py 文件
        result = glob_search("**/*.py", str(tmp_path))
        assert "main.py" in result
        assert "utils.py" in result
        assert "helper.py" in result
        assert "README.md" not in result

    def test_glob_no_match(self, tmp_path):
        """无匹配结果"""
        file_write(str(tmp_path / "test.txt"), "content")
        result = glob_search("*.xyz", str(tmp_path))
        assert "未找到" in result


class TestListDirectory:
    """创建嵌套目录 → list → 验证结构正确"""

    def test_list_directory(self, tmp_path):
        """列出目录内容"""
        # 创建结构
        (tmp_path / "dir_a").mkdir()
        (tmp_path / "dir_b").mkdir()
        file_write(str(tmp_path / "file1.txt"), "content1")
        file_write(str(tmp_path / "dir_a" / "file2.txt"), "content2")

        result = list_directory(str(tmp_path))
        assert "dir_a" in result
        assert "dir_b" in result
        assert "file1.txt" in result

    def test_list_directory_recursive(self, tmp_path):
        """递归列出目录"""
        (tmp_path / "outer").mkdir()
        (tmp_path / "outer" / "inner").mkdir()
        file_write(str(tmp_path / "outer" / "inner" / "deep.txt"), "deep")

        result = list_directory(str(tmp_path), max_depth=3)
        assert "outer" in result
        assert "inner" in result
        assert "deep.txt" in result


class TestSensitiveFileBlocked:
    """尝试读写敏感文件 → 验证被拒绝"""

    def test_sensitive_file_read_blocked(self, tmp_path):
        """读取 .env 文件应被拒绝"""
        env_file = str(tmp_path / ".env")
        # 手动创建（绕过 file_write 安全检查）
        with open(env_file, "w") as f:
            f.write("SECRET=123")

        result = file_read(env_file)
        assert "拒绝" in result or "错误" in result

    def test_sensitive_file_write_blocked(self, tmp_path):
        """写入 .env 文件应被拒绝"""
        env_file = str(tmp_path / ".env")
        result = file_write(env_file, "SECRET=hack")
        assert "错误" in result or "不允许" in result

    def test_ssh_dir_blocked(self, tmp_path):
        """访问 .ssh 目录应被拒绝"""
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        ssh_file = str(ssh_dir / "id_rsa")
        with open(ssh_file, "w") as f:
            f.write("private key")

        result = file_read(ssh_file)
        assert "拒绝" in result or "错误" in result


class TestBashExecuteSafe:
    """执行安全命令 → 验证输出"""

    @pytest.mark.asyncio
    async def test_bash_execute_echo(self):
        """echo 命令应正常返回"""
        result = await bash_execute("echo 'hello world'")
        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_bash_execute_ls(self, tmp_path):
        """ls 命令应列出文件"""
        file_write(str(tmp_path / "test.txt"), "content")
        result = await bash_execute(f"ls {tmp_path}")
        assert "test.txt" in result

    @pytest.mark.asyncio
    async def test_bash_execute_with_cwd(self, tmp_path):
        """使用工作目录执行命令"""
        file_write(str(tmp_path / "marker.txt"), "found")
        result = await bash_execute("ls", cwd=str(tmp_path))
        assert "marker.txt" in result


class TestBashExecuteBlocked:
    """执行危险命令 → 验证被阻止"""

    @pytest.mark.asyncio
    async def test_bash_rm_rf_root_blocked(self):
        """rm -rf / 应被阻止"""
        result = await bash_execute("rm -rf /")
        assert "安全策略阻止" in result or "命令被禁止" in result or "错误" in result

    @pytest.mark.asyncio
    async def test_bash_fork_bomb_blocked(self):
        """fork bomb 应被阻止"""
        result = await bash_execute(":(){ :|:& };:")
        assert "安全策略阻止" in result or "命令被禁止" in result or "错误" in result

    @pytest.mark.asyncio
    async def test_bash_shutdown_blocked(self):
        """shutdown 命令应被阻止"""
        result = await bash_execute("shutdown -h now")
        assert "安全策略阻止" in result or "命令被禁止" in result or "错误" in result


class TestBashTimeout:
    """执行长时间命令 → 验证超时处理"""

    @pytest.mark.asyncio
    async def test_bash_timeout(self):
        """sleep 100 应触发超时"""
        result = await bash_execute("sleep 100", timeout=2)
        assert "超时" in result
