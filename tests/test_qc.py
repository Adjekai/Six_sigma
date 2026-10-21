import math

import pytest

from app.qc import generator_failure_risk


def test_two_failures_and_eight_successes_known_answer():
    result = generator_failure_risk(2, 8)

    assert result["failure_probability"] == pytest.approx(0.25)
    assert result["posterior_alpha"] == 3
    assert result["posterior_beta"] == 9


def test_credible_interval_is_ordered_and_within_probability_bounds():
    result = generator_failure_risk(2, 8)

    # The credible interval describes uncertainty in the posterior failure probability.
    assert 0 < result["credible_interval_lower"]
    assert result["credible_interval_lower"] < result["credible_interval_upper"]
    assert result["credible_interval_upper"] < 1


def test_no_tests_returns_prior_mean():
    result = generator_failure_risk(0, 0)

    assert result["failure_probability"] == pytest.approx(0.5)


@pytest.mark.parametrize("bad_count", [-1, 1.5, True, "2", None, math.nan, math.inf])
def test_invalid_counts_are_rejected(bad_count):
    with pytest.raises((TypeError, ValueError)):
        generator_failure_risk(bad_count, 0)


@pytest.mark.parametrize(
    "bad_count", [-1, 1.5, False, "2", None, math.nan, -math.inf, math.inf]
)
def test_invalid_success_counts_are_rejected(bad_count):
    with pytest.raises((TypeError, ValueError)):
        generator_failure_risk(0, bad_count)
