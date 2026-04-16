"""Streamlit UI for GPA goal planner."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from gpa_planner.course import W_REM
from gpa_planner.editor_parse import parse_courses_from_dataframe
from gpa_planner.gpa import (
    max_achievable_gpa,
    quality_point_deficit,
    unweighted_gpa,
    weighted_gpa,
)
from gpa_planner.scale import next_threshold_pct
from gpa_planner.sheet_import import read_uploaded_table
from gpa_planner.spillover import run_spillover

DEFAULT_ROWS = 6

def _default_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Grade": "",
                "Class": f"Course {i + 1}",
                "Term": "Full Year",
                "Level": "AP",
                "Credits": 5.0,
                "Q1 %": 90.0,
                "Q2 %": 90.0,
                "Q3 %": 90.0,
                "E1 %": 90.0,
                "Q4 %": float("nan"),
                "F1 %": float("nan"),
                "Course %": float("nan"),
                "Remainder %": 90.0,
            }
            for i in range(DEFAULT_ROWS)
        ]
    )


def _sync_editor_to_df() -> None:
    editor_value = st.session_state.get("class_table_editor")
    if isinstance(editor_value, pd.DataFrame):
        st.session_state.class_table_df = editor_value.copy()


def _replace_table(df: pd.DataFrame) -> None:
    st.session_state.class_table_df = df.copy()
    # Clear widget-owned value so data_editor re-initializes from class_table_df.
    if "class_table_editor" in st.session_state:
        del st.session_state["class_table_editor"]


st.set_page_config(page_title="GPA goal planner", layout="wide")
st.title("GPA goal planner")
st.caption(
    "Weights: Q1–Q4 = 22% each; E1 & F1 = 6% each. "
    "Completed (Q1+Q2+Q3+E1) = 72%; remaining (Q4+F1) = 28%. "
    "For Semester (S1), use Q1+Q2+E1 only (normalized to the semester final); set credits to 2.5. "
    "If only some early grades are entered, the planner auto-infers baseline remainder from known weighted grades. "
    "Import a Google Sheet (CSV or Excel): **File → Download → Comma-separated values (.csv)**."
)

if "class_table_df" not in st.session_state:
    st.session_state.class_table_df = _default_df()
if "last_import_sig" not in st.session_state:
    st.session_state.last_import_sig = None

with st.sidebar:
    st.header("GPA mode")
    gpa_mode = st.radio(
        "Calculation",
        options=["weighted", "unweighted"],
        format_func=lambda x: "Weighted" if x == "weighted" else "Unweighted",
        index=0,
        horizontal=True,
        help="Unweighted uses the CP grade table for every class (max 4.0 on this scale).",
    )
    use_unweighted = gpa_mode == "unweighted"
    st.header("Goal")
    _goal_max = 4.0 if use_unweighted else 5.0
    # Separate widget keys so each mode keeps its own goal (unweighted max is 4.0).
    _goal_key = "goal_gpa_unweighted" if use_unweighted else "goal_gpa_weighted"
    goal_gpa = st.number_input(
        "Goal GPA",
        min_value=0.0,
        max_value=_goal_max,
        value=3.8 if use_unweighted else 4.0,
        step=0.01,
        format="%.2f",
        key=_goal_key,
    )
    st.header("Baseline remainder (Q4 + F1)")
    baseline_mode = st.radio(
        "How to set assumed Q4/F1 average before optimization",
        options=[
            "avg_q",
            "column",
        ],
        format_func=lambda x: {
            "avg_q": "Average of Q1–Q3 (per class)",
            "column": "Use “Remainder %” column",
        }[x],
        index=0,
    )
    st.divider()
    uploaded = st.file_uploader(
        "Import sheet (.csv / .xlsx)",
        type=["csv", "xlsx", "xls"],
        help="Columns recognized: Grade, Class, Q1–Q4, E1, F1, Type, Weight, “Grade #”. "
        "Empty grades and FALSE are treated as blanks. “Doesn’t Count” rows are excluded from GPA.",
    )
    st.link_button(
        "Download template sheet",
        "https://docs.google.com/spreadsheets/u/1/d/1FgQUba-fVAT2A74Lg6k4vwFkH1pElIH7UDeLQczioG0/copy",
        help="Open a copy-ready Google Sheets template in a new tab.",
    )
    if uploaded is not None:
        upload_sig = f"{uploaded.name}:{uploaded.size}"
        if st.session_state.last_import_sig != upload_sig:
            try:
                raw = uploaded.read()
                imported = read_uploaded_table(raw, uploaded.name)
                _replace_table(imported)
                st.session_state.last_import_sig = upload_sig
                st.success(f"Loaded **{len(imported)}** rows. Edit below if needed, then calculate.")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    if st.button("Reset table to sample rows"):
        _replace_table(_default_df())
        st.session_state.last_import_sig = None
        st.rerun()
    st.markdown("---")
    st.markdown("Then click **Calculate plan** in the main panel →")

st.subheader("Classes")
edited = st.data_editor(
    st.session_state.class_table_df,
    key="class_table_editor",
    on_change=_sync_editor_to_df,
    num_rows="dynamic",
    width="stretch",
    column_config={
        "Grade": st.column_config.TextColumn("Grade", help="Optional (e.g. 9–12). Not used in math.", width="small"),
        "Class": st.column_config.TextColumn("Class", width="medium"),
        "Term": st.column_config.SelectboxColumn(
            "Term",
            options=["Full Year", "Semester (S1)"],
            required=False,
            help="Semester (S1) uses Q1 + Q2 + E1 as the final for this row.",
        ),
        "Level": st.column_config.SelectboxColumn(
            "Level",
            options=["AP", "Honors", "CP", "Doesn't Count", ""],
            required=False,
        ),
        "Credits": st.column_config.NumberColumn("Credits", min_value=0.25, step=0.25, format="%.2f"),
        "Q1 %": st.column_config.NumberColumn("Q1 %", min_value=0.0, max_value=100.0, step=0.01, format="%.2f"),
        "Q2 %": st.column_config.NumberColumn("Q2 %", min_value=0.0, max_value=100.0, step=0.01, format="%.2f"),
        "Q3 %": st.column_config.NumberColumn("Q3 %", min_value=0.0, max_value=100.0, step=0.01, format="%.2f"),
        "E1 %": st.column_config.NumberColumn("E1 %", min_value=0.0, max_value=100.0, step=0.01, format="%.2f"),
        "Q4 %": st.column_config.NumberColumn(
            "Q4 %",
            min_value=0.0,
            max_value=100.0,
            step=0.01,
            format="%.2f",
            help="If set with F1, year is treated as complete (locked).",
        ),
        "F1 %": st.column_config.NumberColumn(
            "F1 %",
            min_value=0.0,
            max_value=100.0,
            step=0.01,
            format="%.2f",
            help="If set with Q4, year is treated as complete (locked).",
        ),
        "Course %": st.column_config.NumberColumn(
            "Course %",
            min_value=0.0,
            max_value=100.0,
            step=0.01,
            format="%.2f",
            help="Optional: final % when quarter grades are missing (e.g. from your sheet’s “Grade #”).",
        ),
        "Remainder %": st.column_config.NumberColumn(
            "Remainder %",
            min_value=0.0,
            max_value=100.0,
            step=0.01,
            format="%.2f",
            help="Q4+F1 average for planning rows when baseline uses this column.",
        ),
    },
    hide_index=True,
)

run = st.button("Calculate plan", type="primary")

if not run:
    st.info(
        "**Placeholders:** rows with no Q1–Q3/E1 and no **Course %** stay in the table but are "
        "**skipped** for GPA until you add grades. **Doesn’t Count** never affects GPA. "
        "**Semester (S1)** rows count immediately when Q1, Q2, and E1 are present."
    )
    st.stop()

rows = edited.dropna(how="all", subset=["Class"])
if rows.empty:
    st.error("Add at least one class row.")
    st.stop()

courses, errors = parse_courses_from_dataframe(rows, baseline_mode)

if errors:
    st.error("Fix the following:\n\n- " + "\n- ".join(errors))
    st.stop()

if not courses:
    st.error("No rows to process.")
    st.stop()

counted_n = sum(1 for c in courses if c.counts_for_gpa)
_mode_label = "unweighted" if use_unweighted else "weighted"
st.caption(
    f"**{counted_n}** of **{len(courses)}** rows count toward {_mode_label} GPA "
    "(others are placeholders or “Doesn’t Count”)."
)

try:
    max_g = max_achievable_gpa(courses, unweighted=use_unweighted)
except ValueError as e:
    st.error(str(e))
    st.stop()

baseline_finals = [c.final_from_remainder(c.remainder_baseline) for c in courses]
_gpa_fn = unweighted_gpa if use_unweighted else weighted_gpa
baseline_w = _gpa_fn(courses, baseline_finals)
deficit = quality_point_deficit(goal_gpa, courses, baseline_finals, unweighted=use_unweighted)

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric(f"Baseline {_mode_label} GPA", f"{baseline_w:.4f}")
col_b.metric("Goal", f"{goal_gpa:.4f}")
col_c.metric("Max possible (100% remainder on planning rows)", f"{max_g:.4f}")
col_d.metric("Quality-point gap (baseline)", f"{deficit:+.4f}", help="goal×Σc − Σ(c×points); positive means you need more points.")

if max_g + 1e-6 < goal_gpa:
    st.warning(
        f"Even with **100%** on Q4+F1 in every planning row, {_mode_label} GPA tops out at **{max_g:.4f}**, "
        f"which is below the goal **{goal_gpa:.4f}**."
    )

result = run_spillover(courses, goal_gpa, unweighted=use_unweighted)

st.subheader("After spillover plan")
c1, c2, c3 = st.columns(3)
c1.metric(f"Planned {_mode_label} GPA", f"{result.final_gpa:.4f}")
c2.metric("Goal reached", "Yes" if result.goal_reached else "No")
c3.metric("Steps", len(result.steps))

summary_rows = []
for c, rem, fin in zip(result.courses, result.remainders, result.finals, strict=True):
    if not c.counts_for_gpa:
        summary_rows.append(
            {
                "Class": c.name,
                "In GPA": "No",
                "Level": "—",
                "Credits": c.credits,
                "Note": "Placeholder or doesn’t count",
                "Planned final %": "—",
                "Next % bracket": "—",
                "X for next bracket": "—",
            }
        )
        continue
    T = next_threshold_pct(fin)
    S = c.completed_sum()
    if T is None:
        x_next = None
    else:
        x_next = (T - S) / W_REM
    note = "Locked (year complete or Course %)" if (c.locked or c.fixed_final_pct is not None) else ""
    summary_rows.append(
        {
            "Class": c.name,
            "In GPA": "Yes",
            "Level": c.level,
            "Credits": c.credits,
            "Note": note,
            "Planned final %": round(fin, 2),
            "Next % bracket": T if T is not None else "—",
            "X for next bracket": round(x_next, 2) if x_next is not None else "—",
        }
    )
st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)

if result.steps:
    st.subheader("Spillover steps (easiest first)")
    step_df = pd.DataFrame(
        [
            {
                "Step": i + 1,
                "Class": s.course_name,
                "Target %": round(s.bracket_target_pct, 2),
                "X required": round(s.x_required, 2),
                "Remainder before→after": f"{s.remainder_before:.2f} → {s.remainder_after:.2f}",
                "Final before→after": f"{s.final_before:.2f} → {s.final_after:.2f}",
                "Capped at 100%": "Yes" if s.capped_at_100 else "",
            }
            for i, s in enumerate(result.steps)
        ]
    )
    st.dataframe(step_df, width="stretch", hide_index=True)
else:
    st.caption("No spillover steps (baseline already meets the goal, or no planning rows to adjust).")

if not result.goal_reached and max_g + 1e-6 >= goal_gpa:
    st.warning(
        "The greedy plan did not reach the goal within the step limit or stalled. "
        "Try lowering the goal slightly or check for edge cases in your inputs."
    )
