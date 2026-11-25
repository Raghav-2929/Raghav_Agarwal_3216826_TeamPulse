"""Badge-rule evaluation (pure). Rules are owned by the Challenge Service and arrive here through the
``badge_rules.changed`` event (event-carried state transfer), so evaluation needs no network call."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from teampulse_common.events.contracts import BadgeCriterion, BadgeRule


@dataclass(frozen=True, slots=True)
class UserStats:
    total_completions: int
    streak: int  # current streak of the habit that was just completed
    category_completions: dict[str, int] = field(default_factory=dict)


def is_satisfied(rule: BadgeRule, stats: UserStats) -> bool:
    if not rule.is_active:
        return False
    if rule.criterion is BadgeCriterion.STREAK_DAYS:
        return stats.streak >= rule.threshold
    if rule.criterion is BadgeCriterion.TOTAL_COMPLETIONS:
        return stats.total_completions >= rule.threshold
    if rule.criterion is BadgeCriterion.CATEGORY_COMPLETIONS:
        return (
            rule.category is not None
            and stats.category_completions.get(rule.category.value, 0) >= rule.threshold
        )
    return False  # pragma: no cover - exhaustive


def eligible_badges(rules: Iterable[BadgeRule], stats: UserStats) -> list[BadgeRule]:
    return [rule for rule in rules if is_satisfied(rule, stats)]
