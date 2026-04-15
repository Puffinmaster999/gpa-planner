"""
spillover.py — The optimization engine ("spillover" algorithm).

How it works:
  Your GPA is made up of brackets — e.g. scoring 87% gives more GPA points than 86%.
  This algorithm figures out which courses need the *smallest* bump in Q4+F1
  to jump to the next bracket, and applies those bumps one at a time until
  your GPA goal is reached. It always picks the easiest win first (greedy approach).

  "Spillover" = when one course's improvement isn't enough alone, we keep
  going course by course until the goal is hit.
"""

from __future__ import annotations

from dataclasses import dataclass

from gpa_planner.course import W_REM, CourseInput
from gpa_planner.gpa import max_achievable_gpa, weighted_gpa
from gpa_planner.scale import gpa_points, next_threshold_pct, normalize_level


@dataclass
class SpilloverStep:
    """
    Records what happened in one step of the optimization.
    Each step = one course getting its Q4+F1 target raised to hit the next bracket.
    """
    course_name: str
    bracket_target_pct: float   # The GPA bracket threshold we're aiming for (e.g. 87, 90, 93)
    x_required: float           # Q4+F1 average needed to hit that bracket
    remainder_before: float     # Q4+F1 assumption before this step
    remainder_after: float      # Q4+F1 assumption after this step
    final_before: float         # Projected final % before this step
    final_after: float          # Projected final % after this step
    capped_at_100: bool         # True if the required score exceeds 100 (gets capped)


@dataclass
class SpilloverResult:
    """The full output of the spillover run — everything the UI needs to display."""
    courses: list[CourseInput]
    goal: float
    baseline_gpa: float         # GPA before any optimization
    final_gpa: float            # GPA after optimization
    remainders: list[float]     # Final Q4+F1 targets per course
    finals: list[float]         # Final projected course % per course
    steps: list[SpilloverStep]  # The list of changes made
    goal_reached: bool
    max_possible_gpa: float


def _finals_from_remainders(courses: list[CourseInput], X: list[float]) -> list[float]:
    """Helper: compute final % for every course given the current Q4+F1 assumptions."""
    return [c.final_from_remainder(x) for c, x in zip(courses, X, strict=True)]


def _optimizable(c: CourseInput) -> bool:
    """
    Returns True if this course can still be improved by the algorithm.
    A course is NOT optimizable if:
      - it doesn't count toward GPA
      - it's locked (year already complete)
      - it has a fixed final % (imported Grade # override)
    """
    return c.counts_for_gpa and not c.locked and c.fixed_final_pct is None


def run_spillover(
    courses: list[CourseInput],
    goal: float,
    *,
    eps: float = 1e-5,      # Small tolerance to avoid floating point issues
    max_steps: int = 2000,  # Safety cap so we never loop forever
) -> SpilloverResult:
    """
    Runs the greedy spillover optimization.

    Starting from the baseline Q4+F1 assumptions, repeatedly finds the course
    that needs the smallest Q4+F1 improvement to jump a GPA bracket, applies it,
    and checks if the GPA goal is now met. Stops when goal is reached or no
    more improvements are possible.
    """
    if not courses:
        raise ValueError("need at least one course")

    # X = current Q4+F1 assumption for each course (starts at baseline)
    X = [float(c.remainder_baseline) for c in courses]

    # Validate all baselines are in range
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

        # ✅ Goal reached — return the result
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

        # Find all courses that can be improved and calculate the cost of improvement
        candidates: list[tuple[float, float, int, str]] = []
        for i, c in enumerate(courses):
            if not _optimizable(c):
                continue

            f = finals[i]
            T = next_threshold_pct(f)   # Next GPA bracket threshold above current %
            if T is None:
                continue  # Already at the top bracket

            S = c.completed_sum()
            x_req = (T - S) / W_REM    # Q4+F1 average required to hit bracket T
            x_cap = min(100.0, x_req)  # Can't go above 100%

            # Skip if we're already at or above this target
            if x_cap <= X[i] + 1e-9:
                continue

            # Skip if hitting the bracket wouldn't actually improve GPA points
            lvl = normalize_level(c.level)
            new_f = S + W_REM * x_cap
            if x_req <= 100 and gpa_points(lvl, new_f) <= gpa_points(lvl, f) + 1e-12:
                continue

            # Skip if we'd need >100% and we're already at 100
            if x_req > 100 and X[i] >= 100 - 1e-9:
                continue

            # Sort key: lowest x_req first (easiest win), then highest credits (most impact)
            candidates.append((x_req, -c.credits, i, c.name))

        # No more improvements possible
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

        # Pick the easiest improvement (lowest Q4+F1 required)
        candidates.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
        _, __, i, ___ = candidates[0]

        # Apply the improvement to course i
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

    # Hit the max_steps limit without reaching goal
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
