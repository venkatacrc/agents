---
id: 05
title: Workflows before agents
lab: labs/05_workflows
minutes: 40
track: patterns
summary: routing, parallel fan-out and evaluator-optimizer; when your code should decide the steps instead of the model
---
Anthropic's "Building effective agents" (2024) draws a line that is worth keeping in your head for the rest of the course:

- **Workflows**: LLM calls orchestrated by *your code* along predefined paths.
- **Agents**: the *model* directs its own process and tool use, deciding the steps as it goes.

Agents are more flexible, and they cost that flexibility in tokens, latency and predictability. Every step is a decision the model can get wrong. When you know the steps in advance, a workflow is cheaper, faster, easier to test, and usually more accurate. Start with the simplest thing that works: a single well-prompted call, then a workflow, and only then an agent.

## The patterns

- **Prompt chaining**: a fixed sequence (outline → draft → translate), with code checks between steps.
- **Routing**: classify the input, then send it to a specialized prompt (or a cheaper model for easy cases). Each specialist prompt can be optimized without hurting the others.
- **Parallelization**: *sectioning* (independent subtasks at once) or *voting* (the same task several times, then aggregate). Independent LLM calls are I/O-bound, so a thread pool gives near-linear speedups.
- **Orchestrator-workers**: a model breaks the task into subtasks dynamically and delegates them (lesson 09).
- **Evaluator-optimizer**: one call writes, another grades against explicit criteria, and the writer revises with the feedback until it passes.

Most production "AI features" are workflows. Many products sold as agents are mostly workflows with an agentic step in the middle. That's a good design, not a compromise.

::: trace
title: evaluator-optimizer on release notes
user | Write a release note for upgrading the serving fleet from vLLM 0.9 to 0.10. Readers are on-call engineers.
note | rubric: both version numbers, the breaking change, the rollback command
answer | We upgraded the serving fleet to a new vLLM release.
note | reviewer → FAIL: missing both version numbers; the breaking change; the rollback command
answer | … vLLM goes from 0.9 to 0.10.
note | reviewer → FAIL: missing the breaking change (prefix caching on by default); the rollback command
answer | … Breaking: --enable-prefix-caching is now on by default.
note | reviewer → FAIL: missing the rollback command (kubectl rollout undo deploy/vllm)
answer | … Roll back with: kubectl rollout undo deploy/vllm.
note | reviewer → PASS after 4 rounds
:::

::: write
In `labs/05_workflows/agent.py` (`ask(llm, system, user)` is given):

1. `route(llm, ticket, routes)`: classify with "Reply with exactly one of: …", find the label in the lower-cased reply (no label → `("other", escalation)`), then answer with that route's system prompt.
2. `fan_out(llm, system, items, workers)`: `ThreadPoolExecutor(max_workers=workers)` and `pool.map`, results in input order.
3. `evaluate_optimize(llm, task, rubric, max_rounds)`: draft, review with the rubric ("Reply PASS, or FAIL: followed by what is missing"), rewrite with the feedback, until PASS or out of rounds. Return the draft, the rounds used and the history.
:::

::: run
```bash
python labs/05_workflows/run.py
python labs/05_workflows/run.py --solution
```
The mock model takes 0.25 s per call, so the parallel speedup is real wall-clock time.
:::

::: measure
- routed_ok | tickets routed correctly | 8 | of 8
- seq_s | 8 summaries, sequential | 2.03 | s
- par_s | 8 summaries, 8 workers | 0.26 | s
- rounds | review rounds until PASS | 4 |
:::

::: explain
**Routing is one cheap call that makes every later call better.** The classifier only has to emit a label; the specialist prompts can each be short and focused. In production the router is often a small, fast model, and the "outage" route might page a human instead of answering.

**7.9x faster with 8 workers, same results, same order.** LLM calls spend their time waiting on the network or the GPU, so threads parallelize them well (the GIL is released during I/O). Servers batch concurrent requests (continuous batching in vLLM and SGLang), so for a self-hosted model, parallel requests also raise throughput per GPU. Watch your provider's rate limits.

**The rubric did the work in evaluator-optimizer.** Each FAIL named exactly what was missing, so each rewrite fixed something. A reviewer that says "could be better" gives the writer nothing to act on, the same lesson as error messages in lesson 03. The loop needs a `max_rounds` because reviewers can be unsatisfiable.

**Count the calls.** Routing used 2 calls per ticket and fan-out 1 per document. An agent doing the same work would spend extra calls just deciding what to do next, and might decide differently each time.
:::

::: cards
Q: What is the difference between a workflow and an agent (Anthropic's definition)?
A: In a workflow your code fixes the sequence of LLM calls; in an agent the model decides its own steps and tool use dynamically.
Q: When should you prefer a workflow over an agent?
A: When the steps are known in advance: workflows are cheaper, faster, more predictable and easier to test.
Q: What is routing?
A: Classifying an input with one LLM call and dispatching it to a specialized prompt, tool chain or model for that category.
Q: Why do threads speed up parallel LLM calls in Python despite the GIL?
A: The calls are I/O-bound (waiting on the network or GPU), and the GIL is released while waiting.
Q: What are the two kinds of parallelization in "Building effective agents"?
A: Sectioning (independent subtasks run at once) and voting (the same task run several times and aggregated).
Q: What makes an evaluator-optimizer loop converge?
A: A reviewer with explicit criteria that says specifically what is missing, plus a cap on rounds.
:::
