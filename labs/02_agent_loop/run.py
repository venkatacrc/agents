"""Check Lab 02: one question that needs three tool calls, a runaway model, and a tool error.

Usage: python labs/02_agent_loop/run.py [--solution] [--trace] [--model ollama:NAME]
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agentlab import get_llm, tokens  # noqa: E402
from agentlab.kb import calculator, lookup  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, table, todo_hint  # noqa: E402
from agentlab.loop import DEFAULT_SYSTEM  # noqa: E402
from agentlab.mock import call, calls_made, results_of, say  # noqa: E402
from agentlab.trace import Printer  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)
TOOLS = [lookup, calculator]
TASK = "How much HBM do 8 H100s and 4 A100s (80 GB version) have together, in GB?"


def gb(text):
    found = re.search(r"(\d+) GB", text)
    return found.group(1) if found else None


def competent(messages, tools):
    """Plays a capable model: look up both GPUs at once, compute with the tool, then answer."""
    facts = results_of(messages, "lookup")
    if not facts:
        return [call("lookup", topic="H100"), call("lookup", topic="A100")]
    sums = results_of(messages, "calculator")
    if not sums:
        h = next(gb(f) for f in facts if "H100" in f)
        a = next(gb(f) for f in facts if "A100" in f)
        return call("calculator", expression=f"8 * {h} + 4 * {a}")
    return say(f"8 H100s (80 GB each) and 4 A100s (80 GB each) have {sums[-1]} GB of HBM together.")


def runaway(messages, tools):
    """A model that never decides it is done: keeps re-checking the same fact."""
    return call("lookup", topic="H100")


def sloppy(messages, tools):
    """Writes '8 x 80' first; the error message tells it what is allowed, and it fixes the call."""
    sums = results_of(messages, "calculator")
    if not sums:
        return call("calculator", expression="8 x 80")
    if sums[-1].startswith("Error"):
        return call("calculator", expression="8 * 80")
    return say(f"8 H100s have {sums[-1]} GB of HBM.")


def trace():
    return Printer() if args.trace else None


try:
    llm = get_llm(args.model, competent)
    r1 = m.run_agent(llm, TOOLS, TASK, DEFAULT_SYSTEM, on_event=trace())
    print(f"\nanswer: {r1.answer}")
    rows = [(i + 1, len(msgs), tokens.count_messages(msgs) + tokens.count_tools(tl))
            for i, (msgs, tl) in enumerate(llm.requests)]
    table(rows, ["model call", "messages sent", "prompt tokens"])
    total_prompt = llm.prompt_tokens

    if args.model == "mock":
        if args.trace:
            print("\n-- a runaway model --")
        r2 = m.run_agent(get_llm("mock", runaway), TOOLS, TASK, DEFAULT_SYSTEM, max_steps=6, on_event=trace())
        if args.trace:
            print("\n-- a tool error, fed back --")
        r3 = m.run_agent(get_llm("mock", sloppy), TOOLS, "How much HBM do 8 H100s have?", DEFAULT_SYSTEM, on_event=trace())
        errs = [c for c in results_of(r3.messages, "calculator") if c.startswith("Error")]
        print(f"\nrunaway model: stopped={r2.stopped!r} after {r2.steps} model calls")
        print(f"tool error: the model saw {errs[0]!r}\n  and recovered: {r3.answer!r} ({r3.steps} model calls)")
except NotImplementedError as e:
    todo_hint(e, __file__)

if args.model == "mock":
    total_gb = (re.findall(r"(\d+) GB of HBM", r1.answer) or ["?"])[0]
    ok = ("960" in r1.answer and r1.steps == 3 and r1.tool_calls == 3 and r2.stopped == "max_steps"
          and r2.steps == 6 and "640" in r3.answer)
    record(steps=r1.steps, tool_calls=r1.tool_calls, total_prompt=total_prompt, runaway_steps=r2.steps,
           recovery_steps=r3.steps)
    report(
        "an agent is a loop: the model asks for tools, the harness runs them and appends the results, and the model "
        "decides when to stop. The harness must bound the loop and turn tool errors into observations",
        f"{r1.steps} model calls and {r1.tool_calls} tool calls (two in parallel) to answer {total_gb} GB; "
        f"{total_prompt} prompt tokens in total because every call re-sends the whole history; runaway stopped at "
        f"{r2.steps}; tool error recovered in {r3.steps} calls",
        "PASS" if ok else "CHECK: expected 3 calls / 3 tools / 960 GB, a max_steps stop at 6, and 640 GB after the error",
        "run with --trace and watch the context grow each step; then try --model ollama:NAME and count its steps",
    )
else:
    print(f"\n{args.model}: {r1.steps} model calls, {len(calls_made(r1.messages))} tool calls. {llm.usage()}")
