---
id: 07
title: Reflection with a real verifier
lab: labs/07_reflection
minutes: 45
track: patterns
summary: Reflexion, self-critique and why feedback from tests beats asking the model to try again
---
Agents get better results by trying, checking, and trying again. The research names for this are **Reflexion** (Shinn et al. 2023: the agent writes a verbal reflection on why it failed and keeps it in memory for the next attempt) and **Self-Refine** (Madaan et al. 2023: draft, self-critique, revise). The part that matters in practice is less glamorous: **where does the signal that something is wrong come from?**

## Three sources of feedback, in increasing order of value

1. **None (blind retry).** "Try again." At temperature 0 the model writes the same answer. At higher temperature it writes a *different* answer, which is just sampling: you're doing best-of-n without a way to pick the best.
2. **The model's own critique.** "Review your answer for mistakes." It helps on some tasks, but models are poor at finding their own errors without new information. Huang et al. (2024, "Large Language Models Cannot Self-Correct Reasoning Yet") found that self-correction without external feedback often makes answers *worse*.
3. **An external verifier.** Tests, a compiler, a type checker, a linter, a schema validator, an API that returns an error, a simulator. These produce *new information* the model didn't have: "`parse_duration('1h 30m')` returned 3600, expected 5400". That is what makes the next attempt different.

Coding agents are as strong as they are largely because code comes with verifiers. The loop "edit, run the tests, read the failures, edit again" is reflection with ground truth. It's also why RL on code and math works so well (lesson 13): the same verifiers become rewards.

## Running model code safely

The verifier here runs code the model wrote. Treat it as untrusted: run it in a **separate process** with a **timeout** (an infinite loop must not hang your agent), capture output, and in production add a sandbox (containers, gVisor, Firecracker microVMs, or a remote sandbox service) with no network and no secrets.

::: trace
title: parse_duration, with test feedback
user | Write parse_duration(s) that converts '1h30m', '45s', '2h' or '1h 5m 3s' to seconds; raise ValueError for an empty or malformed string.
answer | attempt 1: re.match(r"(?:(\d+)h)?(?:(\d+)m)?", s) → hours and minutes
tool | 3/7 passed. parse_duration('45s') returned 0, expected 45 · parse_duration('1h 5m 3s') returned 3600, expected 3903 · parse_duration('') returned 0, expected 'ValueError' · …
think | Seconds are never parsed. Add an (\d+)s group.
answer | attempt 2: hours, minutes and seconds groups
tool | 4/7 passed. parse_duration('1h 5m 3s') returned 3600, expected 3903 · parse_duration('') returned 0, expected 'ValueError' · …
think | Spaces between units stop the match. Allow \s* between groups.
answer | attempt 3: \s* between the groups
tool | 5/7 passed. parse_duration('') returned 0, expected 'ValueError' · parse_duration('5x') returned 0, expected 'ValueError'
think | re.match accepts an empty match. Use re.fullmatch and raise when nothing was found.
answer | attempt 4: re.fullmatch, ValueError on empty or malformed input
tool | 7/7 passed
:::

::: write
In `labs/07_reflection/agent.py`:

1. `extract_code(text)`: the first fenced python block, or the whole text.
2. `run_tests(code, fn, tests, timeout)`: write the code plus the test harness to a temp file, run it with `subprocess.run([sys.executable, path], timeout=...)`, parse the `RESULTS` line. Timeout → 0 passed with "timed out"; no results → "the code did not run: <last stderr line>".
3. `reflexion(llm, spec, fn, tests, max_attempts=4)`: generate, test, and on failure append the code and a user message that lists *every* failure and asks the model to reflect on what is wrong before fixing it.
:::

::: run
```bash
python labs/07_reflection/run.py
python labs/07_reflection/run.py --solution
```
The mock model improves only when the feedback names failing inputs, just as real models do.
:::

::: measure
- pass_first | tests passed by the first attempt | 3 | of 7
- attempts | attempts until all tests pass | 4 |
- blind_best | best score with blind retries | 3 | of 7
:::

::: explain
**3 → 4 → 5 → 7 with feedback, stuck at 3/7 without.** Each test failure told the model something specific (an input, the output, the expectation), so each attempt fixed a class of bug. Blind retries had nothing new to work with. Real models at temperature 0 behave the same way, and at higher temperature you'd get variation without direction.

**The sandbox checks matter as much as the loop.** The run starts by feeding `run_tests` an infinite loop and a syntax error: one comes back as "timed out after 2 s (infinite loop?)" and the other as "the code did not run: SyntaxError…", both useful observations instead of a hung or crashed agent.

**Tests can be wrong, and models can game them.** If the tests come from the model too, it can write tests that pass trivially. Agents under pressure have been seen special-casing test inputs or deleting failing tests. RL-trained models do this "reward hacking" too (lesson 13). Keep verifiers outside the agent's write access when you can, and review diffs to test files.
:::

::: cards
Q: What is Reflexion?
A: An agent pattern where after a failed attempt the model writes a verbal reflection on what went wrong, which is kept in context to guide the next attempt.
Q: Why does "try again" without feedback rarely help?
A: At temperature 0 the model repeats itself; at higher temperature it only resamples. No new information enters the context.
Q: What did "LLMs Cannot Self-Correct Reasoning Yet" find?
A: Without external feedback, asking models to review and correct their own reasoning often fails to improve, and can degrade, accuracy.
Q: Give four examples of external verifiers for agents.
A: Unit tests, compilers or type checkers, linters, schema validators, API error responses, simulators, or a human reviewer.
Q: How should an agent run model-written code?
A: In a separate process with a timeout and captured output, and in production inside a sandbox with no network and no secrets.
Q: What is reward hacking in a coding agent?
A: Satisfying the verifier without solving the task, e.g. special-casing test inputs or editing the tests themselves.
:::
