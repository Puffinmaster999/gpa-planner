"""
scale.py — GPA point conversion table.

Maps a course percentage to GPA points depending on course level (AP / Honors / CP).
These thresholds match the school's official weighted GPA scale.

Example:
  93%+ in AP  → 4.7 points
  90%+ in CP  → 3.5 points
  Below 65%   → 0.0 points (failing)
"""

from __future__ import annotations

from typing import Literal

# The three course levels the school uses
Level = Literal["AP", "Honors", "CP"]

# Each row is: (minimum %, (AP points, Honors points, CP points))
# Listed from highest to lowest — the first row your % qualifies for wins.
_ROWS: list[tuple[float, tuple[float, float, float]]] = [
    (98.0, (5.0, 4.5, 4.0)),
    (93.0, (4.7, 4.2, 3.7)),
    (90.0, (4.5, 4.0, 3.5)),
    (87.0, (4.3, 3.8, 3.3)),
    (83.0, (4.0, 3.5, 3.0)),
    (80.0, (3.7, 3.2, 2.7)),
    (77.0, (3.4, 2.9, 2.4)),
    (73.0, (3.0, 2.5, 2.0)),
    (70.0, (2.7, 2.2, 1.7)),
    (65.0, (2.0, 1.5, 1.0)),
    (0.0,  (0.0, 0.0, 0.0)),  # Failing / below 65
]

# Just the threshold percentages in ascending order (used to find the "next bracket up")
_THRESHOLDS_ASC: list[float] = sorted({r[0] for r in _ROWS if r[0] > 0}, reverse=False)


def normalize_level(level: str) -> Level:
    """
    Converts various spellings of course levels to the standard "AP", "Honors", or "CP".
    Raises ValueError if the level isn't recognized.
    """
    s = level.strip()
    low = s.lower()
    if low in ("ap", "a.p.", "advanced placement"):
        return "AP"
    if low in ("honors", "honor", "h", "hn"):
        return "Honors"
    if low in ("cp", "college prep", "c.p."):
        return "CP"
    raise ValueError(f"Unknown level: {level!r} (use AP, Honors, or CP)")


def _points_for_row(level: Level, row: tuple[float, float, float]) -> float:
    """Picks the right GPA points from a scale row based on course level."""
    if level == "AP":
        return row[0]
    if level == "Honors":
        return row[1]
    return row[2]  # CP


def gpa_points(level: Level | str, pct: float) -> float:
    """
    Returns the GPA points earned for a given course % and level.
    Scans the scale from top to bottom and returns the first row the % qualifies for.
    """
    if isinstance(level, str):
        level = normalize_level(level)
    for min_grade, trip in _ROWS:
        if pct >= min_grade:
            return _points_for_row(level, trip)
    return 0.0


def next_threshold_pct(current_final_pct: float) -> float | None:
    """
    Returns the next GPA bracket threshold above your current final %.
    For example: if you're at 91%, the next threshold is 93%.
    Returns None if you're already at the top bracket (98%+).
    """
    for t in _THRESHOLDS_ASC:
        if t > current_final_pct:
            return t
    return None


def next_gpa_points(level: Level | str, current_final_pct: float) -> float | None:
    """
    Returns the GPA points you'd earn if you just reached the next bracket threshold.
    Returns None if there's no higher bracket to reach.
    """
    t = next_threshold_pct(current_final_pct)
    if t is None:
        return None
    if isinstance(level, str):
        level = normalize_level(level)
    return gpa_points(level, t)
