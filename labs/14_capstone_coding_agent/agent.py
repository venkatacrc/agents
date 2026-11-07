"""Lab 14 (capstone): a coding agent. A small Claude Code / Cursor agent built from this course's parts.

Run:  python labs/14_capstone_coding_agent/run.py --trace             (your code)
      python labs/14_capstone_coding_agent/run.py --solution --trace
      python labs/14_capstone_coding_agent/run.py --interactive        (you approve each edit)

It works on a copy of toyrepo/, a tiny package with failing tests. Pieces you have built before:
tools with helpful errors (Lab 03), path safety (Lab 11), approvals (Lab 08), compaction (Lab 04),
a todo list (Lab 06), tests as the verifier (Lab 07), all in the loop from Lab 02.
"""
import difflib  # noqa: F401
import pathlib
import re
import subprocess
import sys

from agentlab.loop import run_agent  # noqa: F401
from agentlab.tools import tool

SYSTEM = """You are a coding agent working in a small Python repository.
- Start by writing a todo list with todo_write, and keep it updated as you work.
- Run the tests first to see what is failing. Read code before you change it.
- edit_file replaces one exact, unique snippet of a file: copy the old text exactly, with its indentation,
  and without the line numbers that read_file shows.
- After editing, run the tests again. You are done when they pass; then summarize what you changed."""


def safe_path(root, path):
    """Resolve path under root; raise ValueError if it escapes (../../etc/passwd, /etc/passwd, symlinks).
    Compare resolved paths: root itself or a path whose .parents include root is fine."""
    # TODO 1
    raise NotImplementedError("safe_path")


def apply_edit(text, old, new):
    """Return text with `old` replaced by `new`, only if `old` occurs exactly once.
    0 times  -> ValueError("old text not found in the file. Closest line is N: '...' (check indentation ...)")
                (use difflib.get_close_matches on the stripped first line of `old`; the mock reads this hint)
    >1 times -> ValueError saying how many times, and to include more lines so it is unique."""
    # TODO 2
    raise NotImplementedError("apply_edit")


def make_tools(root, todos):
    """The agent's tools. list_files, read_file, grep and todo_write are written for you; edit_file must use
    safe_path and apply_edit."""
    root = pathlib.Path(root)

    @tool
    def list_files() -> str:
        """List the files in the repository."""
        return "\n".join(sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()
                                and "__pycache__" not in p.parts))

    @tool
    def read_file(path: str) -> str:
        """Read a file, with line numbers.

        Args:
            path: file path relative to the repository root
        """
        lines = safe_path(root, path).read_text().splitlines()
        return "\n".join(f"{i + 1:4}| {line}" for i, line in enumerate(lines))

    @tool
    def grep(pattern: str) -> str:
        """Search all Python files for a regular expression; returns path:line: text.

        Args:
            pattern: a Python regular expression
        """
        rx = re.compile(pattern)
        hits = [f"{p.relative_to(root)}:{i + 1}: {line.strip()}" for p in sorted(root.rglob("*.py"))
                for i, line in enumerate(p.read_text().splitlines()) if rx.search(line)]
        return "\n".join(hits[:50]) or "no matches"

    @tool(risk="write")
    def edit_file(path: str, old: str, new: str) -> str:
        """Replace one exact, unique snippet in a file.

        Args:
            path: file path relative to the repository root
            old: the exact text to replace, including indentation
            new: the replacement text
        """
        # TODO 3: safe_path, read, apply_edit, write; return f"edited {path}"
        raise NotImplementedError("edit_file")

    @tool(risk="exec")
    def run_tests() -> str:
        """Run the test suite and return the summary and any failures."""
        out = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=root, capture_output=True, text=True,
                             timeout=60)
        text = (out.stdout + out.stderr).strip()
        return text if len(text) < 3000 else text[:1500] + "\n[...]\n" + text[-1500:]

    @tool
    def todo_write(items: list) -> str:
        """Replace the todo list. Each item is {"task": str, "status": "pending" | "in_progress" | "done"}.

        Args:
            items: the full, updated list
        """
        todos[:] = [{"task": str(t.get("task", t)), "status": t.get("status", "pending")} if isinstance(t, dict)
                    else {"task": str(t), "status": "pending"} for t in items]
        return "todo list updated: " + "; ".join(f"[{t['status']}] {t['task']}" for t in todos)

    return [list_files, read_file, grep, edit_file, run_tests, todo_write]


def coding_agent(llm, root, task, approve, compact=None, max_steps=25, on_event=None):
    """Return (run, todos, asked) where asked lists the calls that needed approval.

    Build the tools with make_tools(root, todos). Run run_agent with system=SYSTEM and an execute(call)
    function that: rejects unknown tools; for risk "write" tools appends the call to `asked` and, if
    approve(call) is False, returns "The user rejected this edit." without running it; otherwise runs
    the tool, turning any exception into "Error: <message>". Pass compact and on_event through.
    """
    # TODO 4
    raise NotImplementedError("coding_agent")
