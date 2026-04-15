"""
gpa.py — Weighted GPA calculations.

Three main functions:
  weighted_gpa         — calculates your current weighted GPA
  quality_point_deficit — how far you are from your goal in raw quality points
  max_achievable_gpa   — what's the best GPA you could possibly get
"""

from __future__ import annotations

from gpa_planner.course import CourseInput
from gpa_planner.scale import Level, gpa_points, normalize_level


def weighted_gpa(courses: list[CourseInput], finals: list[float]) -> float:
    """
    Calculates weighted GPA across all courses.

    Formula: sum(credits × GPA_points) / sum(credits)
    Only courses with counts_for_gpa=True are included.

    Args:
      courses — list of CourseInput objects
      finals  — list of final % for each course (same order as courses)
    """
    if len(courses) != len(finals):
        raise ValueError("courses and finals length mismatch")

    numerator = 0.0    # sum of (credits × GPA points)
    denominator = 0.0  # sum of credits

    for c, f in zip(courses, finals, strict=True):
        if not c.counts_for_gpa:
            continue
        lvl: Level = normalize_level(c.level)
        numerator += c.credits * gpa_points(lvl, f)
        denominator += c.credits

    if denominator <= 0:
        raise ValueError(
            "No courses count toward GPA. Set Level to AP, Honors, or CP and enter grades "
            "(or disable "Doesn't Count" / fill placeholder rows when you have data)."
        )

    return numerator / denominator


def quality_point_deficit(
    goal: float, courses: list[CourseInput], finals: list[float]
) -> float:
    """
    How many quality points you're short of your goal.
    Quality points = credits × GPA points for a single course.

    Formula: goal × total_credits − current_quality_points
    Positive result means you need more points to reach the goal.
    """
    total_credits = sum(c.credits for c in courses if c.counts_for_gpa)
    current_quality_points = sum(
        c.credits * gpa_points(normalize_level(c.level), f)
        for c, f in zip(courses, finals, strict=True)
        if c.counts_for_gpa
    )
    return goal * total_credits - current_quality_points


def max_achievable_gpa(courses: list[CourseInput]) -> float:
    """
    Calculates the highest possible GPA assuming you score 100% on Q4+F1
    in every course that still has grades ahead (i.e. not locked).

    Locked courses (year already complete) keep their actual grades.
    """
    finals: list[float] = []
    for c in courses:
        if not c.counts_for_gpa:
            finals.append(0.0)
        elif c.locked or c.fixed_final_pct is not None:
            # Year is already done — use the real grade
            finals.append(c.final_from_remainder(c.remainder_baseline))
        else:
            # Best case: 100% on everything remaining
            finals.append(c.final_from_remainder(100.0))

    return weighted_gpa(courses, finals)
