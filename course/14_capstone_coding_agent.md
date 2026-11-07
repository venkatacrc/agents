---
id: 14
title: Capstone: a coding agent
lab: labs/14_capstone_coding_agent
minutes: 75
track: systems
summary: a small Claude Code or Cursor agent from the course's parts; exact-match edits, tests as verifier, approvals, todos
---
Coding agents are the most successful agents so far, and now you can see why: code comes with a verifier (tests), a precise action space (edit this text in this file), and plenty of training environments (lesson 13). Underneath, Claude Code, Cursor's agent, Codex and SWE-agent are the loop from lesson 02 with a carefully designed set of tools.

## The tools

| tool | why it looks like this |
|---|---|
| `list_files()`, `grep(pattern)` | agentic search: find code by reading, instead of pre-loading the repo into the context (lesson 04) |
| `read_file(path)` | returns **line numbers**, so the model and the errors can talk about locations |
| `edit_file(path, old, new)` | **exact-match replace**: `old` must appear exactly once. No line numbers to get wrong, no whole-file rewrites to truncate. Claude Code's `Edit` and Cursor's `StrReplace` work this way |
| `run_tests()` | the verifier (lesson 07): runs in a subprocess with a timeout, output clipped |
| `todo_write(items)` | the plan as a list the model rewrites as it works (lesson 06), shown to the user |

And the harness around them:

- **Path safety.** Every path is resolved and must stay inside the repository: `../../etc/passwd`, `/etc/passwd` and symlinks pointing out are refused (lesson 11's least privilege).
- **Helpful edit errors.** When `old` isn't found, the error names the closest line and says to check indentation. When it appears twice, it says how many times and asks for more context (lesson 03).
- **Approvals on writes.** Edits ask the human (or are auto-approved in a sandbox); reads never ask (lesson 08).

## The classic mistake

`read_file` shows `  10|     return s[len(s) // 2]`. Models copy that line, line number and all, into `edit_file`'s `old`, and the edit fails. It's one of the most common coding-agent errors, and the fix is in the tool, not the model: a clear error with the closest real line, which the model can paste back. Real harnesses also strip a leading line-number prefix from `old` automatically.

::: trace
title: fix the failing tests (Approve or Deny the first edit)
user | The tests in this repository are failing. Find the bugs and fix them so that all tests pass.
call 224 | todo_write([run the tests (in_progress), read the failing code, fix each bug, re-run the tests])
call 269 | run_tests()
tool | ERROR: test_mean_empty_raises … ZeroDivisionError · FAIL: test_median_even … 3 != 2.5 · Ran 5 tests · FAILED (failures=1, errors=1)
call 824 | read_file(path="stats.py")
tool | 4| def mean(xs): · 5|     return sum(xs) / len(xs) · … · 8| def median(xs): · 9|     s = sorted(xs) · 10|     return s[len(s) // 2]
approve | edit_file(path="stats.py", old="  10|     return s[len(s) // 2]", new="    n = len(s) …")
[approve] tool | Error: old text not found in the file. Closest line is 10: '    return s[len(s) // 2]' (check indentation and spelling).
[approve] think | I copied the line number. Use the exact line from the hint.
[approve] call | edit_file(path="stats.py", old="    return s[len(s) // 2]", new="    n = len(s)\n    mid = n // 2\n    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2")
[approve] tool | edited stats.py
[approve] call | edit_file(path="stats.py", old="    return sum(xs) / len(xs)", new="    if not xs:\n        raise ValueError(\"mean of an empty list\")\n    return sum(xs) / len(xs)")
[approve] tool | edited stats.py
[approve] call | todo_write([…, re-run the tests (in_progress)])  ·  run_tests()
[approve] tool | Ran 5 tests · OK
[approve] answer 2246 | All tests pass. I fixed stats.py: median now averages the two middle values for even-length lists, and mean raises ValueError on an empty list.
[deny] tool | The user rejected this edit.
[deny] answer | You rejected the edit, so I stopped. The failing tests are unchanged.
:::

::: write
In `labs/14_capstone_coding_agent/agent.py`:

1. `safe_path(root, path)`: resolve, and raise `ValueError` unless the result is the root or inside it.
2. `apply_edit(text, old, new)`: replace only if `old` occurs exactly once; otherwise a `ValueError` that helps (closest line via `difflib.get_close_matches`, or the count).
3. `edit_file`'s body: `safe_path`, read, `apply_edit`, write.
4. `coding_agent(llm, root, task, approve, ...)`: build the tools, and run `run_agent` with the system prompt and an `execute` that asks `approve(call)` for write-risk tools, refuses unknown tools, and turns exceptions into `Error: …` results.
:::

::: run
```bash
python labs/14_capstone_coding_agent/run.py --solution --trace
python labs/14_capstone_coding_agent/run.py --solution --interactive    # approve each edit yourself
python labs/14_capstone_coding_agent/run.py --solution --model vllm:Qwen/Qwen2.5-Coder-7B-Instruct
```
Every run works on a fresh copy of `toyrepo/` in a temp directory and prints the final diff.
:::

::: measure
- tests_before | tests passing before | 3 | of 5
- tests_after | tests passing after | 5 | of 5
- steps | model calls | 9 |
- edits_asked | edits that needed approval | 3 |
- edit_errors | failed edits recovered from the error | 1 |
- unit_checks | path-safety and edit unit checks | 5 | of 5
:::

::: explain
**Two bugs fixed in 9 model calls, verified by the tests.** The agent ran the tests first, so it knew *what* was wrong before reading code, read the one file the tracebacks pointed to, made two minimal edits, and re-ran the tests before claiming success. Run the tests, read, edit, verify: that order is what you want from any coding agent, and the system prompt asks for it explicitly.

**The failed edit cost one model call and one approval.** The mock copied the line-number prefix, like real models do, and the error's "Closest line is 10: '    return s[len(s) // 2]'" gave it the exact text. On the second bug it didn't repeat the mistake. Without the hint, models often retry with variations of the wrong string, or fall back to rewriting the whole file.

**Everything here came from an earlier lesson.** The loop (02), tool design and helpful errors (03), a todo list (06), tests as the verifier (07), approvals (08), path safety (11). `coding_agent` accepts lesson 04's `compact` too: for a real repo, plug it in with a budget and clip `run_tests` output with `keep=r"FAIL|ERROR|Error|line \d+"`.

**Next steps for a real one.** Add `run_shell(cmd)` with an allowlist and approvals, checkpoint the state after every edit (lesson 08) so a long session survives a crash, show diffs in approvals, and evaluate it on a few dozen bugs with pass^k (lesson 10). That is, in miniature, how SWE-bench agents are built and measured.
:::

::: cards
Q: Why do coding agents use exact-match string replacement for edits?
A: It needs no line numbers that drift, can't truncate a whole-file rewrite, and fails loudly (not found or not unique) instead of editing the wrong place.
Q: What should `edit_file` do when `old` appears twice?
A: Refuse and say how many matches there are, asking for more surrounding lines so the match is unique.
Q: What is the most common edit_file mistake models make, and the fix?
A: Copying read_file's line-number prefix into `old`; the tool should return the closest real line in its error (or strip the prefix).
Q: How does `safe_path` prevent escaping the workspace?
A: Resolve the joined path (following .. and symlinks) and require that it equals the root or has the root among its parents.
Q: Why should a coding agent run the tests before editing?
A: The failures say what is wrong and where; reading code without them is guessing.
Q: What makes coding particularly well suited to agents?
A: A cheap, objective verifier (tests and compilers), a precise text action space, and abundant environments for RL training.
:::
