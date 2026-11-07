"""Lab 07: reflection with a real verifier. Tests, not the model's opinion, decide what "done" means.

Run:  python labs/07_reflection/run.py             (your code)
      python labs/07_reflection/run.py --solution
"""
import json  # noqa: F401
import re  # noqa: F401
import subprocess  # noqa: F401
import sys  # noqa: F401
import tempfile  # noqa: F401

# Appended to the model's code and run in a separate process. It prints RESULTS[[ok, detail], ...].
HARNESS = '''
import json
results = []
for arg, want in json.loads(TESTS):
    try:
        got = {fn}(arg)
        ok = got == want
        detail = f"{fn}({{arg!r}}) returned {{got!r}}, expected {{want!r}}"
    except Exception as e:
        got = type(e).__name__
        ok = want == got
        detail = f"{fn}({{arg!r}}) raised {{got}}: {{e}}" + ("" if ok else f", expected {{want!r}}")
    results.append([ok, detail])
print("RESULTS" + json.dumps(results))
'''


def extract_code(text):
    """The body of the first ```python ... ``` (or ``` ... ```) block, or the whole text if there is none."""
    # TODO 1
    raise NotImplementedError("extract_code")


def run_tests(code, fn, tests, timeout=5):
    """Run untrusted model code in a *separate process* and return (passed, total, [failure details]).

    tests: [[input, expected], ...]; expected may be an exception name such as "ValueError".
    Build: code + f"\\nTESTS = {json.dumps(json.dumps(tests))}\\n" + HARNESS.format(fn=fn), write it to a
    temp file, run it with subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=...).
    Timeout -> (0, total, ["timed out ..."]). No RESULTS line -> (0, total, ["the code did not run: <last stderr line>"]).
    """
    # TODO 2
    raise NotImplementedError("run_tests")


def reflexion(llm, spec, fn, tests, max_attempts=4):
    """Return (final code, attempts used, [tests passed per attempt]).

    messages = system "You write Python. Reply with one ```python code block." + user spec.
    Each attempt: code = extract_code(llm.chat(messages).text); run the tests; all pass -> return.
    Otherwise append the code as an assistant message, then a user message that lists every failure and
    asks the model to reflect on what is wrong before fixing it. The failures are the signal: without
    them a retry at temperature 0 just writes the same code again.
    """
    # TODO 3
    raise NotImplementedError("reflexion")
