"""Lab 13 reference: agent trajectories as training data, GRPO advantages, prefix-cache reuse."""
from agentlab.tokens import _PIECE


def tokenize(text):
    return _PIECE.findall(text)


def sft_example(segments):
    ids, mask = [], []
    for text, trained in segments:
        toks = tokenize(text)
        ids += toks
        mask += [1 if trained else 0] * len(toks)
    return ids, mask


def reward(run, expected):
    correct = 1.0 if expected in run.answer else 0.0
    return correct - 0.1 * max(0, run.steps - 3)


def group_advantages(rewards, eps=1e-6):
    n = len(rewards)
    mean = sum(rewards) / n
    std = (sum((r - mean) ** 2 for r in rewards) / n) ** 0.5
    return [(r - mean) / (std + eps) for r in rewards]


def common_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def prefix_hit_rate(prompts):
    toks = [tokenize(p) for p in prompts]
    total = sum(len(t) for t in toks)
    hits = sum(common_prefix(prev, cur) for prev, cur in zip(toks, toks[1:]))
    return hits / total
