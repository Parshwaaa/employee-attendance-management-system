"""Attendance calculations using Pandas and NumPy.

Attendance % = attended days / working days * 100, where
    attended days = Present + Late + 0.5 * Half-Day
    working days  = all recorded days except approved Leave

All analysis functions work on active employees only (set only_active=False
to include everybody).
"""

from datetime import datetime

import numpy as np
import pandas as pd

from config import (ATTENDANCE_STATUSES, DATE_FORMAT, HIGH_THRESHOLD,
                    LOW_THRESHOLD, REPORTS_DIR, STATUS_WEIGHTS)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]


# ---------------------------------------------------------------- basics
def period_label(start, end):
    """Human readable description of a date range (None = open ended)."""
    if start and end:
        return f"{start} to {end}"
    if start:
        return f"from {start}"
    if end:
        return f"until {end}"
    return "all dates"


def prepare_attendance(attendance, start=None, end=None):
    """Parse dates, apply the period filter and add 'score' / 'counted' columns."""
    df = attendance.copy()
    df["date"] = pd.to_datetime(df["date"], format=DATE_FORMAT, errors="coerce")
    df = df.dropna(subset=["date"])
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["date"] <= pd.Timestamp(end)]
    df = df.copy()
    df["score"] = df["status"].map(STATUS_WEIGHTS).fillna(0.0).astype(float)
    df["counted"] = np.where(df["status"] == "Leave", 0, 1)
    return df


def classify(percentages, low=LOW_THRESHOLD, high=HIGH_THRESHOLD):
    """Label each percentage as Low / Average / High (NaN -> No Data)."""
    pct = pd.to_numeric(percentages)
    conditions = [pct.isna(), pct < low, pct >= high]
    return np.select(conditions, ["No Data", "Low", "High"], default="Average")


def _percentage(attended, working):
    """Element-wise attended / working * 100, NaN where working == 0."""
    attended = np.asarray(attended, dtype=float)
    working = np.asarray(working, dtype=float)
    result = np.full(attended.shape, np.nan)
    np.divide(attended * 100, working, out=result, where=working > 0)
    return np.round(result, 2)


def overall_percentage(summary):
    """Weighted attendance % of a whole group (not an average of averages)."""
    working = summary["working_days"].sum()
    if working == 0:
        return float("nan")
    return round(float(summary["attended_days"].sum() / working * 100), 2)


# ------------------------------------------------------ employee summaries
def employee_summary(attendance, employees, start=None, end=None,
                     department=None, only_active=True,
                     low=LOW_THRESHOLD, high=HIGH_THRESHOLD):
    """One row per employee with status counts, attendance % and level."""
    emp = employees.copy()
    if department and department != "All":
        emp = emp[emp["department"] == department]
    if only_active:
        emp = emp[emp["status"] == "Active"]

    att = prepare_attendance(attendance, start, end)
    att = att[att["employee_id"].isin(emp["employee_id"])]

    if att.empty:
        counts = pd.DataFrame(columns=ATTENDANCE_STATUSES, dtype=int)
        totals = pd.DataFrame(columns=["attended_days", "working_days"], dtype=float)
    else:
        counts = (att.groupby(["employee_id", "status"]).size()
                  .unstack(fill_value=0)
                  .reindex(columns=ATTENDANCE_STATUSES, fill_value=0))
        totals = att.groupby("employee_id").agg(
            attended_days=("score", "sum"), working_days=("counted", "sum"))

    result = emp.rename(columns={"status": "emp_status"})[
        ["employee_id", "name", "department", "designation", "emp_status"]]
    result = result.merge(counts, left_on="employee_id", right_index=True, how="left")
    result = result.merge(totals, left_on="employee_id", right_index=True, how="left")

    for status in ATTENDANCE_STATUSES:
        result[status] = result[status].fillna(0).astype(int)
    result["attended_days"] = result["attended_days"].fillna(0).astype(float)
    result["working_days"] = result["working_days"].fillna(0).astype(int)
    result["attendance_pct"] = _percentage(result["attended_days"], result["working_days"])
    result["level"] = classify(result["attendance_pct"], low, high)
    return result.sort_values("employee_id").reset_index(drop=True)


def low_attendance(summary, threshold=LOW_THRESHOLD):
    """Employees below the threshold, worst first."""
    return (summary[summary["attendance_pct"] < threshold]
            .sort_values("attendance_pct").reset_index(drop=True))


def high_attendance(summary, threshold=HIGH_THRESHOLD):
    """Employees at or above the threshold, best first."""
    return (summary[summary["attendance_pct"] >= threshold]
            .sort_values("attendance_pct", ascending=False).reset_index(drop=True))


def basic_statistics(summary, low=LOW_THRESHOLD, high=HIGH_THRESHOLD):
    """Descriptive statistics of employee attendance % (NumPy)."""
    values = summary["attendance_pct"].dropna().to_numpy(dtype=float)
    if values.size == 0:
        return {}
    return {
        "Employees with data": int(values.size),
        "Mean attendance %": round(float(np.mean(values)), 2),
        "Median attendance %": round(float(np.median(values)), 2),
        "Standard deviation": round(float(np.std(values)), 2),
        "Lowest attendance %": round(float(np.min(values)), 2),
        "Highest attendance %": round(float(np.max(values)), 2),
        "25th percentile": round(float(np.percentile(values, 25)), 2),
        "75th percentile": round(float(np.percentile(values, 75)), 2),
        f"Employees below {low:g}%": int(np.sum(values < low)),
        f"Employees at or above {high:g}%": int(np.sum(values >= high)),
    }


# ----------------------------------------------------- department analysis
DEPARTMENT_COLUMNS = ["department", "employees", "working_days", "attended_days",
                      "attendance_pct", "avg_employee_pct", "low_count", "rank"]


def department_summary(summary):
    """Compare departments, ranked from best to worst attendance."""
    if summary.empty:
        return pd.DataFrame(columns=DEPARTMENT_COLUMNS)
    grouped = summary.groupby("department").agg(
        employees=("employee_id", "count"),
        working_days=("working_days", "sum"),
        attended_days=("attended_days", "sum"),
        avg_employee_pct=("attendance_pct", "mean"),
        low_count=("level", lambda levels: int((levels == "Low").sum())),
    )
    grouped["attendance_pct"] = _percentage(grouped["attended_days"], grouped["working_days"])
    grouped["avg_employee_pct"] = grouped["avg_employee_pct"].round(2)
    grouped["rank"] = (grouped["attendance_pct"].rank(ascending=False, method="min")
                       .fillna(0).astype(int))
    grouped = grouped.reset_index()[DEPARTMENT_COLUMNS]
    return grouped.sort_values("attendance_pct", ascending=False).reset_index(drop=True)


# ----------------------------------------------------- period comparison
def period_comparison(attendance, employees, start_a, end_a, start_b, end_b,
                      department=None, low=LOW_THRESHOLD, high=HIGH_THRESHOLD):
    """Compare two periods.

    Returns a tuple: (employee_comparison, department_comparison, overall)
    where overall is a dict with the organisation-wide % for each period.
    """
    summary_a = employee_summary(attendance, employees, start_a, end_a, department,
                                 low=low, high=high)
    summary_b = employee_summary(attendance, employees, start_b, end_b, department,
                                 low=low, high=high)

    people = (summary_a[["employee_id", "name", "department", "attendance_pct"]]
              .rename(columns={"attendance_pct": "period_a_pct"})
              .merge(summary_b[["employee_id", "attendance_pct"]]
                     .rename(columns={"attendance_pct": "period_b_pct"}),
                     on="employee_id"))
    people["change"] = (people["period_b_pct"] - people["period_a_pct"]).round(2)
    people["trend"] = np.select(
        [people["change"].isna(), people["change"] > 1, people["change"] < -1],
        ["No Data", "Improved", "Declined"], default="Stable")
    people = people.sort_values("change").reset_index(drop=True)

    depts = (department_summary(summary_a)[["department", "attendance_pct"]]
             .rename(columns={"attendance_pct": "period_a_pct"})
             .merge(department_summary(summary_b)[["department", "attendance_pct"]]
                    .rename(columns={"attendance_pct": "period_b_pct"}),
                    on="department", how="outer"))
    depts["change"] = (depts["period_b_pct"] - depts["period_a_pct"]).round(2)
    depts = depts.sort_values("department").reset_index(drop=True)

    pct_a, pct_b = overall_percentage(summary_a), overall_percentage(summary_b)
    overall = {"period_a": pct_a, "period_b": pct_b,
               "change": round(pct_b - pct_a, 2)}
    return people, depts, overall


# --------------------------------------------- time-based / distribution
def _filtered_attendance(attendance, employees, start, end, department):
    """Attendance rows (with 'department') of active employees in a period."""
    att = prepare_attendance(attendance, start, end)
    emp = employees[employees["status"] == "Active"][["employee_id", "department"]]
    if department and department != "All":
        emp = emp[emp["department"] == department]
    return att.merge(emp, on="employee_id", how="inner")


def monthly_trend(attendance, employees, start=None, end=None, department=None):
    """Month x department table of attendance %, plus an 'Overall' column."""
    att = _filtered_attendance(attendance, employees, start, end, department)
    if att.empty:
        return pd.DataFrame()
    att["month"] = att["date"].dt.strftime("%Y-%m")
    by_dept = att.groupby(["month", "department"])[["score", "counted"]].sum()
    pivot = pd.DataFrame(
        _percentage(by_dept["score"], by_dept["counted"]),
        index=by_dept.index, columns=["pct"])["pct"].unstack("department")
    overall = att.groupby("month")[["score", "counted"]].sum()
    pivot["Overall"] = _percentage(overall["score"], overall["counted"])
    return pivot


def weekday_absence(attendance, employees, start=None, end=None, department=None):
    """Absence rate for each day of the week."""
    att = _filtered_attendance(attendance, employees, start, end, department)
    att = att[att["counted"] == 1]
    columns = ["weekday", "records", "absences", "absence_rate"]
    if att.empty:
        return pd.DataFrame(columns=columns)
    att["day"] = att["date"].dt.dayofweek
    grouped = att.groupby("day").agg(
        records=("status", "size"),
        absences=("status", lambda s: int((s == "Absent").sum())))
    grouped["absence_rate"] = _percentage(grouped["absences"] * 1.0, grouped["records"])
    grouped["weekday"] = [DAY_NAMES[i] for i in grouped.index]
    return grouped.reset_index(drop=True)[columns]


def status_distribution(attendance, employees, start=None, end=None, department=None):
    """Number of records per attendance status."""
    att = _filtered_attendance(attendance, employees, start, end, department)
    return att["status"].value_counts().reindex(ATTENDANCE_STATUSES, fill_value=0)


# ------------------------------------------------------------- dashboard
def dashboard_metrics(employees, attendance, low=LOW_THRESHOLD, high=HIGH_THRESHOLD):
    """Headline numbers for the dashboard cards."""
    summary = employee_summary(attendance, employees, low=low, high=high)
    att = prepare_attendance(attendance)
    metrics = {
        "total_employees": len(employees),
        "active_employees": int((employees["status"] == "Active").sum()),
        "overall_pct": overall_percentage(summary),
        "low_count": int((summary["level"] == "Low").sum()),
        "high_count": int((summary["level"] == "High").sum()),
        "latest_date": "-",
        "latest_text": "No attendance recorded",
    }
    if not att.empty:
        latest = att["date"].max()
        day = att[att["date"] == latest]
        attended = int(day["status"].isin(["Present", "Late", "Half-Day"]).sum())
        metrics["latest_date"] = latest.strftime(DATE_FORMAT)
        metrics["latest_text"] = f"{attended} of {len(day)} attended"
    return metrics


# --------------------------------------------------------------- exports
def export_report_csv(df, prefix, folder=REPORTS_DIR):
    """Write a DataFrame to reports/<prefix>_<timestamp>.csv and return the path."""
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = folder / f"{prefix}_{stamp}.csv"
    df.to_csv(path, index=False)
    return path
