"""Public statistical interface for BloodWatch.

Framework code should import functions from here or the focused modules below.
"""

from bloodwatch.financial import expected_annual_blackout_loss, summarize_financials
from bloodwatch.incidents import summarize_breach_and_recovery
from bloodwatch.reliability import generator_reliability, refrigerator_reliability
from bloodwatch.temperature import analyze_temperature_process, summarize_temperature

__all__ = [
    "expected_annual_blackout_loss",
    "analyze_temperature_process",
    "generator_reliability",
    "refrigerator_reliability",
    "summarize_breach_and_recovery",
    "summarize_financials",
    "summarize_temperature",
]
