"""The tools the lab's MCP server exposes: a small, fake GPU cluster."""
from agentlab.tools import tool

NODES = {"us-east": [("gpu-a1", "H100", 8, 3), ("gpu-a2", "H100", 8, 8), ("gpu-a3", "A100", 8, 0)],
         "eu-west": [("gpu-e1", "B200", 8, 2)]}
JOBS = {"job-123": "running, 32 GPUs, step 9100", "job-121": "failed: CUDA out of memory at step 300"}


@tool
def gpu_inventory(region: str) -> str:
    """List GPU nodes in a region with GPU type and free GPUs.

    Args:
        region: us-east or eu-west
    """
    if region not in NODES:
        raise ValueError(f"unknown region {region!r}; use one of {', '.join(NODES)}")
    return "\n".join(f"{n}: {kind}, {free}/{total} free" for n, kind, total, free in NODES[region])


@tool
def job_status(job_id: str) -> str:
    """Get the status of a training job.

    Args:
        job_id: e.g. job-123
    """
    return f"{job_id}: {JOBS.get(job_id, 'not found')}"


@tool
def kv_cache_gb(layers: int, kv_heads: int, head_dim: int, tokens: int, bytes_per_value: int = 2) -> str:
    """KV cache size in GB for one sequence: 2 x layers x kv_heads x head_dim x tokens x bytes.

    Args:
        layers: transformer layers
        kv_heads: KV heads per layer
        head_dim: head dimension
        tokens: sequence length in tokens
        bytes_per_value: 2 for BF16, 1 for FP8
    """
    return f"{2 * layers * kv_heads * head_dim * tokens * bytes_per_value / 1e9:.2f} GB"


TOOLS = [gpu_inventory, job_status, kv_cache_gb]
