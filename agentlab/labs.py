"""The command line every lab shares, and the CLAIM / MEASURED / VERDICT report.

    python labs/02_agent_loop/run.py                 # your agent.py, mock model
    python labs/02_agent_loop/run.py --solution      # the reference solution.py
    python labs/02_agent_loop/run.py --model ollama:gpt-oss:20b --trace
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def lab_args(doc: str = "", extra=None):
    ap = argparse.ArgumentParser(description=doc)
    ap.add_argument("--solution", action="store_true", help="run the reference solution.py instead of agent.py")
    ap.add_argument("--model", default=os.environ.get("AGENTLAB_MODEL", "mock"),
                    help="mock (default), ollama:NAME, vllm:NAME, sglang:NAME or openai:NAME")
    ap.add_argument("--trace", action="store_true", help="print every model step and tool call")
    if extra:
        extra(ap)
    return ap.parse_args()


def load_impl(lab_file: str, use_solution: bool, student: str = "agent"):
    """Import your file (agent.py by default) or solution.py from the lab's folder."""
    lab_dir = pathlib.Path(lab_file).resolve().parent
    name = "solution" if use_solution else student
    spec = importlib.util.spec_from_file_location(f"{lab_dir.name}_{name}", lab_dir / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def header(lab_file: str, use_solution: bool, model: str, student: str = "agent"):
    lab = pathlib.Path(lab_file).resolve().parent.name
    print(f"[{lab}] using {'solution' if use_solution else student}.py, model {model}")


def table(rows, headers):
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(str(h)), *(len(r[i]) for r in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]
    print("  ".join(str(h).ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))


def report(claim, measured, verdict, next_step):
    print()
    print(f"CLAIM     {claim}")
    print(f"MEASURED  {measured}")
    print(f"VERDICT   {verdict}")
    print(f"NEXT      {next_step}")


def record(**values):
    """The numbers to type into the lesson's Measure step (tools/run_all.py checks them too)."""
    print("RECORD    " + "   ".join(f"{k} = {v}" for k, v in values.items()))


def todo_hint(err: NotImplementedError, lab_file: str, student: str = "agent"):
    lab = pathlib.Path(lab_file).resolve().parent.name
    raise SystemExit(f"\n{lab}/{student}.py is not finished: {err}\n"
                     f"Fill in the TODOs, or run with --solution to see the reference.")
