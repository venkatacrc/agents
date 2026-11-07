"""Lab 06 reference: plan-and-execute with a todo list and replanning on failure."""
import re

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
    context = "\n".join(f"- {s}: {r}" for s, r in done) or "(none yet)"
    run = run_agent(llm, tools, f"Step: {step}\n\nResults so far:\n{context}", system=EXECUTOR, max_steps=6)
    return run.answer.strip()


def replan(llm, task, done, failure):
    finished = "\n".join(f"- {s}: {r}" for s, r in done)
    user = f"Task: {task}\n\nFinished steps:\n{finished}\n\nFailure: {failure}"
    return llm.chat([{"role": "system", "content": REPLANNER}, {"role": "user", "content": user}]).text


def parse_plan(text):
    steps = []
    for line in text.splitlines():
        found = re.match(r"^\s*(?:\d+[.)]|[-*])\s+(.*\S)", line)
        if found:
            steps.append(found.group(1))
    return steps


def show(todos):
    marks = {"pending": "[ ]", "in_progress": "[>]", "done": "[x]", "failed": "[!]"}
    for t in todos:
        print(f"    {marks[t['status']]} {t['step']}")


def plan_and_execute(llm, task, tools, max_replans=2, verbose=False):
    todos = [{"step": s, "status": "pending"} for s in parse_plan(make_plan(llm, task))]
    done, replans = [], 0
    while True:
        todo = next((t for t in todos if t["status"] == "pending"), None)
        if todo is None:
            break
        todo["status"] = "in_progress"
        if verbose:
            show(todos)
        result = execute_step(llm, todo["step"], done, tools)
        if result.startswith("FAILED"):
            todo["status"] = "failed"
            if replans == max_replans:
                return f"gave up: {result}", todos, replans
            replans += 1
            pending = [t for t in todos if t["status"] != "pending"]
            todos = pending + [{"step": s, "status": "pending"} for s in parse_plan(replan(llm, task, done, result))]
            continue
        todo["status"] = "done"
        done.append((todo["step"], result))
    if verbose:
        show(todos)
    return done[-1][1], todos, replans
