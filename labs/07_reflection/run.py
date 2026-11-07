"""Check Lab 07: write parse_duration, verified by tests, with and without feedback.

Usage: python labs/07_reflection/run.py [--solution] [--model ollama:NAME]
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agentlab import get_llm  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, todo_hint  # noqa: E402
from agentlab.mock import say  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)

SPEC = ("Write parse_duration(s: str) -> int that converts a duration like '1h30m', '45s', '2h' or '1h 5m 3s' "
        "to seconds. Units are h, m and s, in that order, each optional, spaces allowed between them. "
        "Raise ValueError for an empty or malformed string.")
TESTS = [["1h30m", 5400], ["2h", 7200], ["90m", 5400], ["45s", 45], ["1h 5m 3s", 3903], ["", "ValueError"],
         ["5x", "ValueError"]]

# What a model typically writes, from first draft to correct. The mock moves one version forward each time
# the feedback shows it a failure it hasn't fixed yet; with no feedback it writes the same code again.
VERSIONS = [
    '''import re

def parse_duration(s):
    h, m = re.match(r"(?:(\\d+)h)?(?:(\\d+)m)?", s).groups()
    return int(h or 0) * 3600 + int(m or 0) * 60
''',
    '''import re

def parse_duration(s):
    h, m, sec = re.match(r"(?:(\\d+)h)?(?:(\\d+)m)?(?:(\\d+)s)?", s).groups()
    return int(h or 0) * 3600 + int(m or 0) * 60 + int(sec or 0)
''',
    '''import re

def parse_duration(s):
    h, m, sec = re.match(r"\\s*(?:(\\d+)h)?\\s*(?:(\\d+)m)?\\s*(?:(\\d+)s)?\\s*", s).groups()
    return int(h or 0) * 3600 + int(m or 0) * 60 + int(sec or 0)
''',
    '''import re

def parse_duration(s):
    found = re.fullmatch(r"\\s*(?:(\\d+)h)?\\s*(?:(\\d+)m)?\\s*(?:(\\d+)s)?\\s*", s)
    if not s.strip() or not found:
        raise ValueError(f"not a duration: {s!r}")
    h, m, sec = found.groups()
    return int(h or 0) * 3600 + int(m or 0) * 60 + int(sec or 0)
''',
]


def informative(text):
    return any(w in text for w in ("expected", "did not run", "timed out"))


def policy(messages, tools):
    feedback = [x["content"] for x in messages if x["role"] == "user"][1:]
    useful = sum(informative(f) for f in feedback)  # "try again" with no details: same input, same output
    return say(f"```python\n{VERSIONS[min(useful, len(VERSIONS) - 1)]}```")


def blind_retry(llm, attempts=4):
    messages = [{"role": "system", "content": "You write Python. Reply with one ```python code block."},
                {"role": "user", "content": SPEC}]
    best = 0
    for _ in range(attempts):
        code = m.extract_code(llm.chat(messages).text)
        passed, total, _ = m.run_tests(code, "parse_duration", TESTS)
        best = max(best, passed)
        if passed == total:
            break
        messages += [{"role": "assistant", "content": f"```python\n{code}```"},
                     {"role": "user", "content": "That is not right. Try again."}]
    return best


try:
    bad = m.run_tests("def parse_duration(s):\n    while True: pass\n", "parse_duration", TESTS, timeout=2)
    crash = m.run_tests("def parse_duration(s) return 0\n", "parse_duration", TESTS)
    print(f"sandbox checks: infinite loop -> {bad[2][0]!r}\n                syntax error  -> {crash[2][0]!r}\n")
    llm = get_llm(args.model, policy)
    code, attempts, history = m.reflexion(llm, SPEC, "parse_duration", TESTS)
    print("with test feedback and reflection, tests passed per attempt:", history)
    print(code)
    blind = blind_retry(get_llm(args.model, policy))
except NotImplementedError as e:
    todo_hint(e, __file__)

n = len(TESTS)
record(pass_first=history[0], attempts=attempts, blind_best=blind)
report(
    "a verifier turns 'try again' into a search that converges: feeding the exact failures back lets the model "
    "fix one problem per round, while a retry with no new information repeats the same mistake",
    f"first attempt passed {history[0]}/{n} tests; with feedback all {n} passed on attempt {attempts} "
    f"({' -> '.join(map(str, history))}); blind retry never beat {blind}/{n}",
    "PASS" if history[-1] == n and blind < n else "CHECK: reflexion should reach all tests, blind retry should not",
    "the tests are the spec: delete the '5x' case and see a wrong solution pass. Then read about reward hacking: "
    "agents trained with RL learn to special-case tests when the verifier is weak",
)
