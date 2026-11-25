from __future__ import annotations

import pytest

from streak_processor.badges import UserStats, eligible_badges, is_satisfied
from teampulse_common.events.contracts import DEFAULT_BADGE_RULES, BadgeCriterion, BadgeRule, Category


def rule(
    criterion: BadgeCriterion, threshold: int, category: Category | None = None, active: bool = True
) -> BadgeRule:
    return BadgeRule(
        code="test_rule",
        name="Test",
        criterion=criterion,
        threshold=threshold,
        category=category,
        is_active=active,
    )


@pytest.mark.parametrize(("streak", "ok"), [(6, False), (7, True), (8, True)])
def test_streak_threshold_is_inclusive(streak, ok):
    assert (
        is_satisfied(rule(BadgeCriterion.STREAK_DAYS, 7), UserStats(total_completions=0, streak=streak)) is ok
    )


@pytest.mark.parametrize(("total", "ok"), [(9, False), (10, True)])
def test_total_completions(total, ok):
    assert is_satisfied(rule(BadgeCriterion.TOTAL_COMPLETIONS, 10), UserStats(total, streak=0)) is ok


def test_category_completions_only_counts_matching_category():
    r = rule(BadgeCriterion.CATEGORY_COMPLETIONS, 3, Category.MINDFULNESS)
    assert not is_satisfied(r, UserStats(10, 0, {"fitness": 10, "mindfulness": 2}))
    assert is_satisfied(r, UserStats(10, 0, {"mindfulness": 3}))


def test_category_with_no_completions_counts_as_zero():
    r = rule(BadgeCriterion.CATEGORY_COMPLETIONS, 1, Category.MINDFULNESS)
    assert not is_satisfied(r, UserStats(10, 3, {"fitness": 10}))  # no mindfulness at all


def test_category_rule_without_category_never_fires():
    assert not is_satisfied(rule(BadgeCriterion.CATEGORY_COMPLETIONS, 1), UserStats(5, 5, {"fitness": 5}))


def test_inactive_rules_never_fire():
    assert not is_satisfied(rule(BadgeCriterion.TOTAL_COMPLETIONS, 1, active=False), UserStats(100, 100))


def test_default_rules_for_a_first_completion():
    assert [r.code for r in eligible_badges(DEFAULT_BADGE_RULES, UserStats(1, 1))] == ["first_step"]


def test_default_rules_for_a_seven_day_streak():
    codes = {r.code for r in eligible_badges(DEFAULT_BADGE_RULES, UserStats(7, 7))}
    assert codes == {"first_step", "on_a_roll", "week_warrior"}
