"""agentlab: the small, dependency-free toolkit the labs build on.

    llm      Reply, ToolCall, and the model backends (mock, Ollama, vLLM, SGLang, OpenAI)
    tokens   an approximate token counter, so context sizes are visible
    tools    Tool, the @tool decorator (JSON schema from a Python signature), Toolbox
    loop     run_agent, the reference agent loop from Lab 02
    mock     helpers for writing the scripted "mock model" policies the labs use offline
    trace    pretty-printing of a run, step by step
    labs     the command line every lab shares (--solution, --model, --trace)
"""
from .llm import LLM, MockLLM, OpenAICompatLLM, Reply, ToolCall, get_llm, tool_message  # noqa: F401
from .tokens import count, count_messages  # noqa: F401
from .tools import Tool, Toolbox, function_schema, tool  # noqa: F401
