"""Lab 08 reference: approvals, clarifying questions, pause/resume through a checkpoint file."""
import json
import os
import re

from agentlab.llm import ToolCall, tool_message


class ApprovalPolicy:
    def __init__(self, always=()):
        self.always = set(always)

    def decide(self, call, tool):
        if tool is None:
            return "deny"
        if call.name == "ask_user":
            return "human"
        if tool.risk == "read":
            return "allow"
        if tool.risk == "destructive":
            return "ask" if re.fullmatch(r"/ckpt/job-\d+/?", str(call.args.get("path", ""))) else "deny"
        return "allow" if call.name in self.always else "ask"


def save(state, path):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)  # atomic: a crash mid-write never leaves half a checkpoint


def load(path):
    with open(path) as f:
        return json.load(f)


def new_state(system, task):
    return {"messages": [{"role": "system", "content": system}, {"role": "user", "content": task}],
            "pending": [], "always": [], "status": "running", "steps": 0, "answer": None}


def respond(state, replies):
    for p, r in zip([p for p in state["pending"] if "reply" not in p], replies):
        p["reply"] = r
    return state


def run_pending(state, box, ckpt):
    while state["pending"]:
        p = state["pending"][0]
        if "reply" not in p:
            return False
        call = ToolCall(name=p["name"], args=p["args"], id=p["id"])
        reply = p["reply"]
        if p["name"] == "ask_user":
            result = reply
        elif reply in ("approve", "always"):
            if reply == "always":
                state["always"].append(p["name"])
            result = box.run(call)
        else:
            reason = reply.partition(":")[2].strip()
            result = "The user denied this action." + (f" Reason: {reason}" if reason else "")
        state["messages"].append(tool_message(call, result))
        state["pending"].pop(0)
        save(state, ckpt)
    return True


def advance(llm, box, state, ckpt, max_steps=12):
    policy = ApprovalPolicy(state["always"])
    if not run_pending(state, box, ckpt):
        state["status"] = "waiting"
        return state
    while state["steps"] < max_steps:
        reply = llm.chat(state["messages"], list(box))
        state["steps"] += 1
        state["messages"].append(reply.message())
        if not reply.tool_calls:
            state.update(status="done", answer=reply.text)
            save(state, ckpt)
            return state
        for call in reply.tool_calls:
            decision = policy.decide(call, box.get(call.name))
            if decision == "allow":
                state["messages"].append(tool_message(call, box.run(call)))
            elif decision == "deny":
                state["messages"].append(tool_message(call, f"Blocked by policy: {call.name} is not allowed "
                                                            f"with {json.dumps(call.args)}."))
            else:
                state["pending"].append({"id": call.id, "name": call.name, "args": call.args, "kind": decision})
            save(state, ckpt)
        if state["pending"]:
            state["status"] = "waiting"
            save(state, ckpt)
            return state
    state["status"] = "max_steps"
    save(state, ckpt)
    return state
