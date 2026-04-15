"""Grading scale: min course % -> GPA points (AP / Honors / CP)."""

from __future__ import annotations

from typing import Literal

Level = Literal["AP", "Honors", "CP"]

# Descending min_grade thresholds from the "Math" tab (PDF).
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
    (0.0, (0.0, 0.0, 0.0)),
]

_THRESHOLDS_ASC: list[float] = sorted({r[0] for r in _ROWS if r[0] > 0}, reverse=False)


def normalize_level(level: str) -> Level:
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
    if level == "AP":
        return row[0]
    if level == "Honors":
        return row[1]
    return row[2]


def gpa_points(level: Level | str, pct: float) -> float:
    """GPA points for course percentage: highest threshold <= pct."""
    if isinstance(level, str):
        level = normalize_level(level)
    for min_grade, trip in _ROWS:
        if pct >= min_grade:
            return _points_for_row(level, trip)
    return 0.0


def next_threshold_pct(current_final_pct: float) -> float | None:
    """Smallest scale cutoff strictly above current final % (next 'bracket up' in %)."""
    for t in _THRESHOLDS_ASC:
        if t > current_final_pct:
            return t
    return None


def next_gpa_points(level: Level | str, current_final_pct: float) -> float | None:
    """GPA points if final were exactly at next_threshold_pct (None if no higher % bracket)."""
    t = next_threshold_pct(current_final_pct)
    if t is None:
        return None
    if isinstance(level, str):
        level = normalize_level(level)
    return gpa_points(level, t)
