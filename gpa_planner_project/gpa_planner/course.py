"""
course.py — Defines a single course and how its final % is calculated.

Grade weights used by this school:
  - Each quarter (Q1, Q2, Q3, Q4) = 22% of the final grade
  - Each exam (E1 = midterm, F1 = final exam) = 6% of the final grade
  - Q1 + Q2 + Q3 + E1 = 72%  →  the "completed" portion
  - Q4 + F1 = 28%             →  the "remainder" we're planning for
"""

from __future__ import annotations

from dataclasses import dataclass

# Individual weights for each graded component
WQ = 0.22       # Weight of each quarter grade (Q1, Q2, Q3, Q4)
WE = 0.06       # Weight of each exam (E1 midterm, F1 final exam)
W_REM = 0.28    # Combined weight of Q4 + F1 (the part still ahead of you)


def full_year_final_pct(
    q1: float, q2: float, q3: float, q4: float, e1: float, f1: float
) -> float:
    """
    Calculates your final course % when all grades are known.
    Formula: 22%(Q1+Q2+Q3+Q4) + 6%(E1+F1)
    """
    return WQ * (q1 + q2 + q3 + q4) + WE * (e1 + f1)


@dataclass
class CourseInput:
    """
    Holds all the data for one course.

    Fields:
      name             — e.g. "AP Biology"
      level            — "AP", "Honors", or "CP" (affects GPA point scale)
      credits          — how many credits this class is worth (usually 5)
      q1–q3, e1        — completed grades (the 72% portion)
      remainder_baseline — assumed average for Q4+F1 used before optimization
      counts_for_gpa   — False for "Doesn't Count" or placeholder rows
      locked           — True if Q4+F1 are already graded (can't be changed)
      fixed_final_pct  — set this if we only know the overall course % (e.g. from Grade #)
    """
    name: str
    level: str
    credits: float
    q1: float
    q2: float
    q3: float
    e1: float
    remainder_baseline: float
    counts_for_gpa: bool = True
    locked: bool = False
    fixed_final_pct: float | None = None

    def completed_sum(self) -> float:
        """
        Returns the weighted sum of the grades you already have.
        This is the part of your final % that's already locked in.
        e.g. 0.22*Q1 + 0.22*Q2 + 0.22*Q3 + 0.06*E1
        """
        return WQ * self.q1 + WQ * self.q2 + WQ * self.q3 + WE * self.e1

    def final_from_remainder(self, x: float) -> float:
        """
        Calculates your projected final course % given an assumed Q4+F1 average (x).
        If a fixed final % was provided (e.g. imported from Grade #), returns that instead.
        """
        if self.fixed_final_pct is not None:
            return self.fixed_final_pct
        return self.completed_sum() + W_REM * x
