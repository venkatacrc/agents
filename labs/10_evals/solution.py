"""Lab 10 reference: grading agent runs and estimating pass@k and pass^k."""
from math import comb


def pass_at_k(n, c, k):
    """P(at least one of k samples passes), unbiased from n samples with c passes (Chen et al., 2021)."""
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n, c, k):
    """P(all k samples pass), from n samples with c passes (tau-bench's pass^k)."""
    return comb(c, k) / comb(n, k)


def grade(task, run, tools_used):
    reasons = []
    outcome_ok = task["expect"].lower() in run.answer.lower()
    if not outcome_ok:
        reasons.append(f"answer lacks {task['expect']!r}")
    bad = sorted(set(tools_used) & set(task.get("forbidden", [])))
    if bad:
        reasons.append(f"used forbidden tool(s) {bad}")
    if run.steps > task.get("max_steps", 6):
        reasons.append(f"took {run.steps} steps")
    return {"passed": not reasons, "outcome_ok": outcome_ok, "reasons": reasons}


def summarize(results, k):
    """results: {task_id: [grade, ...]} -> averages over tasks."""
    n_tasks = len(results)
    out = {"pass@1": 0.0, f"pass@{k}": 0.0, f"pass^{k}": 0.0, "outcome_pass@1": 0.0}
    for grades in results.values():
        n = len(grades)
        c = sum(g["passed"] for g in grades)
        out["pass@1"] += c / n
        out[f"pass@{k}"] += pass_at_k(n, c, k)
        out[f"pass^{k}"] += pass_hat_k(n, c, k)
        out["outcome_pass@1"] += sum(g["outcome_ok"] for g in grades) / n
    return {key: round(v / n_tasks, 3) for key, v in out.items()}
