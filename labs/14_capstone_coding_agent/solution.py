"""Lab 14 reference: a small coding agent assembled from the course's parts."""
import difflib
import pathlib
import re
import subprocess
import sys

from agentlab.loop import run_agent
from agentlab.tools import tool

SYSTEM = """You are a coding agent working in a small Python repository.
- Start by writing a todo list with todo_write, and keep it updated as you work.
- Run the tests first to see what is failing. Read code before you change it.
- edit_file replaces one exact, unique snippet of a file: copy the old text exactly, with its indentation,
  and without the line numbers that read_file shows.
- After editing, run the tests again. You are done when they pass; then summarize what you changed."""


def safe_path(root, path):
    root = pathlib.Path(root).resolve()
    p = (root / path).resolve()
    if p != root and root not in p.parents:
        raise ValueError(f"{path!r} is outside the repository")
    return p


def apply_edit(text, old, new):
    n = text.count(old)
    if n == 1:
        return text.replace(old, new)
    if n > 1:
        raise ValueError(f"old text appears {n} times; include more surrounding lines so it is unique")
    lines = text.splitlines()
    first = old.strip().splitlines()[0].strip() if old.strip() else ""
    near = difflib.get_close_matches(first, [x.strip() for x in lines], n=1, cutoff=0.6)
    hint = ""
    if near:
        i = [x.strip() for x in lines].index(near[0])
        hint = f" Closest line is {i + 1}: {lines[i]!r} (check indentation and spelling)."
    raise ValueError("old text not found in the file." + hint)


def make_tools(root, todos):
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
        p = safe_path(root, path)
        p.write_text(apply_edit(p.read_text(), old, new))
        return f"edited {path}"

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
    todos = []
    tools = {t.name: t for t in make_tools(root, todos)}
    asked = []

    def execute(call):
        t = tools.get(call.name)
        if t is None:
            return f"Error: no tool {call.name!r}"
        if t.risk == "write":
            asked.append(call)
            if not approve(call):
                return "The user rejected this edit."
        try:
            return str(t.fn(**call.args))
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

    run = run_agent(llm, list(tools.values()), task, system=SYSTEM, max_steps=max_steps, execute=execute,
                    compact=compact, on_event=on_event)
    return run, todos, asked
