"""Unit tests for the pure aggregation layer: rounding, defaults, ordering and k-anonymity edge cases
that the API-level tests in ``test_insights.py`` do not pin down."""

from __future__ import annotations

import uuid
from datetime import date

from insight_service.aggregation import badges_from, personal_series, streaks_from, team_series
from teampulse_common.events.contracts import Category

D1, D2, D3 = date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)


def day(d: date, **attrs) -> dict:
    return {"pk": "X", "sk": f"DAY#{d.isoformat()}", **attrs}


class TestPersonalSeries:
    def test_values_and_totals_are_rounded_to_two_decimals(self):
        daily, _, totals = personal_series([day(D1, completions=1, value=1.234)], D1, D1, None)
        assert daily[0].value == 1.23
        _, _, totals = personal_series(
            [day(D1, completions=1, value=0.1), day(D2, completions=1, value=0.2)], D1, D2, None
        )
        assert totals.total_value == 0.3  # not 0.30000000000000004

    def test_consistency_rate_is_active_days_over_days_in_range(self):
        _, _, totals = personal_series([day(D1, completions=2, value=2)], D1, D3, None)
        assert (totals.completions, totals.active_days, totals.consistency_rate) == (2, 1, 0.33)

    def test_category_filter_restricts_series_and_breakdown(self):
        items = [day(D1, completions=3, value=3, cat_fitness=2, cat_sleep=1)]
        daily, breakdown, _ = personal_series(items, D1, D1, Category.FITNESS)
        assert daily[0].completions == 2
        assert [(c.category.value, c.completions) for c in breakdown] == [("fitness", 2)]

    def test_breakdown_without_filter_is_sorted_and_omits_zero(self):
        items = [day(D1, completions=3, cat_sleep=1, cat_fitness=2, cat_learning=0)]
        _, breakdown, _ = personal_series(items, D1, D1, None)
        assert [(c.category.value, c.completions) for c in breakdown] == [("fitness", 2), ("sleep", 1)]


class TestStreaksAndBadges:
    def test_missing_counters_default_to_zero(self):
        habit = uuid.uuid4()
        [s] = streaks_from(
            [{"sk": f"STREAK#{habit}", "frequency": "daily", "last_period": "2026-11-08"}], date(2026, 11, 8)
        )
        assert (s.current, s.longest, s.total_completions, s.alive) == (0, 0, 0, True)

    def test_dead_streak_reports_zero_current(self):
        [s] = streaks_from(
            [
                {
                    "sk": f"STREAK#{uuid.uuid4()}",
                    "frequency": "daily",
                    "last_period": "2026-11-01",
                    "current": 5,
                    "longest": 9,
                    "total": 20,
                }
            ],
            date(2026, 11, 8),
        )
        assert (s.current, s.longest, s.total_completions, s.alive) == (0, 9, 20, False)

    def test_streaks_sorted_by_current_then_longest(self):
        today = date(2026, 11, 8)
        items = [
            {"sk": f"STREAK#{uuid.uuid4()}", "last_period": "2026-11-08", "current": c, "longest": lg}
            for c, lg in [(1, 9), (4, 4), (1, 3)]
        ]
        assert [(s.current, s.longest) for s in streaks_from(items, today)] == [(4, 4), (1, 9), (1, 3)]

    def test_badges_newest_first(self):
        items = [
            {"code": c, "name": c, "awarded_at": f"2026-11-0{n}T10:00:00+00:00"}
            for c, n in [("a", 1), ("b", 3), ("c", 2)]
        ]
        assert [b.code for b in badges_from(items)] == ["b", "c", "a"]


class TestTeamSeries:
    def test_average_is_over_active_days_only_and_rounded(self):
        items = [
            day(D1, completions=3, active_users={"a", "b", "c"}),
            day(D2, completions=4, active_users={"a", "b", "c", "d"}),
            day(D3, completions=5, active_users={"a", "b", "c", "d"}),
        ]
        _, totals, _, _ = team_series(items, D1, date(2026, 11, 4), 3, None)  # 4th day has no data
        assert totals.active_days == 3
        assert totals.avg_active_members == 3.67
        assert totals.completions == 12

    def test_zero_activity_days_are_suppressed_too(self):
        # Releasing "0" would reveal that every member was inactive that day.
        daily, totals, _, _ = team_series([], D1, D2, 3, None)
        assert [(d.completions, d.active_members, d.suppressed) for d in daily] == [
            (None, None, True),
            (None, None, True),
        ]
        assert (totals.active_days, totals.avg_active_members, totals.suppressed_days) == (0, 0.0, 2)

    def test_exactly_k_members_is_released_k_minus_one_is_suppressed(self):
        items = [
            day(D1, completions=2, active_users={"a", "b"}),
            day(D2, completions=3, active_users={"a", "b", "c"}),
        ]
        daily, totals, _, _ = team_series(items, D1, D2, 3, None)
        assert [d.suppressed for d in daily] == [True, False]
        assert (totals.completions, totals.suppressed_days) == (3, 1)

    def test_category_breakdown_respects_filter_and_range_level_k(self):
        members = {"a", "b", "c"}
        items = [
            day(
                D1,
                completions=5,
                active_users=members,
                cat_fitness=3,
                active_users_cat_fitness=members,
                cat_sleep=2,
                active_users_cat_sleep={"a"},
            )
        ]
        _, _, by_cat, suppressed = team_series(items, D1, D1, 3, None)
        assert [(c.category.value, c.completions) for c in by_cat] == [("fitness", 3)]
        assert [c.value for c in suppressed] == ["sleep"]
        _, _, by_cat, suppressed = team_series(items, D1, D1, 3, Category.FITNESS)
        assert [c.category.value for c in by_cat] == ["fitness"]
        assert suppressed == []
