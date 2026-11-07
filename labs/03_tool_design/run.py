"""Check Lab 03: tool choice from descriptions, recoverable errors, argument coercion.

Usage: python labs/03_tool_design/run.py [--solution] [--trace]
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agentlab import Tool, get_llm  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, table, todo_hint  # noqa: E402
from agentlab.loop import run_agent  # noqa: E402
from agentlab.mock import call, first_user, say, tool_results  # noqa: E402
from agentlab.tools import tool  # noqa: E402
from agentlab.trace import Printer  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)

# ---- Part A: which tool would a model pick? -------------------------------------------------
STOP = set("a an the of to in on for and or is are what which how do does i my me it be by with from at as this that "
           "item items thing things get set use".split())


def words(s):
    return {w[:5] for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP}


def pick(task, tools):
    """A weak model: picks the tool whose name and description share the most words with the task."""
    def text(t):
        params = " ".join(p.get("description", "") + " " + k for k, p in t.parameters["properties"].items())
        return t.name.replace("_", " ") + " " + t.description + " " + params
    scores = [(len(words(task) & words(text(t))), -i, t.name) for i, t in enumerate(tools)]
    return max(scores)[2]


def T(tool_name, desc, **params):
    props = {k: {"type": "string", "description": v} for k, v in params.items()}
    return Tool(name=tool_name, description=desc, parameters={"type": "object", "properties": props,
                                                         "required": list(params)}, fn=lambda **kw: "")


VAGUE = [T("query", "Query the system.", q="query"), T("get", "Get an item.", id="id"),
         T("list", "List things.", kind="kind"), T("update", "Update an item.", id="id", value="value"),
         T("stats", "Get stats.", name="name")]
GOOD = [
    T("search_runbooks", "Search the on-call runbooks and how-to guides by keyword, e.g. how to restart, drain, "
      "rotate or roll back a service.", query="keywords"),
    T("get_job_status", "Get the state, GPU count, step and last log line of a training job.",
      job_id="training job id, like job-123"),
    T("list_gpu_nodes", "List GPU nodes in a region with their free GPUs; use it to find capacity for a new job.",
      region="region such as us-east"),
    T("scale_deployment", "Change the number of replicas of a model serving deployment.",
      name="deployment name", replicas="replica count"),
    T("get_service_metrics", "p50/p99 latency, error rate and QPS of a serving service over the last hour.",
      service="service name"),
]
# (task, the tool a good agent would use; VAGUE tools listed in the same order as GOOD)
TASKS = [
    ("How do I roll back the chat-api service?", 0), ("Show the runbook for draining a node", 0),
    ("Is training job job-123 still running?", 1), ("What step is job job-88 at, and how many GPUs does it use?", 1),
    ("Find free GPUs in us-east for a new job", 2), ("Which GPU nodes in eu-west have capacity?", 2),
    ("Scale the llama-serving deployment to 6 replicas", 3), ("Add replicas to the embedding deployment", 3),
    ("What is the p99 latency of chat-api?", 4), ("Is the error rate of the ranker service up in the last hour?", 4),
    ("How do I rotate the API key of a service?", 0), ("Show the last log line of job-7", 1),
]
acc = {}
for label, tools in (("vague", VAGUE), ("good", GOOD)):
    acc[label] = sum(pick(task, tools) == tools[want].name for task, want in TASKS)
rows = [(task[:52], pick(task, VAGUE), pick(task, GOOD), GOOD[want].name) for task, want in TASKS]
print("Part A: tool choice by a weak model that matches words (what a real model's attention does far better)")
table(rows, ["task", "picked (vague)", "picked (good)", "right tool"])
print(f"right tool: vague names {acc['vague']}/{len(TASKS)}, descriptive names and descriptions {acc['good']}/{len(TASKS)}\n")

# ---- Parts B and C: errors and arguments ------------------------------------------------------
JOBS = {"job-7": "running, 8 GPUs, step 1200, last log: loss 2.31",
        "job-88": "running, 64 GPUs, step 54000, last log: checkpoint saved",
        "job-121": "failed, 16 GPUs, step 300, last log: CUDA out of memory",
        "job-123": "running, 32 GPUs, step 9100, last log: loss 1.87"}
DEPLOYMENTS = {"chat-api": 2, "llama-serving": 4, "embedder": 1}


@tool
def get_job_status(job_id: str) -> str:
    """Get the state, GPU count, step and last log line of a training job.

    Args:
        job_id: training job id, like job-123
    """
    if job_id not in JOBS:
        raise m.NotFound("job", job_id, JOBS)
    return f"{job_id}: {JOBS[job_id]}"


@tool(risk="write")
def scale_deployment(name: str, replicas: int) -> str:
    """Change the number of replicas of a model serving deployment.

    Args:
        name: deployment name
        replicas: replica count
    """
    if name not in DEPLOYMENTS:
        raise m.NotFound("deployment", name, DEPLOYMENTS)
    if not isinstance(replicas, int):
        raise TypeError(f"replicas must be an integer, got {replicas!r}")
    old, DEPLOYMENTS[name] = DEPLOYMENTS[name], replicas
    return f"{name}: {old} -> {replicas} replicas"


def policy(messages, tools):
    """A model that copies ids from the user (typos and all) and sends numbers as strings."""
    task = first_user(messages)
    results = [c for _, c in tool_results(messages)]
    last = results[-1] if results else None
    if last and not last.startswith("Error"):
        return say(f"Done: {last}")
    if last and "Did you mean: " in last:
        fixed = re.search(r"Did you mean: ([\w-]+)", last).group(1)
        prev = [c for c in messages if c.get("tool_calls")][-1]["tool_calls"][0]["function"]["name"]
        key = "job_id" if prev == "get_job_status" else "name"
        extra = {} if prev == "get_job_status" else {"replicas": re.search(r"(\d+) replicas", task).group(1)}
        return call(prev, **{key: fixed}, **extra)
    if last:
        return say("I couldn't complete that: " + last)
    if "scale" in task.lower():
        name, n = re.search(r"Scale (\S+) to (\d+) replicas", task).groups()
        return call("scale_deployment", name=name, replicas=n)  # a string, as models often send
    return call("get_job_status", job_id=re.search(r"(job-?\w+)", task).group(1))


def solve(task, execute):
    llm = get_llm("mock", policy)
    r = run_agent(llm, [get_job_status, scale_deployment], task, execute=execute,
                  on_event=Printer() if args.trace else None)
    return r


def bare(c):
    t = {"get_job_status": get_job_status, "scale_deployment": scale_deployment}[c.name]
    try:
        return str(t.fn(**c.args))
    except Exception as e:  # noqa: BLE001
        return f"Error: {type(e).__name__}: {e}"


TYPO_TASKS = ["What is the status of job-12?", "Is job-8 still running?", "Status of job-1233 please",
              "Scale chat-ap to 3 replicas"]
TYPE_TASKS = ["Scale chat-api to 3 replicas", "Scale llama-serving to 8 replicas", "Scale embedder to 2 replicas"]
try:
    def mine(c):
        return m.call_tool({"get_job_status": get_job_status, "scale_deployment": scale_deployment}[c.name], c.args)
    rows = []
    rec = {"bare": 0, "mine": 0}
    for task in TYPO_TASKS:
        a, b = solve(task, bare), solve(task, mine)
        rec["bare"] += a.answer.startswith("Done")
        rec["mine"] += b.answer.startswith("Done")
        rows.append((task, a.answer[:42], b.answer[:60]))
    print("Part B: ids with typos")
    table(rows, ["task", "bare exception", "helpful_error"])
    first_try = {"bare": 0, "mine": 0}
    for task in TYPE_TASKS:
        for label, ex in (("bare", bare), ("mine", mine)):
            r = solve(task, ex)
            first_try[label] += r.steps == 2 and r.answer.startswith("Done")
    print(f"\nPart C: numbers sent as strings: succeeded first try without coercion {first_try['bare']}/{len(TYPE_TASKS)}, "
          f"with coerce_args {first_try['mine']}/{len(TYPE_TASKS)}")
    sample = m.helpful_error(m.NotFound("job", "job-12", JOBS), get_job_status)
    print(f"\nyour error message: {sample}")
except NotImplementedError as e:
    todo_hint(e, __file__)

record(vague_ok=acc["vague"], good_ok=acc["good"], recovered_bare=rec["bare"], recovered_helpful=rec["mine"],
       first_try_coerced=first_try["mine"])
report(
    "tools are a user interface for the model: clear names and descriptions decide which tool it picks, error "
    "messages that say how to fix the call let it recover, and coercing arguments removes whole classes of mistakes",
    f"right tool {acc['vague']}/12 with vague tools vs {acc['good']}/12 with descriptive ones; typo'd ids recovered "
    f"{rec['bare']}/4 with bare exceptions vs {rec['mine']}/4 with helpful errors; string numbers worked first try "
    f"{first_try['bare']}/3 vs {first_try['mine']}/3 with coercion",
    "PASS" if rec["mine"] == 4 and first_try["mine"] == 3 else "CHECK: helpful errors should recover all 4, coercion all 3",
    "rewrite one of the VAGUE tools in run.py until the weak model picks it correctly; notice you are writing "
    "documentation for a reader that has nothing else to go on",
)
