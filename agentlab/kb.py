"""Two small tools the early labs share: a fact lookup and a safe calculator.

The facts are about hardware and models you already know from training and
serving, so you can check the agent's arithmetic in your head.
"""
from __future__ import annotations

import ast
import operator

from .tools import tool

FACTS = {
    "h100": "NVIDIA H100 SXM: 80 GB HBM3, 3.35 TB/s memory bandwidth, 989 TFLOP/s dense BF16, 700 W.",
    "a100": "NVIDIA A100 SXM: 80 GB HBM2e (a 40 GB version also exists), 2.0 TB/s, 312 TFLOP/s dense BF16, 400 W.",
    "b200": "NVIDIA B200: 192 GB HBM3e, 8 TB/s memory bandwidth, 2250 TFLOP/s dense BF16, 1000 W.",
    "l4": "NVIDIA L4: 24 GB GDDR6, 300 GB/s memory bandwidth, 121 TFLOP/s dense BF16, 72 W.",
    "llama-3-70b": "Llama 3 70B: 70.6 billion parameters, 80 layers, 8 KV heads of dimension 128, 128K context.",
    "gpt-oss-20b": "gpt-oss-20b: 21 billion parameters (3.6 billion active per token, mixture of experts), MXFP4 weights, fits in 16 GB.",
    "bf16": "bfloat16 (BF16): 2 bytes per value, 8 exponent bits, 7 mantissa bits.",
    "kv cache": "KV cache per token = 2 (K and V) x layers x kv_heads x head_dim x bytes per value.",
}

_ALIASES = {"h100 sxm": "h100", "a100 80gb": "a100", "llama 3 70b": "llama-3-70b", "llama3-70b": "llama-3-70b",
            "gpt-oss": "gpt-oss-20b", "bfloat16": "bf16", "kv": "kv cache", "kv-cache": "kv cache"}


@tool
def lookup(topic: str) -> str:
    """Look up a fact about a GPU, a model or a number format in the knowledge base.

    Args:
        topic: the thing to look up, e.g. "H100", "Llama-3-70B", "BF16" or "KV cache"
    """
    key = topic.strip().lower().replace("nvidia ", "")
    key = _ALIASES.get(key, key)
    if key in FACTS:
        return FACTS[key]
    near = [k for k in FACTS if key in k or k in key]
    if near:
        return FACTS[near[0]]
    return f"No entry for {topic!r}. Known topics: {', '.join(FACTS)}."


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("only numbers and + - * / // % ** ( ) are allowed")


@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression exactly. Use it for any arithmetic instead of doing it in your head.

    Args:
        expression: arithmetic using numbers and + - * / // % ** ( ), e.g. "8 * 80 + 4 * 80"
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        raise ValueError(f"cannot parse {expression!r}: use numbers and + - * / // % ** ( ), "
                         "with * for multiplication") from None
    value = _eval(tree)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:.12g}"
    return str(value)
