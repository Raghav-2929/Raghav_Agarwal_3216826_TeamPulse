from __future__ import annotations

from datetime import date, timedelta

import pytest

from streak_processor.streaks import (
    HISTORY_LIMIT,
    StreakResult,
    compute_streak,
    crossed_milestones,
    current_run_start,
    is_alive,
    merge_history,
    milestones_to_announce,
    period_key,
    period_start,
    previous_period,
)
from teampulse_common.events.contracts import Frequency

D, W = Frequency.DAILY, Frequency.WEEKLY
NOV = date(2026, 11, 2)  # a Monday


def days(*offsets: int) -> list[date]:
    return [NOV + timedelta(days=o) for o in offsets]


class TestPeriods:
    def test_daily_key_is_iso_date(self):
        assert period_key(date(2026, 11, 8), D) == "2026-11-08"

    def test_weekly_key_is_zero_padded_iso_week(self):
        assert period_key(date(2026, 3, 2), W) == "2026-W10"
        assert period_key(date(2026, 1, 5), W) == "2026-W02"

    def test_weekly_key_uses_iso_year_at_boundary(self):
        assert period_key(date(2027, 1, 1), W) == "2026-W53"  # Friday 1 Jan 2027 belongs to 2026-W53
        assert period_key(date(2026, 1, 1), W) == "2026-W01"

    def test_period_start(self):
        assert period_start("2026-W45", W) == date(2026, 11, 2)
        assert period_start("2026-11-08", D) == date(2026, 11, 8)

    @pytest.mark.parametrize(
        ("key", "freq", "expected"),
        [
            ("2026-11-01", D, "2026-10-31"),
            ("2026-03-01", D, "2026-02-28"),
            ("2026-W45", W, "2026-W44"),
            ("2027-W01", W, "2026-W53"),
            ("2026-W01", W, "2025-W52"),
        ],
    )
    def test_previous_period(self, key, freq, expected):
        assert previous_period(key, freq) == expected


class TestComputeStreak:
    def test_no_history(self):
        assert compute_streak([], D) == StreakResult(0, 0, None)

    def test_single_day(self):
        assert compute_streak(days(0), D) == StreakResult(1, 1, "2026-11-02")

    def test_consecutive_days(self):
        assert compute_streak(days(0, 1, 2, 3), D) == StreakResult(4, 4, "2026-11-05")

    def test_gap_resets_current_but_keeps_longest(self):
        result = compute_streak(days(0, 1, 2, 5, 6), D)
        assert (result.current, result.longest, result.last_period) == (2, 3, "2026-11-08")

    def test_order_and_duplicates_do_not_matter(self):
        assert compute_streak(days(2, 0, 1, 1, 0), D) == compute_streak(days(0, 1, 2), D)

    def test_backfill_bridging_a_gap_joins_the_runs(self):
        assert compute_streak(days(0, 1, 3, 4), D).current == 2
        assert compute_streak(days(0, 1, 2, 3, 4), D).current == 5

    def test_longest_run_in_the_middle(self):
        result = compute_streak(days(0, 2, 3, 4, 5, 7), D)
        assert (result.current, result.longest) == (1, 4)

    def test_weekly_target_must_be_met_each_week(self):
        week1 = days(0, 2, 4)  # 3 completions in W45 → met
        week2 = days(7, 8)  # 2 completions in W46 → not met for target 3
        week3 = days(14, 15, 16)  # met
        result = compute_streak(week1 + week2 + week3, W, target=3)
        assert (result.current, result.longest, result.last_period) == (1, 1, "2026-W47")

    def test_weekly_consecutive_weeks(self):
        dates = days(0, 1, 7, 8, 14, 15)
        assert compute_streak(dates, W, target=2) == StreakResult(3, 3, "2026-W47")

    def test_weekly_target_one_counts_any_completion(self):
        assert compute_streak(days(6, 7), W, target=1).current == 2  # Sunday W45 + Monday W46

    def test_same_week_completions_count_once_per_day(self):
        assert compute_streak(days(0, 0, 0), W, target=2).current == 0


class TestAliveness:
    today = date(2026, 11, 8)

    @pytest.mark.parametrize(
        ("last", "alive"),
        [
            ("2026-11-09", True),  # employee east of UTC already on "tomorrow" (found in IST smoke test)
            ("2026-11-08", True),
            ("2026-11-07", True),
            ("2026-11-06", False),
            (None, False),
        ],
    )
    def test_daily(self, last, alive):
        assert is_alive(last, D, self.today) is alive

    @pytest.mark.parametrize(
        ("last", "alive"), [("2026-W46", True), ("2026-W45", True), ("2026-W44", True), ("2026-W43", False)]
    )
    def test_weekly(self, last, alive):
        assert is_alive(last, W, self.today) is alive


class TestMilestones:
    @pytest.mark.parametrize(
        ("before", "after", "expected"),
        [
            (2, 3, [3]),
            (3, 3, []),
            (3, 4, []),
            (6, 8, [7]),
            (0, 1, []),
            (0, 7, [3, 7]),
            (29, 30, [30]),
            (100, 99, []),
        ],
    )
    def test_only_newly_crossed_thresholds(self, before, after, expected):
        assert crossed_milestones(before, after) == expected

    def test_milestone_schedule_from_the_product_spec(self):
        # Celebrated streak lengths (spec: 3 days, 1/2/3 weeks, 30/60/100 days, one year).
        assert crossed_milestones(0, 1000) == [3, 7, 14, 21, 30, 60, 100, 365]

    @pytest.mark.parametrize("m", [14, 21, 60, 100, 365])
    def test_each_milestone_fires_exactly_at_its_threshold(self, m):
        assert crossed_milestones(m - 1, m) == [m]
        assert crossed_milestones(m, m + 1) == []

    def test_run_start_is_the_first_period_of_the_latest_run(self):
        assert current_run_start([], D) is None
        assert current_run_start(days(0, 1, 2, 5, 6), D) == "2026-11-07"
        assert current_run_start(days(0, 1, 2, 3, 4, 5, 6), D) == "2026-11-02"  # gap filled: one run
        assert current_run_start(days(0, 1, 7, 8), W, target=2) == "2026-W45"

    def test_milestone_already_announced_for_a_joined_run_is_not_repeated(self):
        # 3 was announced for the run that began on 2 Nov; a back-fill joins it to a later run.
        assert milestones_to_announce(2, 7, "2026-11-02", {"3": "2026-11-02"}) == [7]

    def test_milestone_from_an_older_separate_run_is_announced_again(self):
        assert milestones_to_announce(2, 3, "2026-11-07", {"3": "2026-11-02"}) == [3]

    def test_nothing_announced_before_means_plain_crossing(self):
        assert milestones_to_announce(0, 7, "2026-11-02", {}) == [3, 7]


class TestHistory:
    def test_merge_dedupes_and_sorts(self):
        assert merge_history(["2026-11-03", "2026-11-01"], date(2026, 11, 3)) == ["2026-11-01", "2026-11-03"]

    def test_merge_adds_new_day(self):
        assert merge_history([], date(2026, 11, 3)) == ["2026-11-03"]

    def test_merge_is_bounded_keeping_most_recent(self):
        assert HISTORY_LIMIT == 400  # spec: more than a year of daily history is retained
        history = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(400)]
        merged = merge_history(history, date(2026, 12, 31))
        assert len(merged) == 400
        assert merged[-1] == "2026-12-31"
        assert merged[0] == "2025-01-02"
