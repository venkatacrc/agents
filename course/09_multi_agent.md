---
id: 09
title: Multi-agent systems
lab: labs/09_multi_agent
minutes: 45
track: patterns
summary: orchestrator and workers like Deep Research; context isolation, parallel subagents, and what it really costs
---
A **multi-agent** system is several agent loops whose inputs and outputs are wired together by code or by another agent. The pattern that has proven itself in production is **orchestrator-workers**: a lead agent breaks the task into independent pieces, hands each to a **subagent** with a fresh context, and combines their results.

Anthropic's Research feature, OpenAI's and Google's Deep Research, and Claude Code's `Task` tool (and Cursor's subagents) all work this way. Each subagent starts with an empty history and one question, does its own searching and reading, and returns a short answer. The lead never sees the raw pages.

## Why it helps

- **Context isolation.** A researcher that reads ten documents on speculative decoding doesn't carry them into the next question. Each context stays small and on-topic, which helps quality (lesson 04's context rot) and cost.
- **Parallelism.** Independent subagents run at the same time. Anthropic reported research queries taking minutes instead of hours with parallel subagents and parallel tool calls.
- **Specialization.** Each role gets its own short prompt and tools: a researcher with search, a writer with none.

## What it costs, honestly

Anthropic's engineering post on their research system reported that agents use about 4x the tokens of chat, and multi-agent systems about 15x. More tokens bought better answers on broad research questions, where breadth matters and the work splits cleanly. Total tokens can also go *down* (as in this lab) when one agent would otherwise drag every document through every later step. Which one you get depends on the shape of the task, so measure it.

Multi-agent setups are a poor fit when the subtasks depend on each other or need shared context. Coding is the usual example: two agents editing the same code in parallel make conflicting decisions. Cognition's "Don't build multi-agents" (2025) makes that case: every subagent acts on a partial view of the decisions made so far. The common resolution is single-threaded agents for tightly coupled work, and subagents only for read-only, independent exploration ("search the codebase for X and report back").

::: trace
title: lead + 3 researchers
user | Compare speculative decoding, prefix caching and FP8 quantization for an LLM serving team: for each, the speed-up or saving and the main caveat, with sources.
plan | lead → 3 questions: What speed-up or saving does speculative decoding give, and what is its main caveat? · … prefix caching … · … FP8 quantization …
note | 3 researchers start in parallel, each with an empty history and one question
call | researcher 1: search(query="speculative decoding") · read(doc="speculative-decoding-overview") · read(doc="speculative-decoding-in-production")
tool | researcher 1 → 2-3x lower latency per token at batch size 1 … shrinks toward 1x at large batch sizes (sources: …)
call | researcher 2 and 3 do the same for prefix caching and FP8
tool 294 | the lead's context holds only 3 short findings
answer | Brief: speculative decoding 2-3x lower latency at batch 1 … · prefix caching up to 5x faster TTFT … · FP8 about 1.6x throughput … (with sources)
:::

::: write
In `labs/09_multi_agent/agent.py` (prompts given):

1. `subagent(llm, question, tools)`: a fresh `run_agent` with the RESEARCHER system prompt and only the question; return its answer.
2. `orchestrate(llm, task, tools, workers)`: ask the LEAD for questions (one per line, strip bullets and numbers), run `subagent` for each in a `ThreadPoolExecutor`, then one WRITER call with every question and finding. Return `(brief, questions, findings)`.
:::

::: run
```bash
python labs/09_multi_agent/run.py --solution
```
The same task is also run by one agent with the same tools, for comparison.
:::

::: measure
- single_peak | peak context, one agent | 1999 | tokens
- lead_peak | peak context, lead | 294 | tokens
- sub_peak | peak context, any researcher | 839 | tokens
- single_total | total prompt tokens, one agent | 9201 | tokens
- multi_total | total prompt tokens, lead + researchers | 6192 | tokens
:::

::: explain
**The lead never held more than 294 tokens.** It saw the task, its questions and three short findings. The single agent's context reached 1,999 tokens because every document it read stayed in its history. Each researcher peaked at 839, its own question's documents only.

**Fewer total tokens here, and that's not a law.** Total prompt tokens went *down* (6,192 versus 9,201), because the single agent re-sent all six documents on every later step while each researcher only re-sent its own two. The multi-agent setup made more model calls (14 versus 10), and each subagent pays for its own system prompt and tools. With longer documents and more cross-topic steps, isolation wins by more; with many subagents that each re-read the same material, or a lead that pulls their full transcripts back, it loses. Anthropic's 15x number comes from subagents doing much *more* work (more searches, more sources), which was the goal. Measure tokens per useful answer on your own tasks.

**Wall time fell from 1.5 s to 0.9 s** because the three researchers ran in parallel. The latency win from parallel subagents is real and grows with the number of independent subtasks.

**Read the brief for errors a lead can't see.** The writer only knows what researchers reported. If one misread a source, nothing downstream can catch it. Production systems add a citation check: a subagent that verifies each claim against its source.
:::

::: cards
Q: What is the orchestrator-workers pattern?
A: A lead agent decomposes a task into subtasks, delegates each to a worker (subagent) with a fresh context, and synthesizes their results.
Q: What is context isolation, and why does it help?
A: Each subagent starts with an empty history and only its subtask, so its context stays small and on-topic, and the lead sees only condensed findings.
Q: When are multi-agent systems a poor fit?
A: When subtasks are tightly coupled or need shared decisions, like parallel edits to the same code; agents acting on partial context make conflicting choices.
Q: Roughly how many tokens did Anthropic report multi-agent research uses compared with chat?
A: About 15x (single agents about 4x); the extra tokens bought better results on broad research tasks.
Q: Why can multi-agent use fewer total tokens than one agent?
A: A single agent re-sends every document it has read on every later step; isolated subagents each re-send only their own.
Q: How do frontier coding agents usually use subagents?
A: For read-only, independent exploration (search the codebase, research a question) that returns a short report, while one main agent makes the edits.
:::
