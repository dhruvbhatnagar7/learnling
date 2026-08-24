"""Oral reading fluency against the Hasbrouck & Tindal (2017) norms."""

from __future__ import annotations

import pytest

from learnling.fluency import (
    FLUENCY_SUPPORT_THRESHOLD_WCPM,
    NormsUnavailable,
    Season,
    assess_fluency,
    citation,
    compute_wcpm,
    needs_fluency_support,
    norms_for,
    percentile_band,
)

# --- The norms table itself -------------------------------------------------


def test_grade_1_has_no_fall_norm():
    """The trap this table is famous for.

    Grade 1 students are not reading connected text in the fall, so no norm
    exists. Several web renderings shift grade 1 left a column and invent a
    Fall row from the Winter values. Refusing is correct; defaulting would
    manufacture a number the source does not contain.
    """
    with pytest.raises(NormsUnavailable):
        norms_for(1, Season.FALL)


def test_grade_1_reference_values_are_not_shifted():
    """The two values that expose a left-shifted transcription."""
    assert norms_for(1, Season.WINTER)[50] == 29
    assert norms_for(1, Season.SPRING)[50] == 60


def test_grade_1_winter_and_spring_are_fully_populated():
    for season in (Season.WINTER, Season.SPRING):
        cutoffs = norms_for(1, season)
        assert sorted(cutoffs) == [10, 25, 50, 75, 90]


@pytest.mark.parametrize("grade", [1, 2, 3, 4, 5, 6])
@pytest.mark.parametrize("season", list(Season))
def test_percentiles_are_ordered_within_every_published_cell(grade, season):
    """A transposed row would almost certainly break monotonicity."""
    if grade == 1 and season is Season.FALL:
        pytest.skip("no published norm")
    cutoffs = norms_for(grade, season)
    values = [cutoffs[p] for p in (10, 25, 50, 75, 90)]
    assert values == sorted(values)


def test_norms_generally_increase_across_the_year():
    """Within a grade, the 50th percentile should not go backwards."""
    for grade in range(2, 7):
        fall = norms_for(grade, Season.FALL)[50]
        winter = norms_for(grade, Season.WINTER)[50]
        spring = norms_for(grade, Season.SPRING)[50]
        assert fall <= winter <= spring


def test_grades_outside_the_table_are_refused():
    with pytest.raises(NormsUnavailable):
        norms_for(7, Season.FALL)


def test_citation_is_available_for_reports():
    text = citation()
    assert "Hasbrouck" in text and "Tindal" in text and "2017" in text


# --- WCPM computation -------------------------------------------------------


def test_wcpm_subtracts_errors_and_scales_to_a_minute():
    # 100 words, 10 errors, 60 seconds -> 90 wcpm
    assert compute_wcpm(100, 10, 60) == 90


def test_wcpm_scales_a_partial_minute():
    # 60 correct words in 30 seconds is a 120 wcpm pace
    assert compute_wcpm(65, 5, 30) == 120


def test_wcpm_never_goes_negative():
    assert compute_wcpm(10, 50, 60) == 0


def test_wcpm_requires_positive_elapsed_time():
    with pytest.raises(ValueError):
        compute_wcpm(100, 0, 0)


# --- Banding ----------------------------------------------------------------


def test_bands_across_a_known_column():
    """Grade 2 spring: 10th=43, 25th=72, 50th=100, 75th=124, 90th=148."""
    grade, season = 2, Season.SPRING
    assert percentile_band(30, grade, season) == "below 10th"
    assert percentile_band(50, grade, season) == "10th-25th"
    assert percentile_band(80, grade, season) == "25th-50th"
    assert percentile_band(110, grade, season) == "50th-75th"
    assert percentile_band(130, grade, season) == "75th-90th"
    assert percentile_band(200, grade, season) == "above 90th"


def test_band_boundaries_are_inclusive_at_the_cutoff():
    """Landing exactly on a cutoff counts as reaching that band."""
    cutoffs = norms_for(2, Season.SPRING)
    assert percentile_band(cutoffs[50], 2, Season.SPRING) == "50th-75th"
    assert percentile_band(cutoffs[90], 2, Season.SPRING) == "above 90th"


# --- needs_fluency_support --------------------------------------------------


def test_one_reading_is_never_enough_to_flag_support():
    """The rule is defined over two unpracticed readings. One is a day."""
    # far below the grade 2 spring 50th (100), but still only one reading
    verdict, note = needs_fluency_support([40], 2, Season.SPRING)
    assert verdict is False
    assert "required" in note


def test_ten_or_more_below_the_50th_over_two_readings_flags_support():
    # grade 2 spring 50th = 100; average 88 is 12 below
    verdict, _ = needs_fluency_support([86, 90], 2, Season.SPRING)
    assert verdict is True


def test_just_inside_the_threshold_does_not_flag():
    # average 91 is 9 below the 50th of 100 — under the published threshold
    verdict, _ = needs_fluency_support([90, 92], 2, Season.SPRING)
    assert verdict is False


def test_exactly_ten_below_flags_support():
    """'10 or more words below' includes 10."""
    cutoffs = norms_for(2, Season.SPRING)
    target = cutoffs[50] - FLUENCY_SUPPORT_THRESHOLD_WCPM
    verdict, _ = needs_fluency_support([target, target], 2, Season.SPRING)
    assert verdict is True


def test_a_strong_reader_is_not_flagged():
    verdict, _ = needs_fluency_support([130, 140], 2, Season.SPRING)
    assert verdict is False


# --- assess_fluency end to end ---------------------------------------------


def test_assess_reports_accuracy_alongside_rate():
    """Rate alone hides the reader guessing their way through a page fast."""
    result = assess_fluency(
        total_words_read=100,
        uncorrected_errors=10,
        elapsed_seconds=60,
        skill_grade=2,
        season=Season.SPRING,
    )
    assert result.wcpm == 90
    assert result.accuracy_pct == 90.0


def test_assess_bands_against_the_passage_grade_not_the_learners_age():
    """A 12-year-old on grade-2 material is measured against grade-2 norms."""
    result = assess_fluency(
        total_words_read=100,
        uncorrected_errors=10,
        elapsed_seconds=60,
        skill_grade=2,
        season=Season.SPRING,
    )
    assert result.skill_grade == 2
    assert result.percentile_band == "25th-50th"


def test_assess_withholds_a_support_verdict_on_a_single_reading():
    result = assess_fluency(
        total_words_read=50,
        uncorrected_errors=10,
        elapsed_seconds=60,
        skill_grade=2,
        season=Season.SPRING,
    )
    assert result.needs_fluency_support is False
    assert result.readings_counted == 1
    assert "required" in result.readings_note


def test_assess_uses_prior_readings_to_reach_a_verdict():
    result = assess_fluency(
        total_words_read=90,
        uncorrected_errors=0,
        elapsed_seconds=60,
        skill_grade=2,
        season=Season.SPRING,
        prior_unpracticed_wcpm=[86],
    )
    assert result.readings_counted == 2
    assert result.needs_fluency_support is True


def test_high_rate_with_low_accuracy_is_not_reported_as_fluent():
    """The reader this guards against: fast, inaccurate, and easy to miss."""
    # 250 words attempted, 90 wrong -> 160 WCPM, above the grade 2 spring
    # 90th percentile of 148, on 64% accuracy.
    result = assess_fluency(
        total_words_read=250,
        uncorrected_errors=90,
        elapsed_seconds=60,
        skill_grade=2,
        season=Season.SPRING,
    )
    assert result.percentile_band == "above 90th"  # rate alone looks excellent
    assert result.accuracy_pct == 64.0  # accuracy tells the real story


def test_a_grade_1_fall_assessment_is_refused_rather_than_defaulted():
    with pytest.raises(NormsUnavailable):
        assess_fluency(
            total_words_read=40,
            uncorrected_errors=2,
            elapsed_seconds=60,
            skill_grade=1,
            season=Season.FALL,
        )
