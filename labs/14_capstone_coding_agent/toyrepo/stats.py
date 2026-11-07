"""Small statistics helpers used by the metrics dashboard."""


def mean(xs):
    return sum(xs) / len(xs)


def median(xs):
    s = sorted(xs)
    return s[len(s) // 2]


def percentile(xs, p):
    """Nearest-rank percentile, p in [0, 100]."""
    s = sorted(xs)
    k = max(0, min(len(s) - 1, round(p / 100 * len(s)) - 1))
    return s[k]
