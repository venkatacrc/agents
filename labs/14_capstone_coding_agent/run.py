"""Check Lab 14: a coding agent fixes the failing tests in a copy of toyrepo/.

Usage: python labs/14_capstone_coding_agent/run.py [--solution] [--trace] [--interactive] [--model ollama:qwen2.5:7b]
"""
import ast
import difflib
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from agentlab import get_llm  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, todo_hint  # noqa: E402
from agentlab.mock import call, calls_made, results_of, say, tool_results  # noqa: E402
from agentlab.trace import Printer, fmt_call  # noqa: E402

args = lab_args(__doc__, lambda ap: ap.add_argument("--interactive", action="store_true",
                                                    help="approve or reject each edit yourself"))
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)
TASK = "The tests in this repository are failing. Find the bugs and fix them so that all tests pass."

# What a capable model "knows" about fixing these bugs; the mock finds the code by reading files, like a model.
FIXES = {
    "return s[len(s) // 2]": "    n = len(s)\n    mid = n // 2\n    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2",
    "return sum(xs) / len(xs)": "    if not xs:\n        raise ValueError(\"mean of an empty list\")\n"
                                "    return sum(xs) / len(xs)",
}


def tests_passing(output):
    ran = re.search(r"Ran (\d+) test", output)
    bad = sum(int(n) for n in re.findall(r"(?:failures|errors)=(\d+)", output))
    return (int(ran.group(1)) - bad if ran else 0), (int(ran.group(1)) if ran else 0)


def policy(messages, tools):
    made = calls_made(messages)
    results = [c for _, c in tool_results(messages)]
    done = list(zip(made, results))
    tests = results_of(messages, "run_tests")
    if not any(c.name == "todo_write" for c in made):
        return call("todo_write", items=[{"task": "run the tests", "status": "in_progress"},
                                         {"task": "read the failing code", "status": "pending"},
                                         {"task": "fix each bug", "status": "pending"},
                                         {"task": "re-run the tests", "status": "pending"}])
    if not tests:
        return call("run_tests")
    if "rejected" in results[-1]:
        return say("You rejected the edit, so I stopped. The failing tests are unchanged.")
    if tests[-1].rstrip().endswith("OK"):
        if made[-1].name != "todo_write":
            return call("todo_write", items=[{"task": t, "status": "done"} for t in
                                             ("run the tests", "read the failing code", "fix each bug", "re-run the tests")])
        fixed = [c.args["new"].strip().splitlines()[0] for c, r in done if c.name == "edit_file" and r.startswith("edited")]
        return say("All tests pass. I fixed stats.py: median now averages the two middle values for even-length "
                   "lists, and mean raises ValueError on an empty list. Edits began with: " + "; ".join(fixed))
    files = sorted(set(re.findall(r'File "[^"]*?([\w]+\.py)"', tests[0])) - {"test_stats.py", "case.py"})
    target = files[0] if files else "stats.py"
    reads = [r for c, r in done if c.name == "read_file"]
    if not reads:
        return call("read_file", path=target)
    source = "\n".join(line.split("| ", 1)[1] if "| " in line else "" for line in reads[-1].splitlines())
    edited = [c for c, r in done if c.name == "edit_file" and r.startswith("edited")]
    for snippet, new in FIXES.items():
        if snippet in source and not any(snippet in c.args["old"] for c in edited):
            line = next(x for x in reads[-1].splitlines() if snippet in x)
            failed = [r for c, r in done if c.name == "edit_file" and r.startswith("Error")]
            if not failed:
                return call("edit_file", path=target, old=line, new=new)  # a classic slip: copies the line number too
            hint = re.search(r"Closest line is \d+: ('.*?'|\".*?\")", failed[-1])
            same = hint and snippet in ast.literal_eval(hint.group(1))
            return call("edit_file", path=target, old=ast.literal_eval(hint.group(1)) if same else line.split("| ", 1)[1],
                        new=new)
    if made[-1].name == "edit_file":
        return [call("todo_write", items=[{"task": "run the tests", "status": "done"},
                                          {"task": "read the failing code", "status": "done"},
                                          {"task": "fix each bug", "status": "done"},
                                          {"task": "re-run the tests", "status": "in_progress"}]), call("run_tests")]
    return say("I could not find a fix for the remaining failures.")


def approve(c):
    edit = f"edit {c.args.get('path')}: {c.args.get('old', '')!r} -> {c.args.get('new', '')!r}"
    if args.interactive:
        return input(f"\n  approve {edit[:300]}? [y/N] ").strip().lower().startswith("y")
    print(f"  [human] approved {edit[:110]}")
    return True


try:
    work = pathlib.Path(tempfile.mkdtemp()) / "toyrepo"
    shutil.copytree(HERE / "toyrepo", work)
    checks = {"inside": m.safe_path(work, "stats.py") == (work / "stats.py").resolve()}
    for bad in ("../../etc/passwd", "/etc/passwd"):
        try:
            m.safe_path(work, bad)
            checks[bad] = False
        except ValueError:
            checks[bad] = True
    for text, old, want in (("a = 1\nb = 1\n", "= 1", "appears 2 times"), ("    x = 1\n", "  x = 2", "Closest line")):
        try:
            m.apply_edit(text, old, "z")
            checks[want] = False
        except ValueError as e:
            checks[want] = want in str(e)
    print("unit checks: " + ", ".join(f"{k}: {'ok' if v else 'WRONG'}" for k, v in checks.items()))

    before = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=work, capture_output=True, text=True)
    p_before = tests_passing(before.stdout + before.stderr)
    original = (work / "stats.py").read_text()
    llm = get_llm(args.model, policy)
    run, todos, asked = m.coding_agent(llm, work, TASK, approve,
                                       on_event=Printer(width=120) if args.trace else None)
    after = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=work, capture_output=True, text=True)
    p_after = tests_passing(after.stdout + after.stderr)
    edit_errors = sum(1 for c, r in zip(calls_made(run.messages), [x for _, x in tool_results(run.messages)])
                      if c.name == "edit_file" and r.startswith("Error"))
    print(f"\nanswer: {run.answer}\n\ntodo list: " + "; ".join(f"[{t['status']}] {t['task']}" for t in todos))
    print("\ndiff:\n" + "".join(difflib.unified_diff(original.splitlines(True), (work / "stats.py").read_text()
                                                     .splitlines(True), "a/stats.py", "b/stats.py")))
    print(f"tests passing {p_before[0]}/{p_before[1]} -> {p_after[0]}/{p_after[1]} in {run.steps} model calls, "
          f"{run.tool_calls} tool calls ({', '.join(sorted(set(fmt_call(c).split('(')[0] for c in calls_made(run.messages))))}); "
          f"{len(asked)} edits needed approval, {edit_errors} failed edit recovered; {llm.usage()}")
except NotImplementedError as e:
    todo_hint(e, __file__)

record(tests_before=p_before[0], tests_after=p_after[0], steps=run.steps, edits_asked=len(asked),
       edit_errors=edit_errors, unit_checks=sum(checks.values()))
report(
    "a coding agent is the same loop with the right tools: exact-match edits with helpful errors, path safety, "
    "approvals on writes, a todo list for the plan, and the test suite as the verifier",
    f"tests {p_before[0]}/{p_before[1]} -> {p_after[0]}/{p_after[1]} in {run.steps} model calls; {len(asked)} edits "
    f"approved, {edit_errors} bad edit fixed from the error hint; unit checks {sum(checks.values())}/{len(checks)}",
    "PASS" if p_after[0] == p_after[1] > p_before[0] and all(checks.values()) else "CHECK",
    "add a bug to toyrepo/stats.py (percentile of an empty list), add a test, and run with a real model: "
    "--model ollama:qwen2.5-coder:7b or vllm:NAME; then plug in Lab 04's compact and Lab 08's checkpoints",
)
