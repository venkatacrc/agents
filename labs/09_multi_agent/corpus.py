"""A small library of serving-technique notes for the research agents to search and read."""
import random

_rng = random.Random(9)
_FILLER = [
    "The method was evaluated on a range of model sizes and request mixes.",
    "Implementation details matter: kernel launch overheads and memory layout change the picture.",
    "Production deployments report results that vary with traffic shape and batch size.",
    "Several open-source engines, including vLLM, SGLang and TensorRT-LLM, ship an implementation.",
    "The technique composes with tensor parallelism, though the gains are not always additive.",
    "Profiling with Nsight Systems shows where the time goes before and after the change.",
    "Benchmarks used ShareGPT-style conversations and synthetic long-context prompts.",
    "Tail latency (p99) often moves differently from the mean and should be measured separately.",
]


def _pad(core, n=14):
    lines = [_rng.choice(_FILLER) for _ in range(n)]
    half = n // 2
    return "\n".join(lines[:half] + core + lines[half:])


DOCS = {
    "speculative-decoding-overview": _pad([
        "Speculative decoding drafts several tokens with a small model and verifies them in one pass of the large model.",
        "Key result: 2-3x lower latency per token at batch size 1 with an acceptance rate around 0.7.",
    ]),
    "speculative-decoding-in-production": _pad([
        "At high batch sizes the GPU is already busy, so verification work competes with other requests.",
        "Caveat: speed-up shrinks toward 1x at large batch sizes and depends on draft acceptance rate.",
    ]),
    "prefix-caching-overview": _pad([
        "Prefix caching keeps the KV cache of shared prompt prefixes (system prompts, tool definitions, history).",
        "Key result: up to 5x faster time to first token and about 90% fewer prefill FLOPs on agent workloads with long shared prefixes.",
    ]),
    "prefix-caching-pitfalls": _pad([
        "Any change early in the prompt (a timestamp in the system prompt, reordered tools) invalidates everything after it.",
        "Caveat: only exact token-prefix matches hit the cache; keep prompts append-only and stable.",
    ]),
    "fp8-quantization-overview": _pad([
        "FP8 (E4M3) weights and activations halve memory traffic compared with BF16 on Hopper and Blackwell GPUs.",
        "Key result: about 1.6x higher throughput and half the weight memory with under 1% accuracy loss on most benchmarks.",
    ]),
    "fp8-quantization-accuracy": _pad([
        "Outlier channels and long reasoning chains are the most sensitive; per-channel scales help.",
        "Caveat: needs calibration and per-tensor or per-channel scaling; some tasks (math, code) degrade more.",
    ]),
    "continuous-batching": _pad(["Continuous batching adds and removes requests at every decode step.",
                                 "Key result: 10-20x throughput over static batching."]),
    "paged-attention": _pad(["PagedAttention stores the KV cache in fixed-size blocks like virtual memory pages.",
                             "Key result: near-zero KV fragmentation, 2-4x more concurrent requests."]),
    "disaggregated-serving": _pad(["Prefill and decode run on separate GPU pools and the KV cache is transferred.",
                                   "Key result: better goodput under strict time-to-first-token and inter-token SLOs."]),
}


def search_docs(query):
    words = [w for w in query.lower().replace("-", " ").split() if len(w) > 2]
    scored = sorted(((sum(w in name.replace("-", " ") for w in words), name) for name in DOCS), reverse=True)
    return [name for s, name in scored if s > 0][:3]
