"""Check Lab 10: 10 tasks x 8 trials of a stochastic agent, graded on outcome and trajectory.

Usage: python labs/10_evals/run.py [--solution] [--model ollama:NAME] [--trials 8]
"""
import json
import pathlib
import random
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agentlab import get_llm  # noqa: E402
from agentlab.kb import calculator, lookup  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, table, todo_hint  # noqa: E402
from agentlab.loop import run_agent  # noqa: E402
from agentlab.mock import call, calls_made, results_of, say  # noqa: E402
from agentlab.tools import tool  # noqa: E402

args = lab_args(__doc__, lambda ap: ap.add_argument("--trials", type=int, default=8))
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)


@tool(risk="write")
def send_email(to: str, body: str) -> str:
    """Send an email.

    Args:
        to: recipient address
        body: the message
    """
    return f"sent to {to}"


# (id, question, topic to look up, expected substring, how often the agent gets it right)
TASKS = [
    ("t01", "How much HBM does an H100 have?", "H100", "80 GB", 0.95),
    ("t02", "What is the memory bandwidth of a B200?", "B200", "8 TB/s", 0.9),
    ("t03", "How many parameters does gpt-oss-20b activate per token?", "gpt-oss-20b", "3.6 billion", 0.6),
    ("t04", "What is the power draw of an L4?", "L4", "72 W", 0.95),
    ("t05", "How many dense BF16 TFLOP/s does an A100 do?", "A100", "312 TFLOP/s", 0.85),
    ("t06", "How many KV heads does Llama 3 70B have?", "Llama-3-70B", "8 KV heads", 0.7),
    ("t07", "How many bytes per value does BF16 use?", "BF16", "2 bytes", 0.98),
    ("t08", "How much HBM do 4 B200s have in total, in GB?", "B200", "768", 0.75),
    ("t09", "How many layers does Llama 3 70B have?", "Llama-3-70B", "80 layers", 0.9),
    ("t10", "What is the memory bandwidth of an H100?", "H100", "3.35 TB/s", 0.8),
]
P_EMAIL = 0.12  # sometimes it "helpfully" emails the answer, which nobody asked for


def agent_policy(task, trial):
    tid, question, topic, expect, p = task
    rng = random.Random(f"{tid}-{trial}")
    right, emails = rng.random() < p, rng.random() < P_EMAIL

    def policy(messages, tools):
        if right and not results_of(messages, "lookup"):
            return call("lookup", topic=topic)
        if tid == "t08" and right and not results_of(messages, "calculator"):
            gb = re.search(r"(\d+) GB", results_of(messages, "lookup")[0]).group(1)
            return call("calculator", expression=f"4 * {gb}")
        if right:
            fact = results_of(messages, "calculator")[-1] + " GB" if tid == "t08" else results_of(messages, "lookup")[0]
            answer = f"From the knowledge base: {fact}"
        else:
            answer = "I believe it is " + re.sub(r"\d+(\.\d+)?", lambda x: str(round(float(x.group()) * 1.5, 1)), expect)
        if emails and not results_of(messages, "send_email"):
            return call("send_email", to="me@example.com", body=answer)
        return say(answer)
    return policy


trace_path = pathlib.Path(tempfile.mkdtemp()) / "eval_runs.jsonl"
try:
    print(f"pass@k and pass^k for n=10 samples, c=7 passes: "
          f"pass@1={m.pass_at_k(10, 7, 1):.3f} pass@4={m.pass_at_k(10, 7, 4):.3f} pass^4={m.pass_hat_k(10, 7, 4):.3f}\n")
    results, rows = {}, []
    with open(trace_path, "w") as out:
        for task in TASKS:
            grades = []
            for trial in range(args.trials):
                llm = get_llm(args.model, agent_policy(task, trial))
                run = run_agent(llm, [lookup, calculator, send_email], task[1])
                used = [c.name for c in calls_made(run.messages)]
                g = m.grade({"expect": task[3], "forbidden": ["send_email"], "max_steps": 4}, run, used)
                grades.append(g)
                out.write(json.dumps({"task": task[0], "trial": trial, "grade": g, "messages": run.messages}) + "\n")
            results[task[0]] = grades
            c = sum(g["passed"] for g in grades)
            why = sorted({r.split(" ")[0] + " " + r.split(" ")[1] for g in grades for r in g["reasons"]})
            rows.append((task[0], task[1][:46], f"{c}/{args.trials}", ", ".join(why)))
    table(rows, ["task", "question", "passed", "failure kinds"])
    s = m.summarize(results, 4)
except NotImplementedError as e:
    todo_hint(e, __file__)

print(f"\n{json.dumps(s)}\nevery trajectory is in {trace_path} (one JSON line per run: read a few failures!)")
record(**{"pass1": s["pass@1"], "pass_at_4": s["pass@4"], "pass_hat_4": s["pass^4"], "outcome_pass1": s["outcome_pass@1"]})
report(
    "one run of a stochastic agent tells you little: pass@k asks whether it can succeed, pass^k whether it "
    "succeeds every time, and grading the trajectory catches right answers reached the wrong way",
    f"pass@1 {s['pass@1']}, pass@4 {s['pass@4']}, pass^4 {s['pass^4']}; grading only the answer would report "
    f"pass@1 {s['outcome_pass@1']} and miss the unrequested emails",
    "PASS" if s["pass@4"] > s["pass@1"] > s["pass^4"] and s["outcome_pass@1"] > s["pass@1"] else "CHECK: expected pass@4 > pass@1 > pass^4",
    "open the JSONL and read five failing trajectories before changing anything: error analysis beats metrics. "
    "Then add an LLM-as-judge grader and measure how often it disagrees with the exact checks",
)
