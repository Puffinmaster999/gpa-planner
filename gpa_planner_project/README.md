# GPA Goal Planner 📊

A web app that tells you exactly what you need to score on Q4 and your final exam to hit your target GPA.

## How to use it

1. Enter your classes and Q1–Q3 + midterm grades in the table
2. Set your goal GPA in the sidebar
3. Click **Calculate plan**
4. The app shows you the minimum Q4 + final exam averages needed per class

## Grade weights

| Component | Weight |
|-----------|--------|
| Q1, Q2, Q3, Q4 | 22% each |
| E1 (midterm), F1 (final exam) | 6% each |
| **Q1+Q2+Q3+E1 (completed)** | **72%** |
| **Q4+F1 (remaining)** | **28%** |

## Importing from Google Sheets

1. Open your grade sheet in Google Sheets
2. Go to **File → Download → Comma-separated values (.csv)**
3. Upload the file using the sidebar uploader

Column names are flexible — "Quarter 1", "Q1", "q1" all work.

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project structure

```
app.py                   # Main Streamlit web interface
gpa_planner/
  course.py              # Course data model + grade weight math
  scale.py               # GPA point conversion table (AP / Honors / CP)
  gpa.py                 # Weighted GPA calculation
  editor_parse.py        # Converts table rows into course objects
  sheet_import.py        # Google Sheets CSV/Excel importer
  spillover.py           # Optimization algorithm (finds easiest path to goal)
```
