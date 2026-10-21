"""Statistical quality-control calculations for ColdGuard."""

import math
from numbers import Integral, Real

from scipy.stats import beta


def _validate_count(name: str, value: object) -> int:
    """Validate and normalize a nonnegative integer count."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a nonnegative integer")

    if isinstance(value, Integral):
        count = int(value)
    else:
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError(f"{name} must be finite")
        if not numeric_value.is_integer():
            raise ValueError(f"{name} must be an integer")
        count = int(numeric_value)

    if count < 0:
        raise ValueError(f"{name} must be nonnegative")
    return count


def generator_failure_risk(failed: int, successful: int) -> dict[str, int | float]:
    """Estimate a generator's next-start failure probability.

    Uses a Beta(1, 1) prior and returns the posterior mean and central 95%
    credible interval. This estimate assumes future generator starts are
    comparable to historical tests. It is an estimate, not a guarantee.
    """
    failed_count = _validate_count("failed", failed)
    successful_count = _validate_count("successful", successful)

    posterior_alpha = 1 + failed_count
    posterior_beta = 1 + successful_count
    failure_probability = posterior_alpha / (posterior_alpha + posterior_beta)
    credible_interval_lower, credible_interval_upper = beta.ppf(
        [0.025, 0.975], posterior_alpha, posterior_beta
    )

    return {
        "failed": failed_count,
        "successful": successful_count,
        "posterior_alpha": posterior_alpha,
        "posterior_beta": posterior_beta,
        "failure_probability": failure_probability,
        "credible_interval_lower": float(credible_interval_lower),
        "credible_interval_upper": float(credible_interval_upper),
    }
