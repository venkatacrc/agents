"""Lab 09: multi-agent research. A lead agent plans, sub-agents research in parallel, each in a fresh
context, and only their short findings come back.

Run:  python labs/09_multi_agent/run.py             (your code)
      python labs/09_multi_agent/run.py --solution

This is the orchestrator-worker shape of deep-research systems. The win is context isolation: the lead
never reads the raw documents. The cost is more total tokens.
"""
from concurrent.futures import ThreadPoolExecutor  # noqa: F401

from agentlab.loop import run_agent  # noqa: F401  run_agent(llm, tools, task, system=..., max_steps=...)

LEAD = ("You lead a research team. Split the task into independent research questions, one per line, "
        "each answerable on its own. Reply with the questions only.")
RESEARCHER = ("You research one question with search and read. Reply with a finding of at most three sentences "
              "that quotes the key numbers and caveats and names the documents you used.")
WRITER = "You write the final brief from your team's findings. Be concise and keep every number."


def subagent(llm, question, tools, max_steps=8):
    """Run a fresh agent (system=RESEARCHER) on one question; return its final answer, stripped.
    It starts with an empty history: it knows only the question."""
    # TODO 1
    raise NotImplementedError("subagent")


def orchestrate(llm, task, tools, workers=4):
    """Return (brief, questions, findings).

    1. Ask the lead (system LEAD) for questions; one per non-empty line, strip bullets and numbering.
    2. Run subagent() for every question in parallel (ThreadPoolExecutor(max_workers=workers)).
    3. One WRITER call with the task and every "Question: ...\\nFinding: ..." pair.
    """
    # TODO 2
    raise NotImplementedError("orchestrate")
