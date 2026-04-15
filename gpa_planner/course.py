"""Single-course completed weight and final % from remainder average."""

from __future__ import annotations

from dataclasses import dataclass

WQ = 0.22
WE = 0.06
W_REM = 0.28  # Q4 + F1


def full_year_final_pct(q1: float, q2: float, q3: float, q4: float, e1: float, f1: float) -> float:
    """Course % when all terms and exams are known (matches typical year weights)."""
    return WQ * (q1 + q2 + q3 + q4) + WE * (e1 + f1)


@dataclass
class CourseInput:
    name: str
    level: str  # AP | Honors | CP (or any string if counts_for_gpa is False)
    credits: float
    q1: float
    q2: float
    q3: float
    e1: float
    remainder_baseline: float  # assumed Q4+F1 average for planning rows
    counts_for_gpa: bool = True
    locked: bool = False  # if True, remainder is not changed by spillover (e.g. year complete)
    fixed_final_pct: float | None = None  # if set, final % is always this (e.g. import "Grade #" only)

    def completed_sum(self) -> float:
        return WQ * self.q1 + WQ * self.q2 + WQ * self.q3 + WE * self.e1

    def final_from_remainder(self, x: float) -> float:
        if self.fixed_final_pct is not None:
            return self.fixed_final_pct
        return self.completed_sum() + W_REM * x
