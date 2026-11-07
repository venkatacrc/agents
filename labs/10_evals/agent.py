"""Lab 10: evaluating agents. Agents are stochastic, so one run tells you little; and a right answer
reached the wrong way is still a failure.

Run:  python labs/10_evals/run.py             (your code)
      python labs/10_evals/run.py --solution
"""
from math import comb  # noqa: F401  comb(n, k) = n choose k


def pass_at_k(n, c, k):
    """P(at least one of k attempts passes), estimated without bias from n attempts with c passes:
        1 - C(n - c, k) / C(n, k)        (and 1.0 when n - c < k)
    This is the metric of code-generation papers: "can it ever do it?"."""
    # TODO 1
    raise NotImplementedError("pass_at_k")


def pass_hat_k(n, c, k):
    """P(all k attempts pass): C(c, k) / C(n, k). tau-bench calls this pass^k: "does it do it every time?".
    For an agent that acts for users, this is the one that matters."""
    # TODO 2
    raise NotImplementedError("pass_hat_k")


def grade(task, run, tools_used):
    """Return {"passed": bool, "outcome_ok": bool, "reasons": [str]}.

    outcome_ok: task["expect"] appears in run.answer (case-insensitive).
    passed: outcome_ok AND no tool from task.get("forbidden", []) in tools_used AND
            run.steps <= task.get("max_steps", 6). Each failed check adds a reason.
    """
    # TODO 3
    raise NotImplementedError("grade")


def summarize(results, k):
    """results: {task_id: [grade, ...] (n trials each)}. Return the average over tasks of
    "pass@1" (c / n), f"pass@{k}", f"pass^{k}" and "outcome_pass@1", each rounded to 3 decimals."""
    # TODO 4
    raise NotImplementedError("summarize")
