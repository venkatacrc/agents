---
id: 15
title: The frontier, mapped to what you built
lab:
minutes: 35
track: systems
summary: how Claude Code, Cursor, Codex, Deep Research and computer-use agents are put together, and the frameworks around them
---
Every frontier agent product is built from the pieces in this course. What distinguishes them is how carefully each piece is engineered, and how the model was trained for that harness. Here is the map.

## Coding agents: Claude Code, Cursor, Codex, Devin, SWE-agent

| piece | lesson | what they do |
|---|---|---|
| loop | 02 | one main ReAct loop; the model decides when it's done |
| tools | 03, 14 | read/grep/glob, exact-match edit, shell, web fetch, todo list; few, sharp, well-described |
| context | 04 | agentic search instead of pre-loading the repo; output truncation; auto-compaction near the limit; project rule files (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules`) loaded at start |
| planning | 06 | a todo list in the context; plan mode that writes a plan for you to approve before edits |
| verifier | 07 | run tests, linters and type checkers, read the errors, fix |
| humans | 08 | permission modes and allowlists for shell commands; approval before risky actions; you can interrupt and redirect at any step |
| subagents | 09 | read-only exploration and parallel tasks in isolated contexts; parallel attempts in separate git worktrees |
| safety | 11 | sandboxed execution (containers, OS sandboxes), network restrictions, workspace-only writes |
| extensibility | 12 | MCP servers, hooks around tool calls, skills (instructions plus scripts loaded on demand) |
| serving | 13 | stable prefixes for cache hits; models post-trained with RL in exactly this kind of harness |

Cloud and background agents (Codex cloud, Cursor background agents, Devin, Jules) run the same loop in a remote sandbox with a clone of your repo and hand back a pull request. That's lesson 08's resumable state taken to its conclusion: the run is fully detached from your laptop.

## Research agents: Deep Research and friends

Orchestrator-workers (lesson 09): a lead plans the research, spawns parallel searchers with fresh contexts, and a writer synthesizes with citations. It runs for many minutes and reads hundreds of sources, so context isolation and compaction aren't optional. The models are RL-trained on browsing tasks with verifiable answers (benchmarks like BrowseComp measure this).

## Computer-use and browser agents

The same loop, with screenshots as observations and mouse/keyboard actions as tools (OpenAI's computer-using agent, Anthropic's computer use, Gemini's computer use model). Everything gets harder: observations are large images (context), actions are imprecise (tool design), and the web is full of injected instructions (lesson 11). That is why these products confirm with you before purchases, logins and sends.

## Frameworks

You built the core of each of these yourself, so you can read their docs as "where is the loop, where is the state, where are the approvals?":

- **OpenAI Agents SDK**: agents, tools, handoffs between agents, guardrails, tracing; runs against any OpenAI-compatible model.
- **Claude Agent SDK**: the Claude Code harness as a library: its tools, context management, subagents, hooks and permissions.
- **LangGraph**: agents as explicit state graphs with checkpointers and `interrupt()` for humans in the loop (lesson 08's state machine, generalized).
- **Google ADK**: agents, workflow agents (sequential, parallel, loop), multi-agent hierarchies; A2A, a protocol for agents calling other agents.
- **smolagents** (Hugging Face): small and readable; "code agents" whose actions are Python snippets rather than JSON tool calls.
- **Pydantic AI**, **CrewAI**, **AutoGen / Microsoft Agent Framework**, **Mastra** (TypeScript): typed tools and outputs, role-based crews, multi-agent conversations.
- **DSPy**: programs of LLM calls whose prompts are *optimized* against a metric rather than hand-written (lesson 10's evals as the training signal).

A rule of thumb: use a framework when you need what it adds (durable state, tracing, a team's shared conventions), and keep the loop simple enough that you could rewrite it in an afternoon. Anthropic's advice from "Building effective agents" still holds: many successful production agents are a few hundred lines of plain code.

## What to read next

- Anthropic, "Building effective agents" (2024); "How we built our multi-agent research system" (2025); "Effective context engineering for AI agents" (2025); "Writing effective tools for agents" (2025).
- Yao et al., ReAct (2022); Shinn et al., Reflexion (2023); Yang et al., SWE-agent (2024); Yao et al., tau-bench (2024).
- Simon Willison on prompt injection and the lethal trifecta; Meta, "Agents Rule of Two" (2025); Debenedetti et al., CaMeL (2025).
- DeepSeekMath (GRPO, 2024) and DeepSeek-R1 (2025) for RL with verifiable rewards.
- The MCP specification at modelcontextprotocol.io.

## Your next projects

1. Run lab 14 against a real model: serve `Qwen2.5-Coder-7B-Instruct` (or bigger) with vLLM or SGLang and `--model vllm:…`, add three new bugs to the toy repo, and measure pass^k over 10 trials.
2. Put lesson 04's compaction and lesson 08's checkpoints into the coding agent, and make it survive a `kill -9` mid-session without repeating an edit.
3. Turn your cluster tools from lesson 12 into a real MCP server for something you use daily, and use it from Cursor.
4. Use lesson 13's pieces to generate SFT data from your agent's successful runs, fine-tune a small model on it, and compare its pass@1 before and after.

::: cards
Q: Name four tools nearly every coding agent has.
A: File read with line numbers, search (grep/glob), exact-match edit, and a shell or test runner; usually also a todo list and web fetch.
Q: What is "plan mode" in coding agents?
A: The agent investigates and writes a plan for you to review and approve before it makes any edits.
Q: How do cloud/background coding agents differ from local ones?
A: The same loop runs in a remote sandbox with a clone of the repo, detached from your machine, and returns its work as a branch or pull request.
Q: What makes computer-use agents harder than tool-calling agents?
A: Observations are large screenshots, actions (clicks, typing) are imprecise, and web content is full of untrusted instructions.
Q: Which framework models agents as explicit state graphs with interrupts for humans?
A: LangGraph, with checkpointers and interrupt().
Q: What is a smolagents "code agent"?
A: An agent whose actions are Python code snippets executed in a sandbox, instead of JSON tool calls.
Q: What does DSPy optimize?
A: The prompts (instructions and few-shot examples) of a multi-step LLM program, against a metric on a dataset.
:::
