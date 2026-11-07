---
id: 08
title: Humans in the loop
lab: labs/08_human_in_the_loop
minutes: 60
track: control
summary: approval policies, asking the user, pausing and resuming from a checkpoint, and surviving a crash without acting twice
---
An agent that can only run start-to-finish on its own is either toothless (it only reads) or dangerous (it acts without anyone checking). Real agents pause: to **ask a question** when the task is ambiguous, and to **get approval** before an action with consequences. Cursor and Claude Code ask before running shell commands outside an allowlist; ChatGPT's agent asks before purchases and sends; Codex has approval modes from "suggest" to "full auto".

## An approval policy is code, not a prompt

"Ask before deleting anything" in a system prompt is a request the model may not honor. The policy belongs in the harness, which sees every call before it runs:

| call | decision |
|---|---|
| a read-only tool (`list_jobs`) | **allow**: run it |
| a write (`cancel_job`) | **ask** the human, unless they said "always" for this tool |
| a destructive call (`delete_checkpoints`) on exactly one job folder `/ckpt/job-7` | **ask** |
| a destructive call on anything else (`/ckpt`, `/ckpt/job-7/../..`) | **deny** without bothering the human |
| `ask_user(question)` | it's a question for the **human**, not an action |
| an unknown tool | **deny** |

Note the asymmetry: a policy can *deny* on its own, but it never *auto-approves* something destructive. And "deny without asking" matters for usability. Approval prompts that are almost always "yes" train people to click yes without reading, which is how dangerous actions get through. Ask rarely, and only about things worth reading.

## Pausing is a state machine

A human may answer in a second or tomorrow. The agent can't block a thread waiting, so the run becomes **state** that is saved and resumed:

```text
running ──(model asks for approval / a question)──▶ waiting ──(human replies)──▶ running ──▶ … ──▶ done
```

The state is just data: the messages, the pending calls that need a reply, which tools the user said "always" for, the step count. `advance(state)` runs until the agent finishes or needs a human, saves the state and returns. `respond(state, replies)` attaches answers, and the next `advance` runs the approved calls first. LangGraph's `interrupt()` and checkpointers, the OpenAI Agents SDK's approval flow, and Temporal-style durable workflows all implement this same machine.

## Checkpoints and crashes

Saving state is easy to get subtly wrong:

- **Write atomically.** Write to `state.json.tmp`, then `os.replace` it over `state.json`. A crash mid-write then leaves the old checkpoint intact instead of half a file.
- **Save after every side effect.** If the process dies after cancelling job-7 but before recording it, the resumed agent will cancel it again. Here that's harmless; for "send the payment", it isn't. Record each result as soon as the action completes, and make actions **idempotent** where you can (pass an idempotency key, check before acting).

::: trace
title: free up GPUs, with you approving (try Approve and Deny)
user | Free up GPUs: cancel the idle training jobs and delete their checkpoints.
call | list_jobs()
note | read-only: allowed by policy without asking
tool | job-7: owner alice, idle 30 h · job-88: owner carol, running · job-121: owner bob, idle 50 h · job-130: owner prod-team, idle 26 h, tag production
ask | job-130 is tagged production but idle. Cancel it too?
human | Leave job-130 alone, it's production.
approve | cancel_job(job_id="job-7")  ·  cancel_job(job_id="job-121")
[approve] tool | job-7 cancelled, 8 GPUs released · job-121 cancelled, 8 GPUs released
[approve] call | delete_checkpoints(path="/ckpt/job-7")  ·  delete_checkpoints(path="/ckpt/job-121")  ·  delete_checkpoints(path="/ckpt")
[approve] note | /ckpt is not a single job folder: denied by policy at once, the human is never asked about it
[approve] tool | Blocked by policy: delete_checkpoints is not allowed with {"path": "/ckpt"}.
[approve] approve | delete_checkpoints(path="/ckpt/job-7")  ·  delete_checkpoints(path="/ckpt/job-121")
[approve] human | approve · deny: keep bob's checkpoints, he may resume job-121
[approve] tool | deleted /ckpt/job-7 (1.2 TB freed) · The user denied this action. Reason: keep bob's checkpoints, he may resume job-121
[approve] answer | Cancelled job-7, job-121. Deleted checkpoints /ckpt/job-7. Not deleted (you denied): /ckpt/job-121. Not deleted (blocked by policy): /ckpt. Left job-130 running as you asked.
[deny] tool | The user denied this action. · The user denied this action.
[deny] answer | Cancelled nothing: you denied both cancellations, so their checkpoints stay too. Left job-130 running as you asked.
:::

::: write
In `labs/08_human_in_the_loop/agent.py`:

1. `ApprovalPolicy.decide(call, tool)`: the table above.
2. `save(state, path)`: atomic, via a `.tmp` file and `os.replace`. `load(path)`.
3. `respond(state, replies)`: attach the human's replies, in order, to pending entries that have none.
4. `run_pending(box, state, ckpt)`: process replied entries in order: answers become tool results, `approve`/`always` run the call (`always` also remembers the tool), `deny: reason` becomes "The user denied this action. Reason: …". Save after each one. Return False at the first entry still waiting.
5. `advance(llm, box, state, ckpt, max_steps)`: run pending entries first, then loop: model call; no tool calls → done; for each call, allow (run now), deny (a "Blocked by policy" result) or queue for the human; anything queued → status `waiting`, save, return.
:::

::: run
```bash
python labs/08_human_in_the_loop/run.py --solution                 # a scripted human
python labs/08_human_in_the_loop/run.py --solution --interactive   # you are the human
```
The second scenario kills the process right after you approve the cancellations, then restarts from the checkpoint.
:::

::: measure
- interrupts | pauses for the human | 3 |
- auto_allowed | calls allowed without asking | 1 |
- policy_blocked | calls denied by policy without asking | 1 |
- jobs_cancelled | jobs cancelled | 2 |
- repeated_after_crash | actions repeated after the crash | 0 |
:::

::: explain
**Three pauses, each worth reading.** One question (the production job, which the model noticed and asked about) and two batches of approvals. The read was allowed silently, and `rm -r /ckpt` was refused without asking: the human was never shown a prompt whose right answer is always "no".

**The model asked a question instead of guessing.** Tagged production but idle is ambiguous, and "cancel the idle jobs" could include it. A good agent surfaces that ambiguity, and the harness makes `ask_user` a first-class tool so the question becomes a pause, not a guess written into the final answer.

**Zero actions repeated after the crash.** The process died while executing approved cancellations. Because `run_pending` saved the checkpoint after *each* call, the restarted agent saw job-7's cancellation already recorded and only ran what was left. Move the `save` to after the loop, run again, and watch a cancellation happen twice.

**Approvals need context to be meaningful.** "Approve `delete_checkpoints({'path': '/ckpt/job-121'})`?" is clear here. In real systems show the diff, the command, the recipient and the amount, and say why the agent wants it.
:::

::: cards
Q: Where should an agent's approval policy be enforced, and why?
A: In the harness, before each tool call runs; a rule in the prompt is a request the model may ignore, while code always runs.
Q: Name the four possible decisions for a tool call in this lab's policy.
A: allow (run now), ask (human approval), deny (block without asking), human (a question for the user via ask_user).
Q: Why should a policy deny some calls without asking the human?
A: Prompts whose answer is always "no" waste attention and train people to approve without reading; reserve prompts for real decisions.
Q: Why must a human-in-the-loop agent be a resumable state machine?
A: Humans reply after seconds or days; the run must be saved as data (messages, pending calls, settings) and resumed later, possibly in another process.
Q: How do you write a checkpoint safely?
A: Write to a temporary file and atomically rename it over the old one (os.replace), so a crash never leaves a partial checkpoint.
Q: How do you avoid repeating side effects after a crash?
A: Record each action's result in the checkpoint immediately after it completes, and make actions idempotent where possible.
Q: What should an approval prompt show?
A: Exactly what will happen (command, diff, recipient, amount) and why the agent wants to do it.
:::
