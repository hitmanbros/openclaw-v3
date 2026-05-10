"""Tests for real tool implementations (not mocked)."""

import pytest
import tempfile
from pathlib import Path

from openclaw.tools.fs import read_tool, edit_tool, write_tool
from openclaw.tools.search import grep_tool, find_tool, ls_tool
from openclaw.tools.bash import bash_tool


class TestReadTool:
    """read tool behavior."""

    def test_reads_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("line 1\nline 2\nline 3\n")
            path = f.name
        
        result = read_tool(path=path)
        assert "line 1" in result
        assert "line 2" in result
        
        Path(path).unlink()

    def test_reads_with_offset_limit(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            for i in range(20):
                f.write(f"line {i}\n")
            path = f.name
        
        result = read_tool(path=path, offset=5, limit=3)
        lines = result.strip().split("\n")
        assert len(lines) == 3
        assert "line 4" in lines[0]
        
        Path(path).unlink()

    def test_blocks_sensitive_files(self):
        with pytest.raises(PermissionError):
            read_tool(path="~/.ssh/id_rsa")

    def test_blocks_outside_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            with pytest.raises(ValueError):
                read_tool(path="/etc/passwd", workspace=workspace)


class TestWriteTool:
    """write tool behavior."""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.py"
            write_tool(path=str(path), content="hello world")
            assert path.read_text() == "hello world"

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "a" / "b" / "c.py"
            write_tool(path=str(path), content="x")
            assert path.exists()

    def test_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "file.py"
            path.write_text("old")
            write_tool(path=str(path), content="new")
            assert path.read_text() == "new"


class TestEditTool:
    """edit tool behavior."""

    def test_replaces_text(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "file.py"
            path.write_text("def old(): pass")
            edit_tool(path=str(path), oldText="def old(): pass", newText="def new(): pass")
            assert "def new(): pass" in path.read_text()

    def test_requires_exact_match(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "file.py"
            path.write_text("def old(): pass")
            with pytest.raises(ValueError):
                edit_tool(path=str(path), oldText="def wrong(): pass", newText="def new(): pass")

    def test_batch_edits(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "file.py"
            path.write_text("a\nb\nc")
            edits = [
                {"oldText": "a", "newText": "x"},
                {"oldText": "c", "newText": "z"},
            ]
            edit_tool(path=str(path), edits=edits)
            content = path.read_text()
            assert "x" in content
            assert "z" in content
            assert "a" not in content
            assert "c" not in content


class TestGrepTool:
    """grep tool behavior."""

    def test_finds_pattern(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "file.py"
            path.write_text("def hello():\n    pass\ndef world():\n    pass")
            result = grep_tool(path=str(d), pattern="def ")
            assert "hello" in result
            assert "world" in result

    def test_no_match_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "file.py"
            path.write_text("hello")
            result = grep_tool(path=str(d), pattern="xyz")
            assert result == "" or "no matches" in result.lower()


class TestFindTool:
    """find tool behavior."""

    def test_finds_by_pattern(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.py").write_text("x")
            (Path(d) / "b.txt").write_text("x")
            result = find_tool(path=str(d), pattern="*.py")
            assert "a.py" in result
            assert "b.txt" not in result


class TestLsTool:
    """ls tool behavior."""

    def test_lists_directory(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "file1.py").write_text("x")
            (Path(d) / "file2.py").write_text("x")
            result = ls_tool(path=str(d))
            assert "file1.py" in result
            assert "file2.py" in result


class TestBashTool:
    """bash tool behavior."""

    def test_runs_allowed_command(self):
        result = bash_tool(command="echo hello", workspace="/tmp")
        assert "hello" in result["stdout"]
        assert result["returncode"] == 0

    def test_blocks_disallowed_command(self):
        with pytest.raises(PermissionError):
            bash_tool(command="rm -rf /", workspace="/tmp")

    def test_blocks_curl(self):
        with pytest.raises(PermissionError):
            bash_tool(command="curl https://example.com", workspace="/tmp")

    def test_blocks_ssh(self):
        with pytest.raises(PermissionError):
            bash_tool(command="ssh root@host", workspace="/tmp")

    def test_timeout_kills_long_command(self):
        with pytest.raises(TimeoutError):
            bash_tool(command="sleep 10", workspace="/tmp", timeout=1)

    def test_returns_stderr(self):
        result = bash_tool(command="python3 -c \"import sys; sys.stderr.write('error')\"", workspace="/tmp")
        assert "error" in result["stderr"]
