---
id: 06
title: Plan, execute, replan
lab: labs/06_planning
minutes: 50
track: patterns
summary: write the plan down, run it step by step with small executors, replan when reality disagrees
---
A ReAct agent plans implicitly: each step it decides the next action from the whole history. That works for short tasks. On long ones it drifts: it forgets a requirement, repeats work, or wanders into a subtask and never comes back. The fix every serious agent uses is to **make the plan explicit**.

## Plan-and-execute

1. A **planner** call writes a numbered plan for the task.
2. An **executor** runs one step at a time. Each step is a small, fresh agent that sees only that step and the results of earlier steps, not the whole messy history.
3. When a step fails, a **replanner** sees what is done and what went wrong, and writes new steps for the rest of the task.

This is the structure of Plan-and-Solve (Wang et al. 2023), LLMCompiler, LangGraph's plan-and-execute template, and of deep-research agents. The plan is also a *user interface*: Cursor and Claude Code show a todo list that the agent updates as it works, which lets you see where it is and stop it early if the plan is wrong.

## Todo lists are the modern form

Frontier coding agents don't usually run a separate planner. Instead the model has a `todo_write` tool and is told to keep its plan in it, marking items `in_progress` and `done`. The list lives in the context (and survives compaction because it's re-written), keeps the model honest about what is left, and gives the user a progress view. You'll use exactly that in the capstone. The separate planner in this lab makes the mechanics visible.

## Replanning is the point

Plans meet reality. The hotel is sold out, the API returns an error, the file isn't where the plan said. A system that can't replan either fails or, worse, pretends the failed step succeeded. Two rules:

- An executor must **report failure plainly** (`FAILED: Casa Azul is sold out`), never improvise a replacement silently.
- The replanner keeps the **completed steps** and only rewrites what remains.

::: trace
title: SFO → Lisbon, 3 nights, under 200 EUR a night
user | Plan a 3-night trip from SFO to Lisbon in March: the cheapest flight, the cheapest available hotel under 200 EUR a night, and the total cost in USD.
plan | 1. Find the cheapest flight from SFO to Lisbon in March · 2. Find hotels in Lisbon under 200 EUR per night · 3. Check availability of the cheapest hotel for 3 nights · 4. Compute the total cost in USD
call | search_flights(origin="SFO", destination="Lisbon", month="March")
tool | TAP 236: 812 USD; United 94: 958 USD; Lufthansa 455: 870 USD
call | search_hotels(city="Lisbon", max_eur_per_night=200)
tool | Casa Azul: 145 EUR/night; Hotel Lusitano: 168 EUR/night; Alfama Rooms: 199 EUR/night
call | check_availability(hotel="Casa Azul", nights=3)
tool | Casa Azul: sold out
note | the step's executor reports "FAILED: Casa Azul is sold out", and the replanner keeps steps 1–2
plan | 3'. Check availability of the next cheapest hotel, Hotel Lusitano, for 3 nights · 4. Compute the total cost in USD
call | check_availability(hotel="Hotel Lusitano", nights=3)
tool | Hotel Lusitano: available for 3 nights
call | convert(amount=504, from_currency="EUR", to_currency="USD")
tool | 544.32 USD
answer | Total: 1356.32 USD (flight 812 USD + 3 nights at Hotel Lusitano, 504 EUR = 544.32 USD)
:::

::: write
In `labs/06_planning/agent.py` (the planner, executor and replanner prompts and calls are written for you):

1. `parse_plan(text)`: numbered (`1.`, `2)`) or bulleted lines into a list of steps; ignore everything else the model wrote.
2. `plan_and_execute(llm, task, tools, max_replans)`: the todo loop. Take the first pending todo, mark it `in_progress`, run `execute_step`. `FAILED…` → mark it failed and replan (or give up when out of replans), keeping the non-pending todos and appending the new steps. Otherwise mark it done and remember `(step, result)`. When nothing is pending, the last result is the answer.
:::

::: run
```bash
python labs/06_planning/run.py --solution
```
It prints the todo list as it changes, then runs one ReAct agent on the same task for comparison.
:::

::: measure
- plan_steps | steps in the first plan | 4 |
- replans | replans needed | 1 |
- total_usd | total trip cost | 1356.32 | USD
- plan_peak | peak prompt, plan-and-execute | 915 | tokens
- react_peak | peak prompt, one ReAct agent | 1014 | tokens
:::

::: explain
**One replan recovered from the sold-out hotel.** The executor reported `FAILED`, the replanner kept steps 1 and 2 and wrote a new step 3 for the next-cheapest hotel, and the total came out right. Without the failure signal, a step executor tends to "succeed" with a made-up booking.

**Plan-and-execute used 13 model calls against ReAct's 7.** Planning isn't free: a planner call, a replanner call, and a small agent per step that has to finish with a summary. Its peak prompt was only modestly smaller (915 versus 1,014 tokens), because here both are dominated by the four tool schemas sent on every call. Planning's context savings grow with task length, since each executor's context stays small while a single ReAct context keeps growing.

**So why plan?** For a 4-step task, honestly, ReAct is fine and cheaper. Planning pays off when tasks are long enough to drift, when steps can run in parallel (LLMCompiler executes independent steps of the plan concurrently), when a human should review the plan before anything happens, and when progress must be visible. That's why frontier agents keep the plan as a todo list inside one agent rather than adding a separate planner process for every task.
:::

::: cards
Q: What are the three roles in plan-and-execute?
A: A planner that writes the steps, an executor that runs each step (often a small fresh agent), and a replanner that rewrites the remaining steps after a failure.
Q: Why does a ReAct agent drift on long tasks?
A: Its plan is implicit in a growing history; requirements and progress get buried, so it forgets, repeats or wanders.
Q: What must an executor do when a step fails?
A: Report the failure explicitly (e.g. "FAILED: sold out") rather than improvising or claiming success, so the replanner can react.
Q: What does a replanner keep, and what does it rewrite?
A: It keeps completed steps and their results and rewrites only the remaining steps.
Q: How do modern coding agents keep a plan without a separate planner?
A: With a todo_write tool: the model maintains a todo list in its own context, marking items in_progress and done, which the UI shows to the user.
Q: When is plan-and-execute not worth it?
A: On short tasks: it costs extra model calls (planner, replanner, per-step summaries) and its context savings only matter as tasks grow long.
:::
