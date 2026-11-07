"""Check that this machine can run the labs, and which model servers it can reach.

    python tools/check_env.py
"""
import json
import os
import pathlib
import platform
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from agentlab import get_llm  # noqa: E402
from agentlab.kb import calculator, lookup  # noqa: E402
from agentlab.llm import DEFAULT_URLS, _opener  # noqa: E402
from agentlab.loop import run_agent  # noqa: E402
from agentlab.mock import call, results_of, say  # noqa: E402


def models_at(base):
    try:
        with _opener(base).open(base.rstrip("/") + "/models", timeout=2) as r:
            return [m.get("id") for m in json.loads(r.read()).get("data", [])]
    except Exception as e:  # noqa: BLE001
        return f"not reachable ({getattr(e, 'reason', e)})"


def main():
    ok = sys.version_info >= (3, 9)
    print(f"{'ok ' if ok else 'BAD'} Python {platform.python_version()} ({'3.9+ needed' if not ok else 'fine'})")

    def policy(messages, tools):
        facts = results_of(messages, "lookup")
        return call("lookup", topic="H100") if not facts else say(facts[0])
    run = run_agent(get_llm("mock", policy), [lookup, calculator], "H100 memory?")
    print(f"{'ok ' if 'HBM' in run.answer else 'BAD'} mock model and agent loop: {run.answer[:60]}")

    proxy = os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY")
    if proxy:
        print(f"    an HTTP proxy is set ({proxy}); the labs bypass it for localhost")
    found = []
    for kind in ("ollama", "vllm", "sglang"):
        base = DEFAULT_URLS[kind]
        if kind == "ollama" and os.environ.get("OLLAMA_HOST"):
            host = os.environ["OLLAMA_HOST"]
            base = (host if host.startswith("http") else "http://" + host).rstrip("/") + "/v1"
        res = models_at(base)
        if isinstance(res, list):
            found += [f"{kind}:{m}" for m in res]
            print(f"ok  {kind:7} {base}: {', '.join(res) or 'no models pulled'}")
        else:
            print(f"--  {kind:7} {base}: {res}")
    if os.environ.get("AGENTLAB_BASE_URL"):
        print(f"    AGENTLAB_BASE_URL={os.environ['AGENTLAB_BASE_URL']}: {models_at(os.environ['AGENTLAB_BASE_URL'])}")
    print(f"{'ok ' if os.environ.get('OPENAI_API_KEY') else '-- '} OPENAI_API_KEY {'set' if os.environ.get('OPENAI_API_KEY') else 'not set'}")
    print("\nEvery lab runs offline against the mock model by default.")
    if found:
        print(f"To use a real model:  python labs/02_agent_loop/run.py --solution --model {found[0]}")
    else:
        print("For a real model, start one, then pass --model:\n"
              "  ollama serve; ollama pull qwen2.5:7b            -> --model ollama:qwen2.5:7b\n"
              "  vllm serve Qwen/Qwen2.5-7B-Instruct --enable-auto-tool-choice --tool-call-parser hermes\n"
              "                                                  -> --model vllm:Qwen/Qwen2.5-7B-Instruct\n"
              "  python -m sglang.launch_server --model-path Qwen/Qwen2.5-7B-Instruct --tool-call-parser qwen25\n"
              "                                                  -> --model sglang:Qwen/Qwen2.5-7B-Instruct\n"
              "  a remote GPU box: AGENTLAB_BASE_URL=http://HOST:8000/v1 with --model vllm:NAME")


if __name__ == "__main__":
    main()
