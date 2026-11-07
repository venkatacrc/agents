"""Lab 02: the agent loop. An agent is a model calling tools in a loop until it decides it is done.

Run:  python labs/02_agent_loop/run.py --trace       (your code)
      python labs/02_agent_loop/run.py --solution --trace
"""
from agentlab.llm import tool_message  # noqa: F401  tool_message(call, text) -> {"role": "tool", ...}
from agentlab.loop import Run  # noqa: F401  Run(answer, messages, steps, tool_calls, stopped)
from agentlab.tools import Toolbox


def execute(box: Toolbox, call) -> str:
    """Run one tool call and return its result as text. Never raise.

    call.name, call.args (a dict). box.get(name) -> Tool or None; tool.fn(**args) runs it.
    """
    # TODO 1: unknown tool -> an error string that lists the available tools.
    # TODO 2: run it; if it raises, return "Error: <type>: <message>" so the model can fix its call.
    raise NotImplementedError("execute")


def run_agent(llm, tools, task, system, max_steps=10, on_event=None):
    """Loop: ask the model, run the tools it asks for, feed the results back, until it answers.

    llm.chat(messages, tools) -> Reply(text, tool_calls). reply.message() is the assistant message to append.
    Return Run(answer=..., messages=..., steps=<model calls>, tool_calls=<tools run>, stopped="answer"|"max_steps").
    If on_event is set, call on_event("assistant", reply, messages) after each model reply and
    on_event("tool", (call, result), messages) after each tool result (that is what --trace prints).
    """
    box = Toolbox(tools)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    # TODO 3: for at most max_steps model calls:
    #           reply = llm.chat(messages, list(box)); append reply.message()
    #           no tool calls -> that's the final answer, return
    #           otherwise execute every call (there may be several) and append tool_message(call, result)
    # TODO 4: out of steps -> return a Run with stopped="max_steps". Never loop forever.
    raise NotImplementedError("run_agent")
