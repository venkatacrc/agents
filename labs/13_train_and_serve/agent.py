"""Lab 13: how agentic models are trained and served, seen from the harness.

Run:  python labs/13_train_and_serve/run.py             (your code)
      python labs/13_train_and_serve/run.py --solution

Training: an agent run is a token sequence. Supervised fine-tuning (SFT) on good trajectories puts the
loss only on what the model wrote. RL (GRPO-style) samples a group of rollouts per task, scores them
with a verifiable reward, and pushes up the ones better than the group's average.
Serving: every step is a new request whose prompt is the previous prompt plus a little. A prefix cache
reuses the KV cache of the shared part, if the harness keeps the history append-only.
"""
from agentlab.tokens import _PIECE  # noqa: F401  the regex behind the course's approximate tokenizer


def tokenize(text):
    return _PIECE.findall(text)


def sft_example(segments):
    """segments: [(text, trained)] in order; trained is True for the assistant's own tokens (its words, its
    tool calls, and the <|im_end|> that teaches it to stop). Return (tokens, loss_mask) with mask 1 = loss."""
    # TODO 1
    raise NotImplementedError("sft_example")


def reward(run, expected):
    """A verifiable reward: 1.0 if `expected` is in run.answer else 0.0, minus 0.1 for every model call
    (run.steps) beyond 3, a stand-in for latency and cost."""
    # TODO 2
    raise NotImplementedError("reward")


def group_advantages(rewards, eps=1e-6):
    """GRPO: advantage_i = (r_i - mean(r)) / (std(r) + eps), population std over the group.
    No value network: the group is the baseline."""
    # TODO 3
    raise NotImplementedError("group_advantages")


def common_prefix(a, b):
    """Number of leading tokens two token lists share."""
    # TODO 4
    raise NotImplementedError("common_prefix")


def prefix_hit_rate(prompts):
    """Fraction of all prompt tokens served from a prefix cache that holds the previous request:
    sum of common_prefix(prev, cur) over consecutive prompts / total tokens of all prompts."""
    # TODO 5
    raise NotImplementedError("prefix_hit_rate")
