"""Weighted GPA from course finals and credits."""

from __future__ import annotations

from gpa_planner.course import CourseInput
from gpa_planner.scale import Level, gpa_points, normalize_level


def weighted_gpa(
    courses: list[CourseInput],
    finals: list[float],
) -> float:
    if len(courses) != len(finals):
        raise ValueError("courses and finals length mismatch")
    num = 0.0
    den = 0.0
    for c, f in zip(courses, finals, strict=True):
        if not c.counts_for_gpa:
            continue
        lvl: Level = normalize_level(c.level)
        num += c.credits * gpa_points(lvl, f)
        den += c.credits
    if den <= 0:
        raise ValueError(
            "No courses count toward GPA. Set Type to AP, Honors, or CP and enter grades "
            "(or disable “Doesn’t Count” / fill placeholder rows when you have data)."
        )
    return num / den


def quality_point_deficit(goal: float, courses: list[CourseInput], finals: list[float]) -> float:
    """goal * sum(credits) - sum(credits * points). Positive => need more quality points."""
    total_c = sum(c.credits for c in courses if c.counts_for_gpa)
    qp = sum(
        c.credits * gpa_points(normalize_level(c.level), f)
        for c, f in zip(courses, finals, strict=True)
        if c.counts_for_gpa
    )
    return goal * total_c - qp


def max_achievable_gpa(courses: list[CourseInput]) -> float:
    """Weighted GPA if every unlocked planning course gets 100% on the remaining 28%."""
    finals: list[float] = []
    for c in courses:
        if not c.counts_for_gpa:
            finals.append(0.0)
        elif c.locked or c.fixed_final_pct is not None:
            finals.append(c.final_from_remainder(c.remainder_baseline))
        else:
            finals.append(c.final_from_remainder(100.0))
    return weighted_gpa(courses, finals)
