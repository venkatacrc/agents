"""Check Lab 04: read 20 log files and report every error, under four context strategies.

Usage: python labs/04_context_memory/run.py [--solution] [--trace]
"""
import pathlib
import random
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agentlab import get_llm, tokens  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, table, todo_hint  # noqa: E402
from agentlab.loop import run_agent  # noqa: E402
from agentlab.mock import all_text, call, say, system_text  # noqa: E402
from agentlab.tools import tool  # noqa: E402
from agentlab.trace import Printer  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)

rng = random.Random(7)
ERRORS = {3: "ERROR rank 12: NCCL timeout in all_reduce after 1800 s",
          7: "ERROR rank 3: CUDA out of memory (tried to allocate 2.50 GiB)",
          11: "ERROR dataloader worker 5 died: corrupt shard 0417",
          15: "ERROR checkpoint save failed: disk quota exceeded on /ckpt",
          18: "ERROR loss is NaN at step 48210; skipping update"}
LOGS = {}
for f in range(20):
    lines = []
    for k in range(36):
        step = f * 1000 + k * 25
        lines.append(f"02:{f:02d}:{k:02d} INFO step {step} loss {2.9 - step / 30000 + rng.random() * 0.05:.3f} "
                     f"tok/s {rng.randint(48000, 52000)} grad_norm {rng.random() * 2:.2f}")
    if f in ERRORS:
        lines.insert(17, f"02:{f:02d}:17 {ERRORS[f]}")
    LOGS[f"train_{f:02d}.log"] = "\n".join(lines)


@tool
def list_logs() -> str:
    """List the log files of last night's training run."""
    return ", ".join(LOGS)


@tool
def read_log(name: str) -> str:
    """Read one log file.

    Args:
        name: file name from list_logs, e.g. train_00.log
    """
    return LOGS[name]


TASK = "Read every log file of last night's training run and list every ERROR line, with the file it was in."


def policy(messages, tools):
    """The agent part reads files one by one; the summarizer part keeps progress and every error."""
    if system_text(messages).startswith("You summarize"):
        seen = all_text(messages)
        everything = re.search(r"(?:All files: )?(train_\d\d\.log(?:, train_\d\d\.log){5,})", seen)
        read = sorted(set(re.findall(r"read_log[^\n]*?(train_\d\d\.log)", seen))
                      | set(re.findall(r"train_\d\d\.log", " ".join(re.findall(r"Files read: ([^\n]*)", seen)))))
        errs = sorted(set(re.findall(r"\d\d:\d\d:\d\d ERROR[^\n]*", seen)))
        return say((f"All files: {everything.group(1)}\n" if everything else "")
                   + f"Files read: {', '.join(read)}\nErrors found:\n" + "\n".join(errs))
    seen = all_text(messages)
    listed = re.search(r"(train_\d\d\.log(?:, train_\d\d\.log){5,})", seen)
    if not listed:
        return call("list_logs")
    files = listed.group(1).split(", ")
    done_text = re.findall(r"Files read: ([^\n]*)", seen)
    read = set(re.findall(r"train_\d\d\.log", " ".join(done_text)))
    for msg in messages:
        for c in msg.get("tool_calls") or []:
            if c["function"]["name"] == "read_log":
                read.add(re.search(r"train_\d\d\.log", c["function"]["arguments"]).group(0))
    todo = [f for f in files if f not in read]
    if todo:
        return call("read_log", name=todo[0])
    found = sorted(set(re.findall(r"\d\d:(\d\d):\d\d (ERROR[^\n]*)", seen)))
    return say(f"Found {len(found)} errors:\n" + "\n".join(f"train_{f}.log: {e}" for f, e in found))


def summarize(llm):
    def run(middle):
        transcript = "\n\n".join(f"{x['role']}: {x.get('content') or x.get('tool_calls')}" for x in middle)
        r = llm.chat([{"role": "system", "content": "You summarize an agent's progress for the agent itself. "
                       "Keep: the full list of files, which files were already read, and every ERROR line verbatim. "
                       "Drop everything else."},
                      {"role": "user", "content": transcript}])
        return r.text
    return run


def drop_oldest(budget):
    """The naive fix: forget the oldest turns until the history fits."""
    def run(messages):
        out = list(messages)
        while tokens.count_messages(out) > budget and len(out) > 4:
            del out[2]
            while out[2]["role"] == "tool":
                del out[2]
        return out
    return run


BUDGET = 1500
results = {}
try:
    def clipper(c):
        from agentlab.tools import Toolbox
        return m.clip(Toolbox([list_logs, read_log]).run(c), 250)

    for label, compact, execute in (
        ("keep everything", None, None),
        ("drop oldest turns", drop_oldest(BUDGET), None),
        ("clip tool output", None, clipper),
        ("clip + compact", "compact", clipper),
    ):
        llm = get_llm(args.model, policy)
        if compact == "compact":
            compact = lambda msgs, llm=llm: m.compact(msgs, BUDGET, summarize(llm))  # noqa: E731
        r = run_agent(llm, [list_logs, read_log], TASK, max_steps=40, compact=compact, execute=execute,
                      on_event=Printer(width=110) if args.trace else None)
        found = sum(e.split(": ", 1)[-1][:30] in r.answer for e in ERRORS.values())
        results[label] = (llm.peak_prompt_tokens, llm.prompt_tokens, found, llm.calls)
    print(f"\none task, {sum(tokens.count(v) for v in LOGS.values()):,} tokens of logs, 5 errors hidden in the middle of files")
    table([(k, f"{p:,}", f"{t:,}", f"{f}/5", c) for k, (p, t, f, c) in results.items()],
          ["strategy", "peak context", "total prompt tokens", "errors reported", "model calls"])
    sample = m.clip(LOGS["train_07.log"], 250)
    print(f"\nclip(train_07.log, 250) keeps {tokens.count(sample)} of {tokens.count(LOGS['train_07.log'])} tokens:\n{sample}")
except NotImplementedError as e:
    todo_hint(e, __file__)

full, drop, clipped, both = (results[k] for k in results)
record(peak_full=full[0], total_full=full[1], errors_drop=drop[2], peak_managed=both[0], total_managed=both[1],
       errors_managed=both[2])
report(
    "without management the context grows with every tool result and you pay for all of it on every call; dropping "
    "old turns loses facts, while clipping tool output and summarizing old turns bounds the context and keeps them",
    f"peak context {full[0]:,} -> {both[0]:,} tokens, total prompt tokens {full[1]:,} -> {both[1]:,}; errors "
    f"reported: {full[2]}/5 keep-everything, {drop[2]}/5 drop-oldest, {both[2]}/5 clip+compact",
    "PASS" if both[2] == 5 and both[0] < full[0] / 3 and drop[2] < 5 else "CHECK: clip+compact should keep all 5 errors",
    "set keep=r'$^' in clip (keep nothing special) and watch errors vanish; then lower BUDGET until compaction "
    "runs every step and count the extra summarizer calls",
)
