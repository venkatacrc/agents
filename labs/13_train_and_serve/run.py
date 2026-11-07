"""Check Lab 13: rollouts -> rewards -> GRPO advantages -> an SFT example, then prefix-cache hit rates.

Usage: python labs/13_train_and_serve/run.py [--solution]
"""
import json
import pathlib
import re
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from agentlab import get_llm  # noqa: E402
from agentlab.kb import calculator, lookup  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, table, todo_hint  # noqa: E402
from agentlab.loop import run_agent  # noqa: E402
from agentlab.mock import call, results_of, say  # noqa: E402
from agentlab.tools import tool  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)
render = load_impl(str(HERE.parent / "00_first_call" / "run.py"), True).render_chat  # Lab 00's template
TASK = "How much HBM do 8 H100s and 4 A100s (80 GB version) have together, in GB?"
TOOLS = [lookup, calculator]


def style_policy(style):
    """Four ways a policy model might attempt the task; sampling picks one per rollout."""
    def policy(messages, tools):
        facts = results_of(messages, "lookup")
        sums = results_of(messages, "calculator")
        if style == "parallel":
            if not facts:
                return [call("lookup", topic="H100"), call("lookup", topic="A100")]
        elif style in ("sequential", "guess"):
            if len(facts) < 2:
                return call("lookup", topic=["H100", "A100"][len(facts)])
        elif style == "dithering":
            if len(facts) < 5:
                return call("lookup", topic=["H100", "A100", "H100 SXM", "A100 80GB", "H100"][len(facts)])
        if style == "guess":
            return say("Roughly 8 x 80 + 4 x 80 = 980 GB.")  # does the arithmetic in its head, wrongly
        if not sums:
            return call("calculator", expression="8 * 80 + 4 * 80")
        return say(f"Together they have {sums[-1]} GB of HBM.")
    return policy


GEN = "<|im_start|>assistant\n"


def chatml_segments(messages, tools):
    """Lab 00's ChatML rendering, cut into (text, trained) pieces. Only the assistant's own output is trained."""
    full = render(messages, tools)[: -len(GEN)]
    segs, pos = [], 0
    for i in range(1, len(messages) + 1):
        upto = render(messages[:i], tools)[: -len(GEN)]
        if not full.startswith(upto):
            continue  # inside a group of tool results that share one user turn
        piece, pos = upto[pos:], len(upto)
        if messages[i - 1]["role"] == "assistant":
            segs += [(GEN, False), (piece[len(GEN):], True)]
        else:
            segs.append((piece, False))
    return segs


try:
    styles = ["parallel", "sequential", "guess", "parallel", "dithering", "sequential", "guess", "parallel"]
    runs = [run_agent(get_llm("mock", style_policy(s)), TOOLS, TASK) for s in styles]
    rewards = [m.reward(r, "960") for r in runs]
    adv = m.group_advantages(rewards)
    print("a group of 8 rollouts for one prompt (GRPO):")
    table([(i, s, r.steps, f"{w:+.2f}", f"{a:+.2f}", r.answer[:44]) for i, (s, r, w, a) in
           enumerate(zip(styles, runs, rewards, adv))], ["rollout", "behaviour", "model calls", "reward", "advantage", "answer"])

    best = runs[max(range(8), key=lambda i: adv[i])]
    segs = chatml_segments(best.messages, TOOLS)
    assert "".join(t for t, _ in segs) + GEN == render(best.messages, TOOLS), "segments must re-join"
    ids, mask = m.sft_example(segs)
    frac = sum(mask) / len(ids)
    out = pathlib.Path(tempfile.mkdtemp()) / "sft.jsonl"
    out.write_text(json.dumps({"messages": best.messages, "tools": [t.schema() for t in TOOLS]}) + "\n")
    print(f"\nSFT example from the best rollout: {len(ids)} tokens, {sum(mask)} with loss ({frac:.1%}). "
          f"Trained spans:\n  " + "\n  ".join(repr(t) for t, tr in segs if tr) + f"\n  (OpenAI-format record written to {out})")

    # ---- serving: what a prefix cache can reuse across the steps of a longer run ----
    docs = {f"doc_{i:02d}": f"Notes {i}: " + " ".join(f"measurement {i}.{k} is {k * i % 97}" for k in range(40))
            for i in range(12)}

    @tool
    def read_doc(name: str) -> str:
        """Read a document.

        Args:
            name: doc_00 to doc_11
        """
        return docs[name]

    def reader(messages, tools):
        done = len(results_of(messages, "read_doc"))
        return call("read_doc", name=f"doc_{done:02d}") if done < len(docs) else say("Read all 12 documents.")

    llm = get_llm("mock", reader)
    run_agent(llm, [read_doc, lookup, calculator], "Read all the docs and summarize them.", max_steps=20)
    reqs = llm.requests

    def variant(kind):
        prompts = []
        for i, (msgs, tools) in enumerate(reqs):
            msgs = [dict(x) for x in msgs]
            if kind == "timestamp":
                msgs[0]["content"] = f"Current time: 06:00:{i:02d}. " + msgs[0]["content"]
            if kind == "tool order":
                tools = tools[i % len(tools):] + tools[: i % len(tools)]
            if kind == "rewrite old results":
                tool_idx = [k for k, x in enumerate(msgs) if x["role"] == "tool"]
                for k in tool_idx[:-2]:
                    msgs[k]["content"] = "[old result elided]"
            prompts.append(render(msgs, tools))
        return m.prefix_hit_rate(prompts)

    hits = {k: variant(k) for k in ("append-only", "timestamp", "tool order", "rewrite old results")}
    print(f"\nprefix-cache hit rate over the {len(reqs)} requests of a 12-document run:")
    table([(k, f"{v:.1%}") for k, v in hits.items()], ["harness behaviour", "prompt tokens served from cache"])
except NotImplementedError as e:
    todo_hint(e, __file__)

record(trained_frac=round(frac, 3), best_advantage=round(max(adv), 2), hit_append=round(hits["append-only"], 3),
       hit_timestamp=round(hits["timestamp"], 3), hit_rewrite=round(hits["rewrite old results"], 3))
report(
    "the harness shapes training and serving: trajectories become SFT data with loss only on the model's own "
    "tokens, verifiable rewards rank rollouts against their group, and an append-only history lets the prefix "
    "cache skip almost all prefill",
    f"{frac:.1%} of the best trajectory's tokens carry loss; the best rollout's advantage is {max(adv):+.2f}; "
    f"prefix-cache hits {hits['append-only']:.0%} append-only vs {hits['timestamp']:.0%} with a timestamp in the "
    f"system prompt and {hits['rewrite old results']:.0%} when old results are rewritten",
    "PASS" if hits["append-only"] > 0.85 and hits["timestamp"] < 0.05 and max(adv) > 0 else "CHECK",
    "serve a real model with vLLM (--enable-prefix-caching) or SGLang (RadixAttention), run Lab 04 against it with "
    "--model vllm:NAME, and compare time to first token per step with and without compaction",
)
