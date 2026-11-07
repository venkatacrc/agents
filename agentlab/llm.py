"""Model backends behind one interface: llm.chat(messages, tools) -> Reply.

Messages use the OpenAI chat format, which Ollama, vLLM, SGLang and most
providers accept:

    {"role": "system" | "user", "content": "..."}
    {"role": "assistant", "content": "...", "tool_calls": [{"id", "type": "function",
                                                            "function": {"name", "arguments": "<json>"}}]}
    {"role": "tool", "tool_call_id": "...", "name": "...", "content": "..."}

Pick a backend with --model (or the AGENTLAB_MODEL environment variable):

    mock                      the lab's scripted policy: offline, deterministic, free
    ollama:gpt-oss:20b        Ollama on localhost:11434 (OLLAMA_HOST to change)
    vllm:Qwen/Qwen3-8B        vLLM's OpenAI server, default http://localhost:8000/v1
    sglang:Qwen/Qwen3-8B      SGLang's OpenAI server, default http://localhost:30000/v1
    openai:gpt-4.1-mini       OpenAI (OPENAI_API_KEY; OPENAI_BASE_URL for any compatible API)

AGENTLAB_BASE_URL overrides the server address for every non-mock backend.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import tokens


@dataclass
class ToolCall:
    name: str
    args: dict
    id: str = ""


@dataclass
class Reply:
    text: str = ""
    tool_calls: list = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def message(self) -> dict:
        """The assistant message to append to the conversation."""
        m = {"role": "assistant", "content": self.text}
        if self.tool_calls:
            m["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.args)}}
                for c in self.tool_calls
            ]
        return m


def tool_message(call: ToolCall, content: str) -> dict:
    return {"role": "tool", "tool_call_id": call.id, "name": call.name, "content": content}


class LLM:
    """Counts calls and tokens for every backend, so labs can measure cost."""

    name = "llm"

    def __init__(self):
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.peak_prompt_tokens = 0
        self.requests: list = []  # (messages, tools) of every call, for labs that inspect prompts
        self._lock = threading.Lock()  # workflows call one model from several threads

    def chat(self, messages: list, tools: Optional[list] = None, **kw) -> Reply:
        tools = list(tools or [])
        reply = self._chat(messages, tools, **kw)
        if not reply.prompt_tokens:
            reply.prompt_tokens = tokens.count_messages(messages) + tokens.count_tools(tools)
        if not reply.completion_tokens:
            reply.completion_tokens = tokens.count_message(reply.message())
        with self._lock:
            self._account(messages, tools, reply)
        return reply

    def _account(self, messages, tools, reply):
        self.requests.append(([dict(m) for m in messages], tools))
        self.calls += 1
        self.prompt_tokens += reply.prompt_tokens
        self.completion_tokens += reply.completion_tokens
        self.peak_prompt_tokens = max(self.peak_prompt_tokens, reply.prompt_tokens)

    def _chat(self, messages, tools, **kw) -> Reply:
        raise NotImplementedError

    def usage(self) -> str:
        return (f"{self.calls} model calls, {self.prompt_tokens:,} prompt + {self.completion_tokens:,} "
                f"completion tokens, peak prompt {self.peak_prompt_tokens:,}")


class MockLLM(LLM):
    """A stand-in model: a Python function plays the model's part.

    policy(messages, tools) returns a Reply, a string (a final answer) or a list
    of ToolCall. Policies only see what a real model would see, the messages and
    the tool definitions, so a broken harness breaks them the same way.
    """

    name = "mock"

    def __init__(self, policy: Callable, latency: float = 0.0):
        super().__init__()
        self.policy = policy
        self.latency = latency
        self._ids = 0

    def _chat(self, messages, tools, **kw) -> Reply:
        if self.latency:
            time.sleep(self.latency)
        with self._lock:
            out = self.policy(messages, tools)
        if isinstance(out, str):
            out = Reply(text=out)
        elif isinstance(out, ToolCall):
            out = Reply(tool_calls=[out])
        elif isinstance(out, list):
            out = Reply(tool_calls=out)
        with self._lock:
            for c in out.tool_calls:
                if not c.id:
                    self._ids += 1
                    c.id = f"call_{self._ids}"
        return out


def _opener(url: str):
    """Talk to local servers directly even when an HTTP proxy is configured."""
    host = urllib.parse.urlparse(url).hostname or ""
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith(".local"):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


class OpenAICompatLLM(LLM):
    """Any server that speaks POST /v1/chat/completions with tool calling."""

    def __init__(self, base_url: str, model: str, api_key: str = "", temperature: float = 0.0, timeout: float = 300):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout
        self.name = model

    def _chat(self, messages, tools, **kw) -> Reply:
        body = {"model": self.model, "messages": messages, "temperature": kw.get("temperature", self.temperature)}
        if tools:
            body["tools"] = [t.schema() if hasattr(t, "schema") else t for t in tools]
        if kw.get("json"):
            body["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        try:
            with _opener(self.base_url).open(req, timeout=self.timeout) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{self.base_url}: HTTP {e.code}: {e.read().decode(errors='replace')[:500]}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"cannot reach {self.base_url} ({e.reason}). Is the server running?") from None
        msg = data["choices"][0]["message"]
        calls = []
        for c in msg.get("tool_calls") or []:
            f = c.get("function", {})
            raw = f.get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except json.JSONDecodeError:
                args = {"_unparsed": raw}
            calls.append(ToolCall(name=f.get("name", ""), args=args, id=c.get("id") or f"call_{len(calls)}"))
        usage = data.get("usage") or {}
        return Reply(text=msg.get("content") or "", tool_calls=calls,
                     prompt_tokens=usage.get("prompt_tokens", 0), completion_tokens=usage.get("completion_tokens", 0))


DEFAULT_URLS = {
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
    "sglang": "http://localhost:30000/v1",
    "openai": "https://api.openai.com/v1",
}


def get_llm(spec: Optional[str] = None, policy: Optional[Callable] = None, latency: float = 0.0) -> LLM:
    spec = spec or os.environ.get("AGENTLAB_MODEL", "mock")
    if spec == "mock":
        if policy is None:
            raise SystemExit("this script has no mock policy; pass --model ollama:<name> (or vllm:, sglang:, openai:)")
        return MockLLM(policy, latency=latency)
    kind, _, model = spec.partition(":")
    if kind not in DEFAULT_URLS or not model:
        raise SystemExit(f"unknown --model {spec!r}; use mock, ollama:NAME, vllm:NAME, sglang:NAME or openai:NAME")
    url = os.environ.get("AGENTLAB_BASE_URL")
    if not url and kind == "ollama" and os.environ.get("OLLAMA_HOST"):
        host = os.environ["OLLAMA_HOST"]
        url = (host if host.startswith("http") else "http://" + host).rstrip("/") + "/v1"
    if not url and kind == "openai":
        url = os.environ.get("OPENAI_BASE_URL")
    key = os.environ.get("OPENAI_API_KEY", "") if kind == "openai" else os.environ.get("AGENTLAB_API_KEY", "")
    return OpenAICompatLLM(url or DEFAULT_URLS[kind], model, api_key=key)
