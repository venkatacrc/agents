"""Lab 06: planning. Decide the steps first, run them one at a time, replan when one fails.

Run:  python labs/06_planning/run.py             (your code)
      python labs/06_planning/run.py --solution

The planner, the executor (a small agent per step) and the replanner are written for you below.
You write the parts that make it a system: parsing the plan, the todo list, and the replan loop.
"""
import re  # noqa: F401

from agentlab.loop import run_agent

PLANNER = ("You are a planner. Break the task into a short numbered list of concrete steps, one tool-sized "
           "action each. Reply with the list only.")
EXECUTOR = ("You execute one step of a plan with the tools. Reply with the step's result in one line. "
            "If the step cannot be done, reply starting with FAILED: and say why.")
REPLANNER = ("You revise plans. Given the task, the finished steps and a failure, reply with a numbered list of "
             "the remaining steps only.")


def make_plan(llm, task):
    return llm.chat([{"role": "system", "content": PLANNER}, {"role": "user", "content": task}]).text


def execute_step(llm, step, done, tools):
    """Run one step with a fresh, small agent. `done` is [(step, result)] so far: its only memory."""
    context = "\n".join(f"- {s}: {r}" for s, r in done) or "(none yet)"
    run = run_agent(llm, tools, f"Step: {step}\n\nResults so far:\n{context}", system=EXECUTOR, max_steps=6)
    return run.answer.strip()


def replan(llm, task, done, failure):
    finished = "\n".join(f"- {s}: {r}" for s, r in done)
    user = f"Task: {task}\n\nFinished steps:\n{finished}\n\nFailure: {failure}"
    return llm.chat([{"role": "system", "content": REPLANNER}, {"role": "user", "content": user}]).text


def parse_plan(text):
    """Numbered ("1. x", "2) y") or bulleted ("- z") lines -> ["x", "y", "z"]. Ignore other lines."""
    # TODO 1
    raise NotImplementedError("parse_plan")


def show(todos):
    marks = {"pending": "[ ]", "in_progress": "[>]", "done": "[x]", "failed": "[!]"}
    for t in todos:
        print(f"    {marks[t['status']]} {t['step']}")


def plan_and_execute(llm, task, tools, max_replans=2, verbose=False):
    """Return (final answer, todos, replans used).

    todos = [{"step": str, "status": "pending" | "in_progress" | "done" | "failed"}], from parse_plan(make_plan(...)).
    Loop: take the first pending todo, mark it in_progress (show(todos) if verbose), run execute_step.
      result starts with "FAILED" -> mark failed; if replans are used up return ("gave up: ...", todos, replans);
                                     otherwise keep the non-pending todos and append the replanned steps as pending.
      otherwise -> mark done and append (step, result) to `done`.
    When nothing is pending, the last result is the answer.
    """
    # TODO 2
    raise NotImplementedError("plan_and_execute")
