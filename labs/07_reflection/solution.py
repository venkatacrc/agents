"""Lab 07 reference: generate, verify with real tests, reflect on the failures, retry."""
import json
import re
import subprocess
import sys
import tempfile

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
    found = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    return found.group(1) if found else text


def run_tests(code, fn, tests, timeout=5):
    program = code + f"\nTESTS = {json.dumps(json.dumps(tests))}\n" + HARNESS.format(fn=fn)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(program)
    try:
        out = subprocess.run([sys.executable, f.name], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 0, len(tests), [f"timed out after {timeout} s (infinite loop?)"]
    if "RESULTS" not in out.stdout:
        return 0, len(tests), [f"the code did not run: {out.stderr.strip().splitlines()[-1] if out.stderr else 'no output'}"]
    results = json.loads(out.stdout.split("RESULTS", 1)[1])
    failures = [d for ok, d in results if not ok]
    return len(tests) - len(failures), len(tests), failures


def reflexion(llm, spec, fn, tests, max_attempts=4):
    messages = [{"role": "system", "content": "You write Python. Reply with one ```python code block."},
                {"role": "user", "content": spec}]
    history = []
    code = ""
    for attempt in range(1, max_attempts + 1):
        code = extract_code(llm.chat(messages).text)
        passed, total, failures = run_tests(code, fn, tests)
        history.append(passed)
        if passed == total:
            return code, attempt, history
        messages.append({"role": "assistant", "content": f"```python\n{code}```"})
        messages.append({"role": "user", "content": "The tests failed:\n" + "\n".join(f"- {x}" for x in failures)
                         + "\n\nReflect: what is wrong with your approach? Then reply with the fixed code."})
    return code, max_attempts, history
