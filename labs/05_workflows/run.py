"""Check Lab 05: routing support tickets, parallel summaries, and an evaluator loop.

Usage: python labs/05_workflows/run.py [--solution] [--model ollama:NAME]
"""
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agentlab import get_llm  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, table, todo_hint  # noqa: E402
from agentlab.mock import last_user, say, system_text  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)

ROUTES = {
    "billing": "You are the billing specialist for an inference platform. Explain charges and credits.",
    "outage": "You are the on-call engineer. Acknowledge, give the status page, and ask for request ids.",
    "howto": "You are a solutions engineer. Answer with concrete steps and a code snippet.",
    "feature": "You are the product manager. Thank them and explain how requests are prioritised.",
}
TICKETS = [
    ("I was charged twice for the same month on my invoice", "billing"),
    ("All requests to the llama-70b endpoint return 503 since 09:10 UTC", "outage"),
    ("How do I stream tokens from the API with Python?", "howto"),
    ("Please add support for structured JSON output", "feature"),
    ("Our credits disappeared after the plan upgrade", "billing"),
    ("Latency is 30 seconds and requests time out, is the service down?", "outage"),
    ("What is the right way to set max_tokens for long documents?", "howto"),
    ("It would be great to have a batch API with a 50% discount", "feature"),
]
KEYWORDS = {"billing": ["charge", "invoice", "credit", "refund", "plan"],
            "outage": ["503", "down", "time out", "timeout", "error rate", "outage"],
            "howto": ["how do i", "how to", "right way", "example"],
            "feature": ["please add", "would be great", "support for", "feature"]}
DOCS = [f"Model card {i}: a {n}B-parameter decoder, context {c}K, trained on {t}T tokens."
        for i, (n, c, t) in enumerate([(8, 128, 15), (70, 128, 15), (7, 32, 2), (27, 128, 14),
                                       (20, 128, 8), (120, 128, 12), (3, 8, 9), (405, 128, 15)])]
TASK = ("Write a release note for upgrading the serving fleet from vLLM 0.9 to 0.10. Readers are on-call engineers.")
RUBRIC = ("1. names both versions (0.9 and 0.10)\n2. states the breaking change: the --enable-prefix-caching flag "
          "is now on by default\n3. gives the rollback command: kubectl rollout undo deploy/vllm\n4. under 60 words")
NEEDS = [("version", r"0\.9.*0\.10", "both version numbers"),
         ("breaking", r"prefix.caching", "the breaking change (prefix caching on by default)"),
         ("rollback", r"rollout undo", "the rollback command (kubectl rollout undo deploy/vllm)")]
ADD = {"version": "vLLM goes from 0.9 to 0.10.",
       "breaking": "Breaking: --enable-prefix-caching is now on by default.",
       "rollback": "Roll back with: kubectl rollout undo deploy/vllm."}


def policy(messages, tools):
    system, user = system_text(messages), last_user(messages)
    if system.startswith("Classify"):
        low = user.lower()
        scores = {k: sum(w in low for w in ws) for k, ws in KEYWORDS.items()}
        best = max(scores, key=scores.get)
        return say(best if scores[best] else "unsure")
    if system in ROUTES.values():
        team = next(k for k, v in ROUTES.items() if v == system)
        return say(f"[{team}] Thanks, we are on it: {user[:40]}")
    if system.startswith("You summarize"):
        n, c = re.search(r"a (\d+)B-parameter decoder, context (\d+)K", user).groups()
        return say(f"{n}B params, {c}K context")
    if system.startswith("You review"):
        missing = [why for _, pat, why in NEEDS if not re.search(pat, user, re.S)]
        if len(user.split()) >= 60:
            missing.append("shorter text (under 60 words)")
        return say("PASS" if not missing else "FAIL: missing " + "; ".join(missing))
    if system.startswith("You write"):
        draft = re.search(r"Your previous draft:\n(.*?)\n\nReviewer", user, re.S)
        text = draft.group(1) if draft else "We upgraded the serving fleet to a new vLLM release."
        feedback = user.split("Reviewer feedback:")[-1] if draft else ""
        # A writer that fixes one thing per round, the first thing the reviewer listed.
        for key, _, why in NEEDS:
            if why in feedback:
                return say(text + " " + ADD[key])
        return say(text)
    return say("?")


try:
    llm = get_llm(args.model, policy, latency=0.25 if args.model == "mock" else 0.0)
    rows, routed_ok = [], 0
    for ticket, want in TICKETS:
        label, answer = m.route(llm, ticket, ROUTES)
        routed_ok += label == want
        rows.append((ticket[:50], want, label, answer[:40]))
    print("routing:")
    table(rows, ["ticket", "should go to", "routed to", "answer"])

    t0 = time.perf_counter()
    seq = [m.ask(llm, "You summarize model cards in a few words.", d) for d in DOCS]
    seq_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    par = m.fan_out(llm, "You summarize model cards in a few words.", DOCS, workers=8)
    par_s = time.perf_counter() - t0
    same = seq == par
    print(f"\nfan-out over {len(DOCS)} documents: sequential {seq_s:.2f} s, parallel {par_s:.2f} s "
          f"({seq_s / par_s:.1f}x), same results in the same order: {same}")

    draft, rounds, history = m.evaluate_optimize(llm, TASK, RUBRIC)
    print("\nevaluator-optimizer:")
    for i, (d, v) in enumerate(history, 1):
        print(f"  round {i}: {v[:90]}")
    print(f"  final draft ({len(draft.split())} words): {draft}")
except NotImplementedError as e:
    todo_hint(e, __file__)

record(routed_ok=routed_ok, seq_s=round(seq_s, 2), par_s=round(par_s, 2), rounds=rounds)
report(
    "when the steps are known, plain code around LLM calls beats an agent: routing sends each input to a focused "
    "prompt, independent calls run in parallel, and a grader with an explicit rubric drives revisions",
    f"routed {routed_ok}/{len(TICKETS)} tickets correctly; {len(DOCS)} summaries in {par_s:.2f} s parallel vs "
    f"{seq_s:.2f} s sequential; the draft passed the rubric after {rounds} review rounds",
    "PASS" if routed_ok == len(TICKETS) and same and par_s < seq_s / 3 and rounds == 4
    else "CHECK: expected 8/8 routes, a parallel speed-up, and a pass in round 4",
    "count the model calls of each pattern (llm.calls) and compare with what an agent would spend deciding the "
    "same steps for itself",
)
