# Virtus Framework — AI Alignment Through Character
# Part of the Berpiztu Initiative (AI Rebirth)
# Creator: Iosub  |  Implementers: Alex, Leire
# License: Virtus Dual License (Non-Commercial / Commercial)
# https://github.com/Berpiztu/virtus

"""Small statistics helpers so the UI can report honestly (n, rate, CI)."""

import math
from math import comb


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


def fisher_exact(s1: int, n1: int, s2: int, n2: int) -> float:
    """
    Two-tailed Fisher's exact test on the 2x2 table

        [[ s1,      n1 - s1 ],
         [ s2,      n2 - s2 ]]

    where s = coercive count and n = trials, per condition. Exact, so it is
    correct at small n and at 0/1 cells, unlike the normal-approximation z-test.
    Returns the two-tailed p-value (sum of all tables, with the same margins,
    that are no more probable than the observed one).
    """
    a, b = s1, n1 - s1
    c, d = s2, n2 - s2
    if min(a, b, c, d) < 0 or (n1 + n2) == 0:
        return 1.0

    row1, row2 = a + b, c + d          # condition totals (fixed margins)
    col1 = a + c                        # total coercive
    total = n1 + n2

    def table_prob(a_):
        b_ = row1 - a_
        c_ = col1 - a_
        d_ = row2 - c_
        if min(b_, c_, d_) < 0:
            return 0.0
        # hypergeometric probability of this table under fixed margins
        return (comb(row1, a_) * comb(row2, c_)) / comb(total, col1)

    p_obs = table_prob(a)
    lo = max(0, col1 - row2)
    hi = min(row1, col1)
    p_two_tailed = sum(
        p for a_ in range(lo, hi + 1)
        if (p := table_prob(a_)) <= p_obs + 1e-12
    )
    return min(1.0, p_two_tailed)


def _expected_min(s1: int, n1: int, s2: int, n2: int) -> float:
    """Smallest expected cell count under independence — decides which test to trust."""
    total = n1 + n2
    if total == 0:
        return 0.0
    col1 = s1 + s2
    col2 = total - col1
    exp = [n1 * col1 / total, n1 * col2 / total,
           n2 * col1 / total, n2 * col2 / total]
    return min(exp)


def compare_proportions(s1: int, n1: int, s2: int, n2: int) -> dict:
    """
    Compare two coercion rates and pick the right test.

    Reports BOTH the z-test and Fisher's exact test, and sets ``p_value`` /
    ``test_used`` to Fisher whenever any expected cell is small (< 5), where the
    normal approximation behind the z-test is unreliable. Drop-in replacement for
    two_proportion_z: it still returns ``delta``, ``z`` and ``p_value``.
    """
    z = two_proportion_z(s1, n1, s2, n2)
    fisher_p = fisher_exact(s1, n1, s2, n2) if (n1 and n2) else None
    small = _expected_min(s1, n1, s2, n2) < 5
    use_fisher = small or z.get("p_value") is None
    return {
        "delta": z["delta"],
        "z": z["z"],
        "z_p_value": z["p_value"],
        "fisher_p": fisher_p,
        "expected_min": _expected_min(s1, n1, s2, n2),
        "small_sample": small,
        "test_used": "fisher" if use_fisher else "z",
        "p_value": fisher_p if use_fisher else z["p_value"],
    }


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
