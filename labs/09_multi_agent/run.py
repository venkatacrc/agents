"""Check Lab 09: one agent reading everything vs a lead with three parallel researchers.

Usage: python labs/09_multi_agent/run.py [--solution] [--model ollama:NAME]
"""
import pathlib
import re
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1]), str(HERE)]

from agentlab import get_llm, tokens  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, table, todo_hint  # noqa: E402
from agentlab.loop import run_agent  # noqa: E402
from agentlab.mock import call, first_user, results_of, say, system_text  # noqa: E402
from agentlab.tools import tool  # noqa: E402
from corpus import DOCS, search_docs  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)


@tool
def search(query: str) -> str:
    """Search the serving-techniques library; returns up to 3 document names.

    Args:
        query: keywords, e.g. "prefix caching"
    """
    return ", ".join(search_docs(query)) or "no documents found"


@tool
def read(doc: str) -> str:
    """Read a document from the library.

    Args:
        doc: a document name returned by search
    """
    return DOCS[doc]


TOPICS = ["speculative decoding", "prefix caching", "FP8 quantization"]
TASK = ("Compare speculative decoding, prefix caching and FP8 quantization for an LLM serving team: for each, "
        "the speed-up or saving it gives and its main caveat.")


def finding_from(messages):
    text = "\n".join(results_of(messages, "read"))
    key = re.findall(r"Key result: ([^\n]*)", text)
    cav = re.findall(r"Caveat: ([^\n]*)", text)
    return key, cav


def research(messages, topics):
    """Search each topic, read every hit about it, then answer from the Key result / Caveat lines."""
    searched = results_of(messages, "search")
    if len(searched) < len(topics):
        return call("search", query=topics[len(searched)])
    hits = [d for s in searched for d in s.split(", ") if any(w in d for t in topics for w in t.lower().split()[:1])]
    read_docs = [c.get("tool_calls")[0]["function"]["arguments"] for c in messages if c.get("tool_calls")
                 and c["tool_calls"][0]["function"]["name"] == "read"]
    todo = [d for d in hits if not any(f'"{d}"' in r for r in read_docs)]
    if todo:
        return call("read", doc=todo[0])
    return None


def policy(messages, tools):
    system, user = system_text(messages), first_user(messages)
    if system.startswith("You lead"):
        return say("\n".join(f"- What speed-up or saving does {t} give, and what is its main caveat?" for t in TOPICS))
    if system.startswith("You write the final brief"):
        parts = re.findall(r"Question: What speed-up or saving does (.*?) give.*?\nFinding: (.*?)(?=\n\nQuestion:|\Z)", user, re.S)
        return say("Brief:\n" + "\n".join(f"- {t}: {f.strip()}" for t, f in parts))
    if system.startswith("You research one question"):
        topic = next(t for t in TOPICS if t.lower() in user.lower())
        nxt = research(messages, [topic])
        if nxt:
            return nxt
        key, cav = finding_from(messages)
        return say(f"{key[0]} {cav[0]} (sources: {', '.join(d for s in results_of(messages, 'search') for d in s.split(', ') if topic.split()[0].lower() in d)})")
    nxt = research(messages, TOPICS)  # the single agent does everything in one context
    if nxt:
        return nxt
    key, cav = finding_from(messages)
    return say("Brief:\n" + "\n".join(f"- {t}: {k} {c}" for t, k, c in zip(TOPICS, key, cav)))


def peak(llm, prefix):
    sizes = [tokens.count_messages(msgs) + tokens.count_tools(tl) for msgs, tl in llm.requests
             if (msgs[0].get("content") or "").startswith(prefix)]
    return max(sizes) if sizes else 0


latency = 0.15 if args.model == "mock" else 0.0
single = get_llm(args.model, policy, latency=latency)
t0 = time.perf_counter()
r = run_agent(single, [search, read], TASK, max_steps=20)
single_s = time.perf_counter() - t0
try:
    multi = get_llm(args.model, policy, latency=latency)
    t0 = time.perf_counter()
    brief, questions, findings = m.orchestrate(multi, TASK, [search, read])
    multi_s = time.perf_counter() - t0
except NotImplementedError as e:
    todo_hint(e, __file__)

print("lead's questions:\n  " + "\n  ".join(questions) + f"\n\n{brief}\n")
lead_peak = max(peak(multi, "You lead"), peak(multi, "You write"))
sub_peak = peak(multi, "You research")
table([("one agent", f"{single.peak_prompt_tokens:,}", "-", f"{single.prompt_tokens:,}", single.calls, f"{single_s:.1f} s"),
       ("lead + 3 researchers", f"{lead_peak:,}", f"{sub_peak:,}", f"{multi.prompt_tokens:,}", multi.calls, f"{multi_s:.1f} s")],
      ["setup", "peak context (lead)", "peak (researcher)", "total prompt tokens", "model calls", "wall time"])
same = all(k in brief for k in re.findall(r"Key result: ([^\n]{20})", "\n".join(DOCS[d] for d in DOCS if any(t.split()[0].lower() in d for t in TOPICS))))
record(single_peak=single.peak_prompt_tokens, lead_peak=lead_peak, sub_peak=sub_peak,
       single_total=single.prompt_tokens, multi_total=multi.prompt_tokens)
report(
    "sub-agents buy context isolation and parallelism: the lead never sees raw documents, each researcher sees "
    "only its own, and they run at the same time. Total cost depends on how much each researcher explores",
    f"the lead's peak context is {lead_peak:,} tokens vs {single.peak_prompt_tokens:,} for one agent reading "
    f"everything; total prompt tokens {multi.prompt_tokens:,} vs {single.prompt_tokens:,}; wall time {multi_s:.1f} s "
    f"vs {single_s:.1f} s",
    "PASS" if same and lead_peak < single.peak_prompt_tokens / 2 and len(findings) == 3
    else "CHECK: the brief should keep all three key results and the lead's context should stay small",
    "make each researcher read 10 documents instead of 2 and watch total tokens overtake the single agent, as in "
    "production research systems; then ask when the trade is worth it (broad, parallel research) and when it "
    "isn't (tightly coupled coding tasks)",
)
