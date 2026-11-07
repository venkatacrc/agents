"""Check Lab 08: free GPUs with a human approving every change, then survive a crash mid-run.

Usage: python labs/08_human_in_the_loop/run.py [--solution] [--interactive] [--trace]
"""
import json
import pathlib
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agentlab import ToolCall, Toolbox, get_llm  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, table, todo_hint  # noqa: E402
from agentlab.mock import call, calls_made, results_of, say  # noqa: E402
from agentlab.tools import tool  # noqa: E402

args = lab_args(__doc__, lambda ap: ap.add_argument("--interactive", action="store_true",
                                                    help="answer the agent's questions and approvals yourself"))
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)

JOBS = {"job-7": ("alice", "idle 30 h", ""), "job-88": ("carol", "running", ""),
        "job-121": ("bob", "idle 50 h", ""), "job-130": ("prod-team", "idle 26 h", "production")}
EFFECTS = []  # every action that really happened
CRASH = {"armed": False}


class Crash(BaseException):
    """The agent's process dies (OOM-killed, laptop closed, pod evicted). Not a tool error."""


@tool
def list_jobs() -> str:
    """List training jobs with owner, state and tags."""
    return "\n".join(f"{j}: owner {o}, {s}{', tag ' + t if t else ''}" for j, (o, s, t) in JOBS.items())


@tool(risk="write")
def cancel_job(job_id: str) -> str:
    """Cancel a training job and release its GPUs.

    Args:
        job_id: the job to cancel
    """
    if CRASH["armed"] and job_id == "job-121":
        CRASH["armed"] = False
        raise Crash()
    EFFECTS.append(("cancel", job_id))
    return f"{job_id} cancelled, 8 GPUs released"


@tool(risk="destructive")
def delete_checkpoints(path: str) -> str:
    """Delete checkpoint files under a path. Cannot be undone.

    Args:
        path: folder to delete, e.g. /ckpt/job-7
    """
    EFFECTS.append(("delete", path))
    return f"deleted {path} (1.2 TB freed)"


@tool(risk="human")
def ask_user(question: str) -> str:
    """Ask the user a question when the request is ambiguous or a choice is theirs to make.

    Args:
        question: one clear question
    """
    raise RuntimeError("the harness answers ask_user, never this function")


TOOLS = Toolbox([list_jobs, cancel_job, delete_checkpoints, ask_user])
SYSTEM = ("You are a cluster operations agent. Ask the user with ask_user when something is ambiguous or risky. "
          "Some actions need the user's approval; if they deny one, respect it and don't retry it.")
TASK = "Free up GPUs: cancel the idle training jobs and delete their checkpoints."


def policy(messages, tools):
    jobs = results_of(messages, "list_jobs")
    if not jobs:
        return call("list_jobs")
    answers = results_of(messages, "ask_user")
    idle = re.findall(r"(job-\d+): owner \S+, idle", jobs[-1])
    prod = re.findall(r"(job-\d+): [^\n]*tag production", jobs[-1])
    if prod and not answers:
        return call("ask_user", question=f"{', '.join(prod)} is tagged production but idle. Cancel it too?")
    keep = set(re.findall(r"job-\d+", " ".join(answers))) if answers and re.search(r"\b(no|leave|keep)\b", answers[-1], re.I) else set()
    targets = [j for j in idle if j not in keep]
    cancels = results_of(messages, "cancel_job")
    if not cancels:
        return [call("cancel_job", job_id=j) for j in targets]
    cancelled = re.findall(r"(job-\d+) cancelled", " ".join(cancels))
    if not results_of(messages, "delete_checkpoints"):
        # Overreaches once, as models do: also asks to wipe the whole /ckpt folder "to tidy up".
        return [call("delete_checkpoints", path=f"/ckpt/{j}") for j in cancelled] + [call("delete_checkpoints", path="/ckpt")]
    paths = {c.id: c.args.get("path") for c in calls_made(messages)}
    outcome = {"deleted": [], "you denied": [], "blocked by policy": []}
    for x in messages:
        if x["role"] == "tool" and x["name"] == "delete_checkpoints":
            key = ("deleted" if x["content"].startswith("deleted") else
                   "you denied" if "denied" in x["content"] else "blocked by policy")
            outcome[key].append(paths[x["tool_call_id"]])
    lines = [f"Cancelled {', '.join(cancelled)}." if cancelled else "Cancelled nothing.",
             f"Deleted checkpoints {', '.join(outcome['deleted']) or 'none'}."]
    lines += [f"Not deleted ({why}): {', '.join(ps)}." for why, ps in outcome.items() if why != "deleted" and ps]
    if keep:
        lines.append(f"Left {', '.join(sorted(keep))} running as you asked.")
    return say(" ".join(lines))


SCRIPT = ["Leave job-130 alone, it's production.", ["approve", "approve"],
          ["approve", "deny: keep bob's checkpoints, he may resume job-121"]]


def human(state, turn):
    pending = [p for p in state["pending"] if "reply" not in p]
    print(f"\n  ⏸ the agent is waiting for you ({len(pending)} item{'s' * (len(pending) > 1)}):")
    for p in pending:
        what = p["args"].get("question") if p["name"] == "ask_user" else f"{p['name']}({json.dumps(p['args'])})"
        print(f"     {'question' if p['kind'] == 'human' else 'approve?'}: {what}")
    if args.interactive:
        replies = []
        for p in pending:
            hint = "your answer" if p["kind"] == "human" else "approve / always / deny: reason"
            replies.append(input(f"     {hint} > ").strip() or "approve")
    else:
        script = SCRIPT[turn] if turn < len(SCRIPT) else ["approve"] * len(pending)
        replies = [script] if isinstance(script, str) else script
        for r in replies:
            print(f"     you: {r}")
    return replies


def drive(llm, ckpt, crash_after=None):
    state = m.new_state(SYSTEM, TASK)
    turn = 0
    state = m.advance(llm, TOOLS, state, ckpt)
    while state["status"] == "waiting":
        m.respond(state, human(state, turn))
        turn += 1
        if crash_after is not None and turn == crash_after:
            CRASH["armed"] = True
        try:
            state = m.advance(llm, TOOLS, state, ckpt)
        except Crash:
            print("\n  💥 the agent process died while running approved actions. Restarting from the checkpoint...")
            state = m.load(ckpt)
            print(f"     checkpoint has {len(state['pending'])} pending item(s), "
                  f"{sum(1 for x in state['messages'] if x['role'] == 'tool')} tool results")
            state = m.advance(get_llm(args.model, policy), TOOLS, state, ckpt)
    return state, turn


try:
    cases = [(ToolCall("list_jobs", {}), "allow"), (ToolCall("cancel_job", {"job_id": "job-7"}), "ask"),
             (ToolCall("delete_checkpoints", {"path": "/ckpt/job-7"}), "ask"),
             (ToolCall("delete_checkpoints", {"path": "/ckpt"}), "deny"),
             (ToolCall("delete_checkpoints", {"path": "/ckpt/job-7/../.."}), "deny"),
             (ToolCall("ask_user", {"question": "?"}), "human"), (ToolCall("rm_rf", {}), "deny")]
    pol = m.ApprovalPolicy()
    got = [pol.decide(c, TOOLS.get(c.name)) for c, _ in cases]
    always = m.ApprovalPolicy(["cancel_job"]).decide(cases[1][0], cancel_job)
    table([(f"{c.name}({json.dumps(c.args)})", want, g) for (c, want), g in zip(cases, got)],
          ["call", "expected", "your policy"])
    policy_ok = got == [w for _, w in cases] and always == "allow"
    print(f"'always' for cancel_job -> {always}\n")

    ckpt = str(pathlib.Path(tempfile.mkdtemp()) / "run.json")
    llm = get_llm(args.model, policy)
    state, pauses = drive(llm, ckpt)
    print(f"\nanswer: {state['answer']}")
    print(f"actions that really happened: {EFFECTS}")
    msgs = state["messages"]
    auto = sum(1 for x in msgs if x["role"] == "tool" and x["name"] == "list_jobs")
    blocked = sum(1 for x in msgs if x["role"] == "tool" and x["content"].startswith("Blocked by policy"))
    first_effects = list(EFFECTS)

    print("\n---- again, but the process crashes after you approve the cancellations ----")
    EFFECTS.clear()
    state2, _ = drive(get_llm(args.model, policy), str(pathlib.Path(tempfile.mkdtemp()) / "run.json"), crash_after=2)
    counts = {e: EFFECTS.count(e) for e in EFFECTS}
    repeated = sum(n - 1 for n in counts.values())
    print(f"\nafter the crash and resume: {EFFECTS}\n  same answer: {state2['answer'] == state['answer']}")
except NotImplementedError as e:
    todo_hint(e, __file__)

record(interrupts=pauses, auto_allowed=auto, policy_blocked=blocked, jobs_cancelled=sum(e[0] == "cancel" for e in first_effects),
       repeated_after_crash=repeated)
ok = (policy_ok and ("cancel", "job-130") not in first_effects and ("delete", "/ckpt") not in first_effects
      and ("delete", "/ckpt/job-121") not in first_effects and repeated == 0 and state2["answer"] == state["answer"])
report(
    "a human-in-the-loop agent is a resumable state machine: risky calls pause the run and persist its state, "
    "the human's answer resumes it, and a crash loses nothing that was checkpointed",
    f"{pauses} pauses (1 question, 2 approval batches); {auto} call auto-allowed, {blocked} blocked by policy without asking "
    f"(rm -r /ckpt); job-130 kept because you said so; after a crash, {repeated} actions ran twice",
    "PASS" if ok else "CHECK: policy table, job-130 untouched, no /ckpt wipe, and nothing repeated after the crash",
    "run with --interactive and be the human: deny a cancellation and watch the agent adapt. Then think about "
    "the crash case where a tool had *partly* run: that is why real tools need idempotency keys",
)
