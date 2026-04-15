"""Greedy spillover: next bracket, rank by lowest required remainder, cap at 100%."""

from __future__ import annotations

from dataclasses import dataclass

from gpa_planner.course import W_REM, CourseInput
from gpa_planner.gpa import max_achievable_gpa, weighted_gpa
from gpa_planner.scale import gpa_points, next_threshold_pct, normalize_level


@dataclass
class SpilloverStep:
    course_name: str
    bracket_target_pct: float
    x_required: float
    remainder_before: float
    remainder_after: float
    final_before: float
    final_after: float
    capped_at_100: bool


@dataclass
class SpilloverResult:
    courses: list[CourseInput]
    goal: float
    baseline_gpa: float
    final_gpa: float
    remainders: list[float]
    finals: list[float]
    steps: list[SpilloverStep]
    goal_reached: bool
    max_possible_gpa: float


def _finals_from_remainders(courses: list[CourseInput], X: list[float]) -> list[float]:
    return [c.final_from_remainder(x) for c, x in zip(courses, X, strict=True)]


def _optimizable(c: CourseInput) -> bool:
    return c.counts_for_gpa and not c.locked and c.fixed_final_pct is None


def run_spillover(
    courses: list[CourseInput],
    goal: float,
    *,
    eps: float = 1e-5,
    max_steps: int = 2000,
) -> SpilloverResult:
    if not courses:
        raise ValueError("need at least one course")
    X = [float(c.remainder_baseline) for c in courses]
    for c, x in zip(courses, X, strict=True):
        if not _optimizable(c):
            continue
        if x < 0 or x > 100:
            raise ValueError("remainder baseline must be in [0, 100]")

    max_gpa = max_achievable_gpa(courses)
    baseline_finals = _finals_from_remainders(courses, X)
    baseline_gpa = weighted_gpa(courses, baseline_finals)

    steps: list[SpilloverStep] = []

    for _ in range(max_steps):
        finals = _finals_from_remainders(courses, X)
        wgpa = weighted_gpa(courses, finals)
        if wgpa + eps >= goal:
            return SpilloverResult(
                courses=courses,
                goal=goal,
                baseline_gpa=baseline_gpa,
                final_gpa=wgpa,
                remainders=list(X),
                finals=finals,
                steps=steps,
                goal_reached=True,
                max_possible_gpa=max_gpa,
            )

        candidates: list[tuple[float, float, int, str]] = []
        for i, c in enumerate(courses):
            if not _optimizable(c):
                continue
            f = finals[i]
            T = next_threshold_pct(f)
            if T is None:
                continue
            S = c.completed_sum()
            x_req = (T - S) / W_REM
            x_cap = min(100.0, x_req)
            if x_cap <= X[i] + 1e-9:
                continue
            lvl = normalize_level(c.level)
            new_f = S + W_REM * x_cap
            if x_req <= 100 and gpa_points(lvl, new_f) <= gpa_points(lvl, f) + 1e-12:
                continue
            if x_req > 100 and X[i] >= 100 - 1e-9:
                continue
            candidates.append((x_req, -c.credits, i, c.name))

        if not candidates:
            finals = _finals_from_remainders(courses, X)
            return SpilloverResult(
                courses=courses,
                goal=goal,
                baseline_gpa=baseline_gpa,
                final_gpa=weighted_gpa(courses, finals),
                remainders=list(X),
                finals=finals,
                steps=steps,
                goal_reached=False,
                max_possible_gpa=max_gpa,
            )

        candidates.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
        _, __, i, ___ = candidates[0]
        c = courses[i]
        f = finals[i]
        T = next_threshold_pct(f)
        assert T is not None
        S = c.completed_sum()
        x_req = (T - S) / W_REM
        x_before = X[i]
        x_after = min(100.0, x_req)
        capped = x_req > 100.0
        final_after = S + W_REM * x_after
        steps.append(
            SpilloverStep(
                course_name=c.name,
                bracket_target_pct=T,
                x_required=x_req,
                remainder_before=x_before,
                remainder_after=x_after,
                final_before=f,
                final_after=final_after,
                capped_at_100=capped,
            )
        )
        X[i] = x_after

    finals = _finals_from_remainders(courses, X)
    return SpilloverResult(
        courses=courses,
        goal=goal,
        baseline_gpa=baseline_gpa,
        final_gpa=weighted_gpa(courses, finals),
        remainders=list(X),
        finals=finals,
        steps=steps,
        goal_reached=weighted_gpa(courses, finals) + eps >= goal,
        max_possible_gpa=max_gpa,
    )
