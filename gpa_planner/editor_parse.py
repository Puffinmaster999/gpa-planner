"""Parse Streamlit editor / import DataFrame rows into CourseInput models."""

from __future__ import annotations

import math

import pandas as pd

from gpa_planner.course import WQ, WE, W_REM, CourseInput, full_year_final_pct, semester_s1_final_pct, semester_s2_final_pct
from gpa_planner.scale import normalize_level


def _cell_float(row: pd.Series, key: str) -> float | None:
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
    s = level_raw.strip().lower()
    return "doesn" in s or "not count" in s


def _is_semester_s1(term_raw: object) -> bool:
    if term_raw is None or (isinstance(term_raw, float) and pd.isna(term_raw)):
        return False
    s = str(term_raw).strip().lower()
    return "semester" in s or s in {"s1", "sem", "half"}

def _is_semester_s2(term_raw: object) -> bool:
    if term_raw is None or (isinstance(term_raw, float) and pd.isna(term_raw)):
        return False
    s = str(term_raw).strip().lower()
    return "semester" in s or s in {"s2", "sem", "half"}


def _weighted_known_average(q1: float | None, q2: float | None, q3: float | None, e1: float | None) -> float | None:
    num = 0.0
    den = 0.0
    if q1 is not None:
        num += WQ * q1
        den += WQ
    if q2 is not None:
        num += WQ * q2
        den += WQ
    if q3 is not None:
        num += WQ * q3
        den += WQ
    if e1 is not None:
        num += WE * e1
        den += WE
    if den <= 0:
        return None
    return num / den


def parse_courses_from_dataframe(
    df: pd.DataFrame,
    baseline_mode: str,
) -> tuple[list[CourseInput], list[str]]:
    """Turn editor rows into courses. Placeholders and “Doesn’t Count” get counts_for_gpa=False."""
    errors: list[str] = []
    courses: list[CourseInput] = []

    for idx, r in df.iterrows():
        name = str(r.get("Class", "")).strip() or f"Row {idx}"
        level_cell = r.get("Level", "")
        if level_cell is None or (isinstance(level_cell, float) and pd.isna(level_cell)):
            level_str = ""
        else:
            level_str = str(level_cell).strip()

        doesnt = _is_doesnt_count(level_str) if level_str else False

        credits = _cell_float(r, "Credits")
        if credits is None or credits <= 0:
            errors.append(f"{name}: Credits must be a positive number.")
            continue
        is_semester_s1 = _is_semester_s1(r.get("Term", ""))
        is_semester_s2 = _is_semester_s2(r.get("Term", ""))

        q1, q2, q3 = _cell_float(r, "Q1 %"), _cell_float(r, "Q2 %"), _cell_float(r, "Q3 %")
        e1 = _cell_float(r, "E1 %")
        q4, f1 = _cell_float(r, "Q4 %"), _cell_float(r, "F1 %")
        rem_col = _cell_float(r, "Remainder %")
        course_pct = _cell_float(r, "Course %")

        has_any_core = any(x is not None for x in (q1, q2, q3, e1))
        has_core = all(x is not None for x in (q1, q2, q3, e1))
        full_year = has_core and all(x is not None for x in (q4, f1))

        if doesnt:
            courses.append(
                CourseInput(
                    name=name,
                    level="CP",
                    credits=credits,
                    q1=0.0,
                    q2=0.0,
                    q3=0.0,
                    e1=0.0,
                    remainder_baseline=0.0,
                    counts_for_gpa=False,
                    locked=True,
                )
            )
            continue

        if is_semester_s1:
            if not all(x is not None for x in (q1, q2, e1)):
                errors.append(f"{name}: Semester (S1) rows require Q1, Q2, and E1.")
                continue
            assert q1 is not None and q2 is not None and e1 is not None
            try:
                lvl = normalize_level(level_str if level_str else "CP")
            except ValueError as e:
                errors.append(f"{name}: {e}")
                continue
            for label, v in [("Q1", q1), ("Q2", q2), ("E1", e1)]:
                if v < 0 or v > 100:
                    errors.append(f"{name}: {label} must be 0–100.")
                    break
            else:
                s1_pct = semester_s1_final_pct(q1, q2, e1)
                courses.append(
                    CourseInput(
                        name=name,
                        level=lvl,
                        credits=credits,
                        q1=0.0,
                        q2=0.0,
                        q3=0.0,
                        e1=0.0,
                        remainder_baseline=0.0,
                        counts_for_gpa=True,
                        locked=True,
                        fixed_final_pct=s1_pct,
                    )
                )



            continue
        if is_semester_s2:
            if not all(x is not None for x in (q3, q4, f1)):
                errors.append(f"{name}: Semester (S2) rows require Q3, Q4, and F1.")
                continue
            assert q3 is not None and q4 is not None and f1 is not None
            try:
                lvl = normalize_level(level_str if level_str else "CP")
            except ValueError as e:
                errors.append(f"{name}: {e}")
                continue
            for label, v in [("Q3", q3), ("Q4", q4), ("F1", f1)]:
                if v < 0 or v > 100:
                    errors.append(f"{name}: {label} must be 0–100.")
                    break
            else:
                s2_pct = semester_s2_final_pct(q3, q4, f1)
                courses.append(
                    CourseInput(
                        name=name,
                        level=lvl,
                        credits=credits,
                        q1=0.0,
                        q2=0.0,
                        q3=0.0,
                        e1=0.0,
                        remainder_baseline=0.0,
                        counts_for_gpa=True,
                        locked=True,
                        fixed_final_pct=s2_pct,
                    )
                )
            continue

        if full_year:
            assert q1 is not None and q2 is not None and q3 is not None and e1 is not None
            assert q4 is not None and f1 is not None
            fy = full_year_final_pct(q1, q2, q3, q4, e1, f1)
            s72 = WQ * (q1 + q2 + q3) + WE * e1
            rem = (fy - s72) / W_REM
            try:
                lvl = normalize_level(level_str if level_str else "CP")
            except ValueError as e:
                errors.append(f"{name}: {e}")
                continue
            for label, v in [("Q1", q1), ("Q2", q2), ("Q3", q3), ("Q4", q4), ("E1", e1), ("F1", f1)]:
                if v < 0 or v > 100:
                    errors.append(f"{name}: {label} must be 0–100.")
                    break
            else:
                courses.append(
                    CourseInput(
                        name=name,
                        level=lvl,
                        credits=credits,
                        q1=q1,
                        q2=q2,
                        q3=q3,
                        e1=e1,
                        remainder_baseline=rem,
                        counts_for_gpa=True,
                        locked=True,
                    )
                )
            continue

        if has_any_core:
            try:
                lvl = normalize_level(level_str if level_str else "CP")
            except ValueError as e:
                errors.append(f"{name}: {e}")
                continue
            for label, v in [("Q1", q1), ("Q2", q2), ("Q3", q3), ("E1", e1)]:
                if v is not None and (v < 0 or v > 100):
                    errors.append(f"{name}: {label} must be 0–100.")
                    break
            else:
                inferred = _weighted_known_average(q1, q2, q3, e1)
                assert inferred is not None
                if baseline_mode == "avg_q":
                    rem = inferred
                else:
                    rem = rem_col if rem_col is not None else inferred
                if q4 is not None and (q4 < 0 or q4 > 100):
                    errors.append(f"{name}: Q4 must be 0–100.")
                    continue
                if f1 is not None and (f1 < 0 or f1 > 100):
                    errors.append(f"{name}: F1 must be 0–100.")
                    continue
                if rem < 0 or rem > 100:
                    errors.append(f"{name}: remainder must be 0–100.")
                    continue
                q1v = q1 if q1 is not None else rem
                q2v = q2 if q2 is not None else rem
                q3v = q3 if q3 is not None else rem
                e1v = e1 if e1 is not None else rem
                courses.append(
                    CourseInput(
                        name=name,
                        level=lvl,
                        credits=credits,
                        q1=q1v,
                        q2=q2v,
                        q3=q3v,
                        e1=e1v,
                        remainder_baseline=rem,
                        counts_for_gpa=True,
                        locked=False,
                    )
                )
            continue

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
                    name=name,
                    level=lvl,
                    credits=credits,
                    q1=0.0,
                    q2=0.0,
                    q3=0.0,
                    e1=0.0,
                    remainder_baseline=0.0,
                    counts_for_gpa=True,
                    locked=True,
                    fixed_final_pct=course_pct,
                )
            )
            continue

        courses.append(
            CourseInput(
                name=name,
                level="CP",
                credits=credits,
                q1=0.0,
                q2=0.0,
                q3=0.0,
                e1=0.0,
                remainder_baseline=0.0,
                counts_for_gpa=False,
                locked=True,
            )
        )

    return courses, errors
