"""Lab 05: workflows. LLM calls wired together by your code along fixed paths.

Run:  python labs/05_workflows/run.py             (your code)
      python labs/05_workflows/run.py --solution

Workflows are cheaper, faster and more predictable than agents when you know the steps in
advance. Three of the patterns from Anthropic's "Building effective agents":
  route              classify the input, then hand it to a specialised prompt
  fan_out            the same prompt over many inputs, in parallel
  evaluate_optimize  one call writes, another grades against a rubric, repeat until it passes
"""
from concurrent.futures import ThreadPoolExecutor  # noqa: F401


def ask(llm, system, user):
    """One model call with a system and a user message; returns the reply text."""
    return llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}]).text.strip()


def route(llm, ticket, routes):
    """routes: {label: system prompt of the specialist}. Return (label, specialist answer).

    1. Ask the model to classify: system "Classify the support ticket. Reply with exactly one of: a, b, c."
    2. Find which label appears in its (lower-cased) reply. None -> ("other", an escalation message).
    3. Answer the ticket with ask(llm, routes[label], ticket).
    """
    # TODO 1
    raise NotImplementedError("route")


def fan_out(llm, system, items, workers=8):
    """ask(llm, system, item) for every item, `workers` at a time, results in input order."""
    # TODO 2: ThreadPoolExecutor(max_workers=workers) and pool.map
    raise NotImplementedError("fan_out")


def evaluate_optimize(llm, task, rubric, max_rounds=5):
    """Return (final draft, rounds used, [(draft, verdict), ...]).

    draft = ask(llm, "You write release notes.", task)
    each round: verdict = ask(llm, "You review drafts against this rubric:\\n" + rubric +
                              "\\nReply PASS, or FAIL: followed by what is missing.", draft)
                PASS -> done. Otherwise rewrite: ask the writer again with the task, the previous
                draft and the feedback (include the words "Reviewer feedback:" before the verdict).
    """
    # TODO 3
    raise NotImplementedError("evaluate_optimize")
