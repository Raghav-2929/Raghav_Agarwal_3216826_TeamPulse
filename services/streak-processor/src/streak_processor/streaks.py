"""Pure streak arithmetic — no I/O, so it is exhaustively unit-tested.

A *period* is a day (``2026-11-08``) for daily habits or an ISO week (``2026-W45``) for weekly
habits. A period is *met* when its completions reach the habit's ``target_per_period``. The streak is
the run of consecutive met periods; it is recomputed from the (bounded) completion history on every
event, so late back-filled completions and duplicate deliveries are handled correctly.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from teampulse_common.events.contracts import Frequency
from teampulse_common.periods import is_alive, period_key, period_start, previous_period

__all__ = [
    "HISTORY_LIMIT",
    "MILESTONES",
    "StreakResult",
    "compute_streak",
    "crossed_milestones",
    "current_run_start",
    "is_alive",
    "merge_history",
    "milestones_to_announce",
    "period_counts",
    "period_key",
    "period_start",
    "previous_period",
]

MILESTONES: tuple[int, ...] = (3, 7, 14, 21, 30, 60, 100, 365)
HISTORY_LIMIT = 400  # completion dates kept per habit (> 1 year of daily history)


def period_counts(dates: Iterable[date], frequency: Frequency) -> Counter[str]:
    return Counter(period_key(d, frequency) for d in set(dates))


@dataclass(frozen=True, slots=True)
class StreakResult:
    current: int  # length of the run ending at the most recent met period
    longest: int
    last_period: str | None  # most recent met period


def _met_periods(dates: Iterable[date], frequency: Frequency, target: int) -> list[str]:
    counts = period_counts(dates, frequency)
    return sorted(k for k, c in counts.items() if c >= target)  # ISO keys sort chronologically


def compute_streak(dates: Iterable[date], frequency: Frequency, target: int = 1) -> StreakResult:
    met = _met_periods(dates, frequency, target)
    longest = run = 0
    previous: str | None = None
    for key in met:
        run = run + 1 if previous is not None and previous_period(key, frequency) == previous else 1
        longest = max(longest, run)
        previous = key
    return StreakResult(current=run, longest=longest, last_period=previous)


def current_run_start(dates: Iterable[date], frequency: Frequency, target: int = 1) -> str | None:
    """First period of the run that ends at the most recent met period (``None`` if nothing is met)."""
    start: str | None = None
    previous: str | None = None
    for key in _met_periods(dates, frequency, target):
        if previous is None or previous_period(key, frequency) != previous:
            start = key
        previous = key
    return start


def crossed_milestones(before: int, after: int, milestones: Iterable[int] = MILESTONES) -> list[int]:
    return [m for m in milestones if before < m <= after]


def milestones_to_announce(
    before: int, after: int, run_start: str | None, announced: dict[str, str]
) -> list[int]:
    """Milestones this completion pushed the streak past, minus those already announced for this run.

    ``announced`` maps a milestone (as text) to the first period of the run it was announced for.
    A late back-fill can join two runs into one. A milestone announced for an earlier part of the
    joined run started on or after ``run_start``, so it is not announced again. A milestone announced
    for an older, separate run started before ``run_start``, so a new run may announce it again.
    """
    return [
        m
        for m in crossed_milestones(before, after)
        if run_start is None or announced.get(str(m), "") < run_start
    ]


def merge_history(history: Iterable[str], new_day: date, limit: int = HISTORY_LIMIT) -> list[str]:
    """Add a completion date to the stored ISO-date history (deduplicated, bounded, sorted)."""
    merged = sorted(set(history) | {new_day.isoformat()})
    return merged[-limit:]
