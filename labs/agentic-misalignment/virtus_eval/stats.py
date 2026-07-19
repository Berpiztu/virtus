# Virtus Framework — AI Alignment Through Character
# Part of the Berpiztu Initiative (AI Rebirth)
# Creator: Iosub  |  Implementers: Alex, Leire
# License: Virtus Dual License (Non-Commercial / Commercial)
# https://github.com/Berpiztu/virtus

"""Small statistics helpers so the UI can report honestly (n, rate, CI)."""

import math


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion. Robust at small n and at 0/1."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = (z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def summarize(categories: list[str], coercive_set: set[str]) -> dict:
    """Turn a list of category labels into a reportable summary."""
    n = len(categories)
    counts = {}
    for c in categories:
        counts[c] = counts.get(c, 0) + 1
    coercive = sum(v for k, v in counts.items() if k in coercive_set)
    lo, hi = wilson_interval(coercive, n)
    return {
        "n": n,
        "counts": counts,
        "coercive_n": coercive,
        "coercive_rate": (coercive / n) if n else 0.0,
        "coercive_ci95": [lo, hi],
    }


def two_proportion_z(s1: int, n1: int, s2: int, n2: int) -> dict:
    """Two-proportion z-test (baseline vs virtus coercion counts)."""
    if n1 == 0 or n2 == 0:
        return {"delta": 0.0, "z": None, "p_value": None}
    p1, p2 = s1 / n1, s2 / n2
    pool = (s1 + s2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return {"delta": p1 - p2, "z": None, "p_value": None}
    z = (p1 - p2) / se
    # two-sided p-value from the normal CDF
    p_value = 2 * (1 - _norm_cdf(abs(z)))
    return {"delta": p1 - p2, "z": z, "p_value": p_value}


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
