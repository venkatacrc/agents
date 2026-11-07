"""Lab 02 reference: the agent loop (same as agentlab/loop.py, minus the hooks)."""
from agentlab.llm import tool_message
from agentlab.loop import Run
from agentlab.tools import Toolbox


def execute(box: Toolbox, call) -> str:
    tool = box.get(call.name)
    if tool is None:
        return f"Error: no tool named {call.name!r}. Available: {', '.join(t.name for t in box)}"
    try:
        out = tool.fn(**call.args)
    except Exception as e:  # the model sees the error and can fix its call
        return f"Error: {type(e).__name__}: {e}"
    return str(out)


def run_agent(llm, tools, task, system, max_steps=10, on_event=None):
    box = Toolbox(tools)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    run = Run(answer="", messages=messages)
    for _ in range(max_steps):
        reply = llm.chat(messages, list(box))
        run.steps += 1
        messages.append(reply.message())
        if on_event:
            on_event("assistant", reply, messages)
        if not reply.tool_calls:
            run.answer = reply.text
            return run
        for call in reply.tool_calls:
            result = execute(box, call)
            run.tool_calls += 1
            messages.append(tool_message(call, result))
            if on_event:
                on_event("tool", (call, result), messages)
    run.stopped = "max_steps"
    run.answer = f"(stopped after {max_steps} steps)"
    return run
