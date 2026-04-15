"""
sheet_import.py — Imports a Google Sheets CSV/Excel export into the app's table format.

This lets you export your grade sheet from Google Sheets and upload it directly
instead of typing everything in manually.

It's flexible with column names — "Quarter 1", "Q1", and "q1" all work.
Empty cells and "FALSE" values (common in Google Sheets) are treated as blank.
"""

from __future__ import annotations

import io
import math
import re
from typing import Any

import pandas as pd

# The column names the Streamlit editor expects (must match app.py exactly)
EDITOR_COLUMNS = [
    "Grade", "Class", "Level", "Credits",
    "Q1 %", "Q2 %", "Q3 %", "E1 %",
    "Q4 %", "F1 %", "Course %", "Remainder %",
]


def _norm_header(h: str) -> str:
    """Normalizes a column header to lowercase with single spaces for flexible matching."""
    s = str(h).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _alias_map() -> dict[str, str]:
    """
    Maps all recognized column name variations → internal key name.
    This is what allows "Quarter 1", "Q1", "q1" etc. to all work.
    """
    m: dict[str, str] = {}
    for key, aliases in [
        ("grade",     ["grade", "yr", "year"]),
        ("class",     ["class", "course", "course name", "subject"]),
        ("q1",        ["q1", "quarter 1"]),
        ("q2",        ["q2", "q 2", "quarter 2"]),
        ("e1",        ["e1", "midterm", "mid year", "midyear", "exam 1"]),
        ("q3",        ["q3", "q 3", "quarter 3"]),
        ("q4",        ["q4", "q 4", "quarter 4"]),
        ("f1",        ["f1", "f 1", "final", "final exam"]),
        ("type",      ["type", "level", "course type"]),
        ("weight",    ["weight", "credits", "credit", "cr"]),
        ("grade_num", ["grade #", "grade#", "course %", "avg", "average", "numerical grade", "grade pct"]),
    ]:
        for a in aliases:
            m[_norm_header(a)] = key
    return m


def coerce_grade_value(raw: Any) -> float | None:
    """
    Converts a raw spreadsheet cell into a usable float (0–100) or None.
    Handles: blank cells, Google Sheets "FALSE", "#N/A", % signs, etc.
    """
    if raw is None or (isinstance(raw, float) and (math.isnan(raw) or pd.isna(raw))):
        return None
    if isinstance(raw, bool):
        return None   # Google Sheets exports missing grades as FALSE sometimes
    if isinstance(raw, str):
        s = raw.strip()
        if not s or s.upper() in ("FALSE", "TRUE", "#N/A", "N/A", "NA", "-", "—"):
            return None
        s = s.replace("%", "")
        try:
            v = float(s)
        except ValueError:
            return None
    else:
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return None
    if math.isnan(v):
        return None
    return v


def normalize_type_for_editor(raw: Any) -> str:
    """
    Maps the "Type" column from Google Sheets to the editor's Level values.
    e.g. "Advanced Placement" → "AP", "Hon" → "Honors", "Doesn't Count" → "Doesn't Count"
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    low = s.lower()
    if "doesn" in low or "not count" in low or low in ("n/a", "na", "-"):
        return "Doesn't Count"
    if low.startswith("ap") or "advanced placement" in low:
        return "AP"
    if low in ("h", "hon", "honors", "honour") or "honors" in low:
        return "Honors"
    if low in ("cp", "college prep", "c.p."):
        return "CP"
    if low in ("false", "true"):
        return ""
    return s[:1].upper() + s[1:] if s else ""


def sheet_raw_to_editor_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes a raw imported DataFrame (from CSV/Excel) and converts it to
    the standard format the Streamlit editor expects.

    - Renames columns using the alias map
    - Coerces grade cells to floats
    - Fills in the Remainder % column based on available data
    - Keeps placeholder rows (empty grades) so nothing is silently dropped
    """
    if df.empty:
        return pd.DataFrame(columns=EDITOR_COLUMNS)

    # Rename columns to internal keys using the alias map
    aliases = _alias_map()
    rename: dict[str, str] = {}
    for col in df.columns:
        canon = aliases.get(_norm_header(str(col)))
        if canon:
            rename[col] = canon
    work = df.rename(columns=rename)

    rows: list[dict[str, Any]] = []
    for _, r in work.iterrows():
        # Grade level (9, 10, 11, 12) — optional display only
        grade = r.get("grade", "")
        grade_str = "" if pd.isna(grade) else str(grade).strip()

        # Class name
        cls = r.get("class", "")
        cls = "" if pd.isna(cls) else str(cls).strip()
        cls = cls or "Course"

        # Course level (AP / Honors / CP / Doesn't Count)
        typ = normalize_type_for_editor(r.get("type", ""))

        # Credits (default to 5.0 if missing or invalid)
        w = coerce_grade_value(r.get("weight", float("nan")))
        credits = float(w) if (w is not None and w > 0) else 5.0

        # Individual grade cells
        q1 = coerce_grade_value(r.get("q1"))
        q2 = coerce_grade_value(r.get("q2"))
        e1 = coerce_grade_value(r.get("e1"))
        q3 = coerce_grade_value(r.get("q3"))
        q4 = coerce_grade_value(r.get("q4"))
        f1 = coerce_grade_value(r.get("f1"))
        gnum = coerce_grade_value(r.get("grade_num"))  # "Grade #" overall course %

        # Calculate remainder baseline and course %
        rem: float | None = None
        course_pct = gnum

        if q4 is not None and f1 is not None and all(x is not None for x in (q1, q2, q3, e1)):
            # Full year: calculate actual remainder from real grades
            from gpa_planner.course import WQ, WE, W_REM, full_year_final_pct
            fy = full_year_final_pct(q1, q2, q3, q4, e1, f1)
            s72 = WQ * (q1 + q2 + q3) + WE * e1
            rem = (fy - s72) / W_REM
            course_pct = fy

        elif gnum is not None and all(x is None for x in (q1, q2, q3, e1)):
            # Only overall grade known — use 85% as a safe remainder assumption
            rem = 85.0

        elif any(x is not None for x in (q1, q2, q3, e1)):
            # Partial year: use average of known quarters as the remainder baseline
            qs = [x for x in (q1, q2, q3) if x is not None]
            rem = sum(qs) / len(qs) if qs else 85.0

        rows.append({
            "Grade": grade_str,
            "Class": cls,
            "Level": typ,
            "Credits": credits,
            "Q1 %": q1,
            "Q2 %": q2,
            "Q3 %": q3,
            "E1 %": e1,
            "Q4 %": q4,
            "F1 %": f1,
            "Course %": course_pct,
            "Remainder %": rem if rem is not None else 85.0,
        })

    # Convert to DataFrame and ensure numeric columns are proper floats (not None)
    out = pd.DataFrame(rows)
    for c in ["Q1 %", "Q2 %", "Q3 %", "E1 %", "Q4 %", "F1 %", "Course %"]:
        out[c] = out[c].apply(
            lambda x: float(x)
            if x is not None and not (isinstance(x, float) and math.isnan(x))
            else float("nan")
        )
    return out


def read_uploaded_table(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Entry point: takes raw bytes from Streamlit's file_uploader and returns
    a cleaned DataFrame ready for the editor.

    Supports .csv and .xlsx / .xls files.
    """
    name = filename.lower()
    bio = io.BytesIO(file_bytes)

    if name.endswith(".csv"):
        raw = pd.read_csv(bio)
    elif name.endswith((".xlsx", ".xls")):
        try:
            raw = pd.read_excel(bio)
        except ImportError as e:
            raise ValueError("Excel import needs openpyxl: pip install openpyxl") from e
    else:
        raise ValueError("Upload a .csv or .xlsx file (File → Download → CSV from Google Sheets).")

    return sheet_raw_to_editor_dataframe(raw)
