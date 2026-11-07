"""Lab 08: human in the loop. The agent pauses for approval or a question, and resumes later, even
after a crash, from a checkpoint file.

Run:  python labs/08_human_in_the_loop/run.py                 (your code, a scripted human)
      python labs/08_human_in_the_loop/run.py --interactive   (you are the human)
      python labs/08_human_in_the_loop/run.py --solution

The key idea: "waiting for a human" is not a blocking input() call. It is saving the whole run state,
returning, and continuing from that state when the answer arrives (seconds or days later).

State (a JSON-able dict):
    {"messages": [...], "pending": [{"id", "name", "args", "kind": "ask"|"human", "reply"?: str}],
     "always": [tool names the user always allows], "status": "running"|"waiting"|"done"|"max_steps",
     "steps": int, "answer": str | None}
A human reply is "approve", "always" (approve and stop asking for this tool), "deny: reason",
or, for ask_user questions, the answer text.
"""
import json
import os  # noqa: F401
import re  # noqa: F401

from agentlab.llm import ToolCall, tool_message  # noqa: F401


class ApprovalPolicy:
    def __init__(self, always=()):
        self.always = set(always)

    def decide(self, call, tool):
        """Return "allow", "ask", "deny" or "human" for one tool call.

        unknown tool                 -> "deny"
        ask_user                     -> "human"  (a question for the user, not an action)
        tool.risk == "read"          -> "allow"
        tool.risk == "destructive"   -> "ask" only if args["path"] is exactly one job folder, /ckpt/job-<digits>,
                                        otherwise "deny" without bothering the human (never auto-allow)
        tool.risk == "write"         -> "allow" if the user said "always" for this tool, else "ask"
        """
        # TODO 1
        raise NotImplementedError("ApprovalPolicy.decide")


def save(state, path):
    """Write state as JSON *atomically*: to path + ".tmp", then os.replace. A crash mid-write must
    leave the previous checkpoint intact, never half a file."""
    # TODO 2
    raise NotImplementedError("save")


def load(path):
    with open(path) as f:
        return json.load(f)


def new_state(system, task):
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": task}],
            "pending": [], "always": [], "status": "running", "steps": 0, "answer": None}


def respond(state, replies):
    """Attach the human's replies, in order, to the pending entries that don't have one yet."""
    for p, r in zip([p for p in state["pending"] if "reply" not in p], replies):
        p["reply"] = r
    return state


def run_pending(state, box, ckpt):
    """Process pending entries in order. Return False as soon as one has no "reply" (still waiting).

    ask_user          -> the tool result is the reply text
    approve / always  -> run it with box.run(ToolCall(name, args, id)); "always" also adds the name to state["always"]
    deny[: reason]    -> tool result "The user denied this action. Reason: ..."
    After each one: append tool_message(call, result), pop it from pending, save(state, ckpt).
    """
    # TODO 3
    raise NotImplementedError("run_pending")


def advance(llm, box, state, ckpt, max_steps=12):
    """Run until the agent finishes, needs a human, or uses max_steps model calls. Return the state.

    1. run_pending first; if it returns False, status "waiting", return.
    2. Loop while state["steps"] < max_steps: model call, steps += 1, append reply.message().
       No tool calls -> status "done", answer = reply.text, save, return.
       For each call, policy.decide:  allow -> run now and append the result
                                      deny  -> append "Blocked by policy: ..." as its result
                                      ask / human -> add {"id", "name", "args", "kind"} to pending
       save after each call. Anything pending -> status "waiting", save, return.
    3. Out of steps -> status "max_steps".
    Use ApprovalPolicy(state["always"]).
    """
    # TODO 4
    raise NotImplementedError("advance")
