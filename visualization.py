"""Matplotlib charts. Every function returns a Figure that the GUI embeds
(or that save_figure() writes to the reports folder)."""

import re
from datetime import datetime

import numpy as np
from matplotlib.figure import Figure

import analytics
from config import HIGH_THRESHOLD, LOW_THRESHOLD, REPORTS_DIR
from validators import ValidationError

COLORS = {"primary": "#2F6DB5", "second": "#E08A2E", "good": "#3C9D5D",
          "bad": "#CC4B4B", "grey": "#7A8594"}
STATUS_COLORS = {"Present": "#3C9D5D", "Late": "#E0A030", "Half-Day": "#6BA3D6",
                 "Leave": "#9AA3AF", "Absent": "#CC4B4B"}

CHART_TYPES = [
    "Department comparison (bar)",
    "Attendance status distribution (pie)",
    "Monthly attendance trend (line)",
    "Employee attendance spread (histogram)",
    "Lowest and highest employees (bar)",
    "Period comparison by department (bar)",
    "Absence rate by weekday (bar)",
]


def _new_figure(size=(7, 4.5)):
    return Figure(figsize=size, dpi=100, constrained_layout=True)


def _title(ax, title, subtitle):
    ax.set_title(f"{title}\n{subtitle}" if subtitle else title, fontsize=11)


def empty_figure(message="No attendance data for the selected filters."):
    fig = _new_figure()
    ax = fig.add_subplot(111)
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12, color=COLORS["grey"])
    ax.axis("off")
    return fig


def _threshold_lines(ax, low, high, orientation="h"):
    draw = ax.axhline if orientation == "h" else ax.axvline
    draw(low, color=COLORS["bad"], linestyle="--", linewidth=1, label=f"Low ({low:g}%)")
    draw(high, color=COLORS["good"], linestyle="--", linewidth=1, label=f"High ({high:g}%)")


# ------------------------------------------------------------------ charts
def department_bar(dept_df, low=LOW_THRESHOLD, high=HIGH_THRESHOLD, subtitle=""):
    data = dept_df.dropna(subset=["attendance_pct"])
    if data.empty:
        return empty_figure()
    fig = _new_figure()
    ax = fig.add_subplot(111)
    values = data["attendance_pct"].to_numpy(dtype=float)
    colors = [COLORS["bad"] if v < low else COLORS["good"] if v >= high
              else COLORS["primary"] for v in values]
    bars = ax.bar(data["department"], values, color=colors)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 1, f"{value:.1f}%",
                ha="center", fontsize=9)
    _threshold_lines(ax, low, high)
    ax.set_ylim(0, 120)
    ax.set_ylabel("Attendance %")
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    _title(ax, "Attendance by department", subtitle)
    return fig


def status_pie(counts, subtitle=""):
    counts = counts[counts > 0]
    if counts.empty:
        return empty_figure()
    fig = _new_figure((5.5, 4.5))
    ax = fig.add_subplot(111)
    ax.pie(counts.to_numpy(), labels=list(counts.index), autopct="%1.1f%%",
           colors=[STATUS_COLORS[s] for s in counts.index], startangle=90,
           wedgeprops={"edgecolor": "white"}, textprops={"fontsize": 9})
    _title(ax, "Attendance status distribution", subtitle)
    return fig


def monthly_line(pivot, subtitle=""):
    if pivot.empty:
        return empty_figure()
    fig = _new_figure()
    ax = fig.add_subplot(111)
    x = np.arange(len(pivot.index))
    for column in pivot.columns:
        if column == "Overall":
            ax.plot(x, pivot[column], color="black", linewidth=2.5, linestyle="--",
                    marker="o", label="Overall")
        else:
            ax.plot(x, pivot[column], marker="o", linewidth=1.5, label=column)
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, rotation=30)
    low_value = np.nanmin(pivot.to_numpy(dtype=float))
    ax.set_ylim(max(0, low_value - 10), 102)
    ax.set_ylabel("Attendance %")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, ncol=2)
    _title(ax, "Monthly attendance trend", subtitle)
    return fig


def attendance_histogram(summary, low=LOW_THRESHOLD, high=HIGH_THRESHOLD, subtitle=""):
    values = summary["attendance_pct"].dropna().to_numpy(dtype=float)
    if values.size == 0:
        return empty_figure()
    fig = _new_figure()
    ax = fig.add_subplot(111)
    start = min(int(np.floor(values.min() / 5) * 5), 95)
    ax.hist(values, bins=np.arange(start, 105, 5), color=COLORS["primary"],
            edgecolor="white")
    _threshold_lines(ax, low, high, orientation="v")
    ax.set_xlabel("Attendance %")
    ax.set_ylabel("Number of employees")
    ax.legend(fontsize=8)
    _title(ax, "Spread of employee attendance", subtitle)
    return fig


def top_bottom_bar(summary, n=5, subtitle=""):
    data = summary.dropna(subset=["attendance_pct"])
    if data.empty:
        return empty_figure()
    fig = _new_figure((9, 4.5))
    left, right = fig.subplots(1, 2, sharex=True)
    lowest = data.nsmallest(n, "attendance_pct").iloc[::-1]
    highest = data.nlargest(n, "attendance_pct").iloc[::-1]
    for ax, part, color, title in ((left, lowest, COLORS["bad"], f"Lowest {len(lowest)}"),
                                   (right, highest, COLORS["good"], f"Highest {len(highest)}")):
        ax.barh(part["name"], part["attendance_pct"], color=color)
        for y, value in enumerate(part["attendance_pct"]):
            ax.text(value + 0.5, y, f"{value:.1f}%", va="center", fontsize=8)
        ax.set_xlim(0, 112)
        ax.set_xlabel("Attendance %")
        ax.set_title(title, fontsize=10)
    fig.suptitle(f"Employee attendance extremes {('- ' + subtitle) if subtitle else ''}",
                 fontsize=11)
    return fig


def period_comparison_bar(dept_cmp, label_a, label_b):
    data = dept_cmp.dropna(subset=["period_a_pct", "period_b_pct"], how="all")
    if data.empty:
        return empty_figure()
    fig = _new_figure()
    ax = fig.add_subplot(111)
    x = np.arange(len(data))
    width = 0.38
    bars_a = ax.bar(x - width / 2, data["period_a_pct"], width, color=COLORS["primary"],
                    label=f"A: {label_a}")
    bars_b = ax.bar(x + width / 2, data["period_b_pct"], width, color=COLORS["second"],
                    label=f"B: {label_b}")
    for bars in (bars_a, bars_b):
        for bar in bars:
            height = bar.get_height()
            if not np.isnan(height):
                ax.text(bar.get_x() + bar.get_width() / 2, height + 1, f"{height:.0f}",
                        ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(data["department"])
    ax.set_ylim(0, 125)
    ax.set_ylabel("Attendance %")
    ax.legend(fontsize=8, loc="upper right", ncol=2)
    ax.set_title("Department attendance - period comparison", fontsize=11)
    return fig


def weekday_bar(weekday_df, subtitle=""):
    if weekday_df.empty:
        return empty_figure()
    fig = _new_figure()
    ax = fig.add_subplot(111)
    rates = weekday_df["absence_rate"].to_numpy(dtype=float)
    bars = ax.bar(weekday_df["weekday"], rates,
                  color=[COLORS["bad"] if r == rates.max() else COLORS["grey"] for r in rates])
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, rate + 0.1, f"{rate:.1f}%",
                ha="center", fontsize=9)
    ax.set_ylabel("Absent records (%)")
    ax.set_ylim(0, rates.max() * 1.25 + 1)
    _title(ax, "Absence rate by day of the week", subtitle)
    return fig


# ---------------------------------------------------------------- dispatcher
def create_chart(chart_name, attendance, employees, filters,
                 low=LOW_THRESHOLD, high=HIGH_THRESHOLD):
    """Build the chart called chart_name for the given filters.

    filters: dict with start, end, department, start_b, end_b (all optional).
    """
    start, end = filters.get("start"), filters.get("end")
    department = filters.get("department") or "All"
    subtitle = analytics.period_label(start, end)
    if department != "All":
        subtitle += f" | {department}"

    def summary():
        return analytics.employee_summary(attendance, employees, start, end,
                                          department, low=low, high=high)

    if chart_name == CHART_TYPES[0]:
        return department_bar(analytics.department_summary(summary()), low, high, subtitle)
    if chart_name == CHART_TYPES[1]:
        counts = analytics.status_distribution(attendance, employees, start, end, department)
        return status_pie(counts, subtitle)
    if chart_name == CHART_TYPES[2]:
        return monthly_line(analytics.monthly_trend(attendance, employees, start, end,
                                                    department), subtitle)
    if chart_name == CHART_TYPES[3]:
        return attendance_histogram(summary(), low, high, subtitle)
    if chart_name == CHART_TYPES[4]:
        return top_bottom_bar(summary(), subtitle=subtitle)
    if chart_name == CHART_TYPES[5]:
        start_b, end_b = filters.get("start_b"), filters.get("end_b")
        if not (start and end and start_b and end_b):
            raise ValidationError("Enter both dates for Period A and Period B "
                                  "to compare two periods.")
        _, dept_cmp, _ = analytics.period_comparison(
            attendance, employees, start, end, start_b, end_b, department, low, high)
        return period_comparison_bar(dept_cmp, analytics.period_label(start, end),
                                     analytics.period_label(start_b, end_b))
    if chart_name == CHART_TYPES[6]:
        return weekday_bar(analytics.weekday_absence(attendance, employees, start, end,
                                                     department), subtitle)
    raise ValidationError(f"Unknown chart type: {chart_name!r}")


def save_figure(fig, name, folder=REPORTS_DIR):
    """Save a figure as PNG in the reports folder and return the file path."""
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    path = folder / f"{safe_name}_{datetime.now():%Y%m%d_%H%M%S}.png"
    fig.savefig(path, dpi=150)
    return path
