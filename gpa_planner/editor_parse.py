"""
editor_parse.py — Converts the Streamlit table rows into CourseInput objects.

When you fill out the class table and hit "Calculate", this file reads
each row and figures out what kind of course it is:

  1. "Doesn't Count" level       → skipped for GPA
  2. Full year (Q1–Q4 + E1 + F1) → locked, grade is final
  3. Partial year (Q1–Q3 + E1)   → planning mode, Q4+F1 still ahead
  4. Course % only               → locked, using a single imported grade
  5. No grades at all            → placeholder, skipped for GPA
"""

from __future__ import annotations

import math

import pandas as pd

from gpa_planner.course import WQ, WE, W_REM, CourseInput, full_year_final_pct
from gpa_planner.scale import normalize_level


def _cell_float(row: pd.Series, key: str) -> float | None:
    """
    Safely reads a cell from a DataFrame row as a float.
    Returns None if the cell is missing, empty, or not a valid number.
    """
    if key not in row:
        return None
    v = row[key]
    if v is None or (isinstance(v, float) and (math.isnan(v) or pd.isna(v))):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(x):
        return None
    return x


def _is_doesnt_count(level_raw: str) -> bool:
    """Returns True if the level cell says this class shouldn't count toward GPA."""
    s = level_raw.strip().lower()
    return "doesn" in s or "not count" in s


def parse_courses_from_dataframe(
    df: pd.DataFrame,
    baseline_mode: str,
) -> tuple[list[CourseInput], list[str]]:
    """
    Reads all rows from the class table and converts them to CourseInput objects.

    Args:
      df            — the DataFrame from the Streamlit editor
      baseline_mode — "avg_q" to use average of Q1–Q3 as the Q4+F1 baseline,
                      "column" to use the "Remainder %" column instead

    Returns:
      (courses, errors) — list of parsed courses and any validation error messages
    """
    errors: list[str] = []
    courses: list[CourseInput] = []

    for idx, r in df.iterrows():
        name = str(r.get("Class", "")).strip() or f"Row {idx}"

        # Read and normalize the level cell
        level_cell = r.get("Level", "")
        if level_cell is None or (isinstance(level_cell, float) and pd.isna(level_cell)):
            level_str = ""
        else:
            level_str = str(level_cell).strip()

        doesnt = _is_doesnt_count(level_str) if level_str else False

        # Credits are required for every row
        credits = _cell_float(r, "Credits")
        if credits is None or credits <= 0:
            errors.append(f"{name}: Credits must be a positive number.")
            continue

        # Read all grade cells (any can be None if not yet entered)
        q1, q2, q3 = _cell_float(r, "Q1 %"), _cell_float(r, "Q2 %"), _cell_float(r, "Q3 %")
        e1 = _cell_float(r, "E1 %")
        q4, f1 = _cell_float(r, "Q4 %"), _cell_float(r, "F1 %")
        rem_col = _cell_float(r, "Remainder %")
        course_pct = _cell_float(r, "Course %")

        has_core = all(x is not None for x in (q1, q2, q3, e1))   # Q1–Q3 + E1 all filled
        full_year = has_core and all(x is not None for x in (q4, f1))  # All 6 grades filled

        # ── Case 1: Doesn't Count ─────────────────────────────────────────────
        if doesnt:
            courses.append(
                CourseInput(
                    name=name, level="CP", credits=credits,
                    q1=0.0, q2=0.0, q3=0.0, e1=0.0,
                    remainder_baseline=0.0,
                    counts_for_gpa=False, locked=True,
                )
            )
            continue

        # ── Case 2: Full year complete (Q1–Q4 + E1 + F1 all entered) ─────────
        if full_year:
            assert q1 is not None and q2 is not None and q3 is not None and e1 is not None
            assert q4 is not None and f1 is not None

            fy = full_year_final_pct(q1, q2, q3, q4, e1, f1)
            s72 = WQ * (q1 + q2 + q3) + WE * e1
            rem = (fy - s72) / W_REM  # Back-calculate effective remainder for consistency

            try:
                lvl = normalize_level(level_str if level_str else "CP")
            except ValueError as e:
                errors.append(f"{name}: {e}")
                continue

            # Validate all grades are in range
            for label, v in [("Q1", q1), ("Q2", q2), ("Q3", q3), ("Q4", q4), ("E1", e1), ("F1", f1)]:
                if v < 0 or v > 100:
                    errors.append(f"{name}: {label} must be 0–100.")
                    break
            else:
                courses.append(
                    CourseInput(
                        name=name, level=lvl, credits=credits,
                        q1=q1, q2=q2, q3=q3, e1=e1,
                        remainder_baseline=rem,
                        counts_for_gpa=True, locked=True,  # Locked: year is done
                    )
                )
            continue

        # ── Case 3: Partial year (Q1–Q3 + E1 entered, Q4/F1 still ahead) ─────
        if has_core:
            assert q1 is not None and q2 is not None and q3 is not None and e1 is not None

            try:
                lvl = normalize_level(level_str if level_str else "CP")
            except ValueError as e:
                errors.append(f"{name}: {e}")
                continue

            for label, v in [("Q1", q1), ("Q2", q2), ("Q3", q3), ("E1", e1)]:
                if v < 0 or v > 100:
                    errors.append(f"{name}: {label} must be 0–100.")
                    break
            else:
                # Set the baseline remainder based on user's chosen mode
                if baseline_mode == "avg_q":
                    rem = (q1 + q2 + q3) / 3.0   # Assume Q4+F1 avg ≈ avg of past quarters
                else:
                    if rem_col is None:
                        errors.append(f"{name}: set Remainder % or use average-of-quarters baseline.")
                        continue
                    rem = rem_col

                # Validate optional Q4 / F1 if partially entered
                if q4 is not None and (q4 < 0 or q4 > 100):
                    errors.append(f"{name}: Q4 must be 0–100.")
                    continue
                if f1 is not None and (f1 < 0 or f1 > 100):
                    errors.append(f"{name}: F1 must be 0–100.")
                    continue
                if rem < 0 or rem > 100:
                    errors.append(f"{name}: remainder must be 0–100.")
                    continue

                courses.append(
                    CourseInput(
                        name=name, level=lvl, credits=credits,
                        q1=q1, q2=q2, q3=q3, e1=e1,
                        remainder_baseline=rem,
                        counts_for_gpa=True, locked=False,  # Not locked: can still be optimized
                    )
                )
            continue

        # ── Case 4: Only Course % is known (e.g. imported "Grade #") ──────────
        if course_pct is not None:
            if course_pct < 0 or course_pct > 100:
                errors.append(f"{name}: Course % must be 0–100.")
                continue
            try:
                lvl = normalize_level(level_str if level_str else "CP")
            except ValueError as e:
                errors.append(f"{name}: {e}")
                continue
            courses.append(
                CourseInput(
                    name=name, level=lvl, credits=credits,
                    q1=0.0, q2=0.0, q3=0.0, e1=0.0,
                    remainder_baseline=0.0,
                    counts_for_gpa=True, locked=True,
                    fixed_final_pct=course_pct,   # Use this % directly, skip normal math
                )
            )
            continue

        # ── Case 5: No grades at all — placeholder row ────────────────────────
        courses.append(
            CourseInput(
                name=name, level="CP", credits=credits,
                q1=0.0, q2=0.0, q3=0.0, e1=0.0,
                remainder_baseline=0.0,
                counts_for_gpa=False, locked=True,  # Can't calculate GPA without grades
            )
        )

    return courses, errors
