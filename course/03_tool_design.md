---
id: 03
title: Designing tools for models
lab: labs/03_tool_design
minutes: 40
track: foundations
summary: the agent-computer interface; names and descriptions pick the tool, errors that teach, arguments that can't be wrong
---
Anthropic's engineers reported that while building their SWE-bench agent they spent more time on the tools than on the prompt. The SWE-agent paper (Yang et al., 2024) gave it a name: the **agent-computer interface (ACI)**. Tools are a user interface whose user is a model, and that user reads everything literally, has no other documentation, and can't ask you what you meant.

## Names and descriptions choose the tool

The model chooses a tool by reading its name and description against the task. Compare:

| vague | descriptive |
|---|---|
| `query(q)`: "Run a query." | `get_job_status(job_id)`: "Status, GPU count, current step and last log line of one training job. Use for 'is job-X running', 'what step'." |
| `do(action, target)` | `scale_deployment(name, replicas)`: "Set the number of replicas of a serving deployment." |
| `info(x)` | `get_service_metrics(service, window_minutes)`: "p50/p99 latency, error rate and QPS of a service." |

Good descriptions say **what the tool returns**, **when to use it** (and when not to), and **the format of inputs** (`job ids look like job-123`). Write them like documentation for a smart new colleague. Then test them: watch which tool a real model picks for twenty realistic requests.

## Errors that teach

A tool's error message is the only feedback the model gets. Compare what the model sees after asking for `job-12`, which doesn't exist:

- `KeyError: 'job-12'`
- `Error: no job 'job-12'. Did you mean: job-123, job-121? Valid job ids: job-7, job-88, job-121, job-123.`

With the first, the model apologizes or guesses. With the second, it retries `job-123`, and if that isn't what the user meant, it can say so. "Did you mean" with `difflib.get_close_matches` is ten lines of code and fixes a whole class of failures.

## Poka-yoke: make mistakes impossible

*Poka-yoke* is the manufacturing term for designing a part so it can't be assembled wrong. For tools:

- **Coerce** obviously-intended types: `"3"` → `3` for an integer, `"true"` → `True`. Models send numbers as strings surprisingly often.
- **Prefer enums** to free strings, and **absolute paths** to relative ones (Anthropic's SWE-bench agent made path mistakes after moving out of the root directory until its tools required absolute paths).
- **Return less, but what matters**: a search that returns 200 lines buries the answer; return the top 10 with a count of the rest.
- **Merge tools that are always called together**, and split tools that do two unrelated things. Fewer, sharper tools beat many overlapping ones.

::: trace
title: a typo, with a helpful error
user | What is the status of job-12?
call | get_job_status(job_id="job-12")
tool | Error: no job 'job-12'. Did you mean: job-123, job-121, job-7? Valid job ids: job-7, job-88, job-121, job-123.
call | get_job_status(job_id="job-123")
tool | job-123: running, 32 GPUs, step 9100, last log: loss 1.87
answer | There is no job-12; the closest is job-123, which is running on 32 GPUs at step 9100.
:::

::: write
In `labs/03_tool_design/agent.py`:

1. `helpful_error(exc, tool)`: `NotFound` → "Error: no job 'job-12'. Did you mean: …? Valid job ids: …" (keep that wording; the mock model reads it). `TypeError` (wrong or missing arguments) → the error plus each parameter's type. Anything else → `"Error: <Type>: <message>"`.
2. `coerce_args(args, schema)`: convert string values to the schema's integer, number or boolean type; leave anything that doesn't convert unchanged.
3. `call_tool(tool, args)`: coerce, run, and turn exceptions into `helpful_error`. Never raises.

Part A of `run.py` needs no code: it shows how a weak model, one that only matches words, picks tools under vague versus descriptive definitions.
:::

::: run
```bash
python labs/03_tool_design/run.py
python labs/03_tool_design/run.py --solution
```
:::

::: measure
- vague_ok | right tool, vague names | 3 | of 12
- good_ok | right tool, descriptive tools | 12 | of 12
- recovered_bare | typo'd ids recovered, bare exceptions | 0 | of 4
- recovered_helpful | typo'd ids recovered, helpful errors | 4 | of 4
- first_try_coerced | string numbers that worked first try with coercion | 3 | of 3
:::

::: explain
**Tool choice went from 3/12 to 12/12 without changing the model.** The lab's "model" just matches words between the task and each tool's name and description, and a real model's attention does a far better version of the same thing. With five tools called `query`, `do`, `info`… it has nothing to match, so it defaults to one. Descriptive names and "use this for…" sentences give it the words to match. Real models are better at guessing than this one, but the direction of the effect is the same, and it grows with the number of tools.

**Recovery went from 0/4 to 4/4 with the same tools.** Only the error text changed. This is the cheapest reliability improvement in agent engineering. Audit every error your tools can return and ask: could a model fix its call from this message alone?

**Coercion turned 0/3 into 3/3 first-try successes.** Without it each `"3"` costs a failed call, an error, and a retry: an extra model round trip and more context. Being liberal in what you accept is a good idea *only* when the intent is unambiguous; never coerce `"delete everything"` into anything.
:::

::: cards
Q: What is the agent-computer interface (ACI)?
A: The tools, their descriptions, inputs, outputs and errors, treated as a user interface designed for a model, from the SWE-agent paper.
Q: What should a good tool description contain?
A: What the tool does and returns, when to use it (and when not to), and the expected input formats, with an example if useful.
Q: Why is "Did you mean: …" in an error message so effective?
A: It gives the model the exact valid values to retry with, turning a dead end into a one-step recovery.
Q: What is poka-yoke in tool design?
A: Designing tools so mistakes are impossible or harmless: enums, coercion of unambiguous types, absolute paths, bounded outputs, safe defaults.
Q: When is it right to coerce a model's argument?
A: Only when the intent is unambiguous, like "3" for an integer or "true" for a boolean. Never for anything that changes meaning.
Q: Many overlapping tools or a few sharp ones?
A: A few sharp ones: overlapping tools confuse selection and every definition costs prompt tokens on every call.
:::
