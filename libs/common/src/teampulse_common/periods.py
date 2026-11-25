"""Calendar-period arithmetic shared by the streak processor (writes streaks) and the Insight Service
(decides whether a stored streak is still alive). Pure functions, no I/O."""

from __future__ import annotations

from datetime import date, timedelta

from teampulse_common.events.contracts import Frequency


def period_key(day: date, frequency: Frequency) -> str:
    """``2026-11-08`` for daily habits, ISO week ``2026-W45`` for weekly habits."""
    if frequency is Frequency.DAILY:
        return day.isoformat()
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def period_start(key: str, frequency: Frequency) -> date:
    if frequency is Frequency.DAILY:
        return date.fromisoformat(key)
    year, week = key.split("-W")
    return date.fromisocalendar(int(year), int(week), 1)


def previous_period(key: str, frequency: Frequency) -> str:
    step = timedelta(days=1 if frequency is Frequency.DAILY else 7)
    return period_key(period_start(key, frequency) - step, frequency)


def is_alive(last_period: str | None, frequency: Frequency, today: date) -> bool:
    """A streak is alive if its last met period is the previous one or later: today's / this week's
    completion may simply not have happened yet, and an employee east of UTC can legitimately already
    be on "tomorrow" relative to the server's UTC date. ISO keys compare chronologically as strings."""
    if last_period is None:
        return False
    return last_period >= previous_period(period_key(today, frequency), frequency)
