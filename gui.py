"""Tkinter user interface.

Tabs: Dashboard, Employees, Attendance, Search & Filter, Analytics, Reports.
The GUI only collects input and shows results - all data handling lives in
employee_manager, attendance_manager, analytics and visualization.
"""

import functools
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import analytics
import config
import visualization
from attendance_manager import AttendanceManager
from employee_manager import EmployeeManager
from validators import (ValidationError, parse_date, parse_optional_date,
                        parse_percentage, validate_date_range, validate_thresholds)

# Row colours used by tables (tag name = value of the status/level column)
TAG_COLORS = {"Present": "#e3f4e8", "Late": "#fff3d6", "Half-Day": "#e3eefa",
              "Leave": "#ececec", "Absent": "#fbe3e3", "Low": "#fbe3e3",
              "High": "#e3f4e8", "Improved": "#e3f4e8", "Declined": "#fbe3e3"}
HEADING_NAMES = {"employee_id": "ID", "attendance_pct": "Attendance %",
                 "emp_status": "Employment", "period_a_pct": "Period A %",
                 "period_b_pct": "Period B %", "avg_employee_pct": "Avg Employee %"}


# ===================================================================== helpers
def safe_action(method):
    """Run a GUI action and show a message box instead of crashing on errors."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except ValidationError as error:
            messagebox.showwarning("Please check your input", str(error))
        except OSError as error:
            messagebox.showerror("File error", f"A file could not be read or written:\n{error}")
        except Exception as error:                       # last line of defence
            messagebox.showerror("Unexpected error", f"{type(error).__name__}: {error}")
    return wrapper


def format_cell(value):
    if isinstance(value, (float, np.floating)):
        return "-" if np.isnan(value) else f"{value:.1f}"
    return str(value)


class DataTable(ttk.Frame):
    """A Treeview with scrollbars that can display any DataFrame."""

    def __init__(self, parent, height=12):
        super().__init__(parent)
        self.tree = ttk.Treeview(self, show="headings", height=height, selectmode="extended")
        y_scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        for tag, color in TAG_COLORS.items():
            self.tree.tag_configure(tag, background=color)

    def show(self, df, columns=None, tag_column=None):
        columns = list(columns or df.columns)
        self.tree.configure(columns=columns)
        for column in columns:
            title = HEADING_NAMES.get(column, column.replace("_", " ").title())
            self.tree.heading(column, text=title,
                              command=lambda c=column: self._sort(c, False))
            self.tree.column(column, width=max(70, min(190, 11 * len(title) + 24)),
                             anchor="w", stretch=True)
        for item in self.tree.get_children():
            self.tree.delete(item)
        for _, row in df.iterrows():
            tags = (str(row[tag_column]),) if tag_column else ()
            self.tree.insert("", "end", values=[format_cell(row[c]) for c in columns],
                             tags=tags)

    def selected_rows(self):
        """Selected rows as a list of {column: displayed text} dictionaries."""
        columns = self.tree["columns"]
        return [dict(zip(columns, self.tree.item(item, "values")))
                for item in self.tree.selection()]

    def _sort(self, column, reverse):
        def key(pair):
            try:
                return (0, float(pair[0]))
            except ValueError:
                return (1, pair[0].lower())
        pairs = [(self.tree.set(item, column), item) for item in self.tree.get_children()]
        pairs.sort(key=key, reverse=reverse)
        for position, (_, item) in enumerate(pairs):
            self.tree.move(item, "", position)
        self.tree.heading(column, command=lambda: self._sort(column, not reverse))


class ChartPanel(ttk.Frame):
    """Embeds a Matplotlib Figure in the window."""

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = None
        self.figure = None

    def show(self, figure):
        self.clear()
        self.figure = figure
        self.canvas = FigureCanvasTkAgg(figure, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def clear(self):
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
        self.canvas = None
        self.figure = None


class FilterBar(ttk.LabelFrame):
    """Date range, department (and optionally Period B and thresholds)."""

    def __init__(self, parent, app, show_period_b=False, show_thresholds=False):
        super().__init__(parent, text="Filters", padding=8)
        self.app = app
        self.start_var, self.end_var = tk.StringVar(), tk.StringVar()
        self.start_b_var, self.end_b_var = tk.StringVar(), tk.StringVar()
        self.dept_var = tk.StringVar(value="All")

        ttk.Label(self, text="From").grid(row=0, column=0, padx=(0, 4))
        ttk.Entry(self, textvariable=self.start_var, width=12).grid(row=0, column=1)
        ttk.Label(self, text="To").grid(row=0, column=2, padx=(10, 4))
        ttk.Entry(self, textvariable=self.end_var, width=12).grid(row=0, column=3)
        ttk.Label(self, text="Department").grid(row=0, column=4, padx=(10, 4))
        self.dept_combo = ttk.Combobox(self, textvariable=self.dept_var, width=14,
                                       state="readonly", values=["All"])
        self.dept_combo.grid(row=0, column=5)
        if show_thresholds:
            ttk.Label(self, text="Low below %").grid(row=0, column=6, padx=(14, 4))
            ttk.Entry(self, textvariable=app.low_var, width=5).grid(row=0, column=7)
            ttk.Label(self, text="High from %").grid(row=0, column=8, padx=(10, 4))
            ttk.Entry(self, textvariable=app.high_var, width=5).grid(row=0, column=9)
        if show_period_b:
            ttk.Label(self, text="Compare with Period B:  From").grid(
                row=1, column=0, columnspan=2, pady=(6, 0), sticky="e")
            ttk.Entry(self, textvariable=self.start_b_var, width=12).grid(row=1, column=2, columnspan=2, pady=(6, 0))
            ttk.Label(self, text="To").grid(row=1, column=4, pady=(6, 0), sticky="e")
            ttk.Entry(self, textvariable=self.end_b_var, width=12).grid(row=1, column=5, pady=(6, 0), sticky="w")
        ttk.Label(self, text="Dates use YYYY-MM-DD. Leave blank for all dates.",
                  foreground="#666").grid(row=2, column=0, columnspan=10, sticky="w", pady=(6, 0))

    def refresh_departments(self):
        values = ["All"] + self.app.employees.departments()
        self.dept_combo["values"] = values
        if self.dept_var.get() not in values:
            self.dept_var.set("All")

    def reset(self):
        for var in (self.start_var, self.end_var, self.start_b_var, self.end_b_var):
            var.set("")
        self.dept_var.set("All")

    def get_filters(self, require_periods=False):
        """Validated filters as a dict (raises ValidationError on bad input)."""
        start = parse_optional_date(self.start_var.get(), "Period A 'From' date")
        end = parse_optional_date(self.end_var.get(), "Period A 'To' date")
        start_b = parse_optional_date(self.start_b_var.get(), "Period B 'From' date")
        end_b = parse_optional_date(self.end_b_var.get(), "Period B 'To' date")
        validate_date_range(start, end, "Period A")
        validate_date_range(start_b, end_b, "Period B")
        if require_periods and not (start and end and start_b and end_b):
            raise ValidationError("Enter the From and To dates for both Period A and Period B.")
        return {"start": start, "end": end, "start_b": start_b, "end_b": end_b,
                "department": self.dept_var.get() or "All"}


# ====================================================================== tabs
class DashboardTab(ttk.Frame):
    CARDS = [("active", "Active employees"), ("overall", "Overall attendance"),
             ("low", "Low attendance"), ("high", "High attendance"),
             ("latest", "Last recorded day")]

    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.values = {}

        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Attendance overview", style="Heading.TLabel").pack(side="left")
        ttk.Button(header, text="Refresh", command=self.refresh).pack(side="right")

        cards = ttk.Frame(self)
        cards.pack(fill="x", pady=10)
        for column, (key, caption) in enumerate(self.CARDS):
            card = ttk.Frame(cards, style="Card.TFrame", padding=(14, 10))
            card.grid(row=0, column=column, padx=5, sticky="nsew")
            cards.columnconfigure(column, weight=1)
            self.values[key] = tk.StringVar(value="-")
            ttk.Label(card, textvariable=self.values[key], style="CardValue.TLabel").pack(anchor="w")
            ttk.Label(card, text=caption, style="CardCaption.TLabel").pack(anchor="w")
        self.latest_note = tk.StringVar()
        ttk.Label(self, textvariable=self.latest_note, foreground="#555").pack(anchor="w")

        charts = ttk.Frame(self)
        charts.pack(fill="both", expand=True, pady=(8, 0))
        charts.columnconfigure(0, weight=3)
        charts.columnconfigure(1, weight=2)
        charts.rowconfigure(0, weight=1)
        self.dept_chart = ChartPanel(charts)
        self.dept_chart.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.pie_chart = ChartPanel(charts)
        self.pie_chart.grid(row=0, column=1, sticky="nsew")

    @safe_action
    def refresh(self):
        low, high = self.app.safe_thresholds()
        employees, attendance = self.app.employees.get_all(), self.app.attendance.get_all()
        metrics = analytics.dashboard_metrics(employees, attendance, low, high)

        overall = metrics["overall_pct"]
        self.values["active"].set(f"{metrics['active_employees']} / {metrics['total_employees']}")
        self.values["overall"].set("-" if np.isnan(overall) else f"{overall:.1f}%")
        self.values["low"].set(str(metrics["low_count"]))
        self.values["high"].set(str(metrics["high_count"]))
        self.values["latest"].set(metrics["latest_date"])
        self.latest_note.set(f"Last recorded day: {metrics['latest_text']}.   "
                             f"Low = below {low:g}%, High = {high:g}% or more.")

        summary = analytics.employee_summary(attendance, employees, low=low, high=high)
        self.dept_chart.show(visualization.department_bar(
            analytics.department_summary(summary), low, high))
        self.pie_chart.show(visualization.status_pie(
            analytics.status_distribution(attendance, employees)))


class EmployeesTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.vars = {key: tk.StringVar() for key in
                     ("id", "name", "department", "designation", "email", "join_date", "status")}

        form = ttk.LabelFrame(self, text="Employee details", padding=10)
        form.pack(fill="x")
        fields = [("Employee ID", "id"), ("Full name", "name"), ("Department", "department"),
                  ("Designation", "designation"), ("Email", "email"),
                  ("Join date (YYYY-MM-DD)", "join_date"), ("Status", "status")]
        for index, (label, key) in enumerate(fields):
            row, col = divmod(index, 4)
            ttk.Label(form, text=label).grid(row=row * 2, column=col, sticky="w", padx=6)
            if key == "department":
                self.dept_combo = ttk.Combobox(form, textvariable=self.vars[key], width=22)
                widget = self.dept_combo
            elif key == "status":
                widget = ttk.Combobox(form, textvariable=self.vars[key], width=22,
                                      state="readonly", values=config.EMPLOYEE_STATUSES)
            else:
                widget = ttk.Entry(form, textvariable=self.vars[key], width=25,
                                   state="readonly" if key == "id" else "normal")
            widget.grid(row=row * 2 + 1, column=col, padx=6, pady=(0, 6), sticky="w")

        buttons = ttk.Frame(form)
        buttons.grid(row=4, column=0, columnspan=4, sticky="w", pady=(6, 0))
        for text, command in (("Add employee", self.add), ("Update selected", self.update),
                              ("Delete selected", self.delete), ("Clear form", self.clear_form)):
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=4)

        self.count_label = ttk.Label(self, foreground="#555")
        self.count_label.pack(anchor="w", pady=(10, 2))
        self.table = DataTable(self, height=14)
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.clear_form()

    def refresh(self):
        self.dept_combo["values"] = self.app.employees.departments(include_defaults=True)
        employees = self.app.employees.get_all()
        self.table.show(employees)
        active = int((employees["status"] == "Active").sum())
        self.count_label.configure(text=f"{len(employees)} employees ({active} active). "
                                        "Click a row to edit or delete it.")

    def _form_values(self):
        return (self.vars["name"].get(), self.vars["department"].get(),
                self.vars["designation"].get(), self.vars["email"].get(),
                self.vars["join_date"].get(), self.vars["status"].get())

    def _selected_id(self):
        emp_id = self.vars["id"].get()
        if not emp_id:
            raise ValidationError("Select an employee from the table first.")
        return emp_id

    @safe_action
    def add(self):
        emp_id = self.app.employees.add_employee(*self._form_values())
        self.app.set_status(f"Added employee {emp_id}.")
        self.clear_form()
        self.refresh()

    @safe_action
    def update(self):
        emp_id = self._selected_id()
        self.app.employees.update_employee(emp_id, *self._form_values())
        self.app.set_status(f"Updated employee {emp_id}.")
        self.refresh()

    @safe_action
    def delete(self):
        emp_id = self._selected_id()
        records = self.app.attendance.count_for_employee(emp_id)
        name = self.vars["name"].get()
        if not messagebox.askyesno(
                "Delete employee",
                f"Delete {name} ({emp_id}) and their {records} attendance records?\n\n"
                "Tip: set the status to Inactive instead to keep the history."):
            return
        self.app.employees.delete_employee(emp_id)
        self.app.attendance.delete_employee_records(emp_id)
        self.app.set_status(f"Deleted employee {emp_id}.")
        self.clear_form()
        self.refresh()

    def on_select(self, _event=None):
        rows = self.table.selected_rows()
        if not rows:
            return
        row = rows[0]
        for key, column in (("id", "employee_id"), ("name", "name"), ("department", "department"),
                            ("designation", "designation"), ("email", "email"),
                            ("join_date", "join_date"), ("status", "status")):
            self.vars[key].set(row[column])

    def clear_form(self):
        for var in self.vars.values():
            var.set("")
        self.vars["status"].set("Active")
        self.table.tree.selection_remove(self.table.tree.selection())


class AttendanceTab(ttk.Frame):
    NOT_MARKED = "Not Marked"

    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.date_var = tk.StringVar(value=date.today().strftime(config.DATE_FORMAT))
        self.dept_var = tk.StringVar(value="All")

        top = ttk.LabelFrame(self, text="Choose a day", padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Date (YYYY-MM-DD)").pack(side="left")
        ttk.Entry(top, textvariable=self.date_var, width=12).pack(side="left", padx=6)
        ttk.Button(top, text="Load", command=self.load).pack(side="left")
        ttk.Button(top, text="Today", command=self.go_today).pack(side="left", padx=4)
        ttk.Label(top, text="Department").pack(side="left", padx=(16, 4))
        self.dept_combo = ttk.Combobox(top, textvariable=self.dept_var, width=14,
                                       state="readonly", values=["All"])
        self.dept_combo.pack(side="left")
        self.dept_combo.bind("<<ComboboxSelected>>", lambda _e: self.load())

        actions = ttk.LabelFrame(self, text="Mark the selected employees as", padding=8)
        actions.pack(fill="x", pady=8)
        for status in config.ATTENDANCE_STATUSES:
            ttk.Button(actions, text=status,
                       command=lambda s=status: self.mark_selected(s)).pack(side="left", padx=3)
        ttk.Button(actions, text="Clear mark", command=self.clear_marks).pack(side="left", padx=(14, 3))
        ttk.Button(actions, text="Mark all unmarked as Present",
                   command=self.mark_all_present).pack(side="right", padx=3)

        self.info = ttk.Label(self, foreground="#555")
        self.info.pack(anchor="w")
        self.table = DataTable(self, height=16)
        self.table.pack(fill="both", expand=True)

    def refresh(self):
        values = ["All"] + self.app.employees.departments()
        self.dept_combo["values"] = values
        if self.dept_var.get() not in values:
            self.dept_var.set("All")
        self.load()

    def go_today(self):
        self.date_var.set(date.today().strftime(config.DATE_FORMAT))
        self.load()

    @safe_action
    def load(self, *_args):
        day = parse_date(self.date_var.get(), "Attendance date")
        marks = self.app.attendance.get_for_date(day)
        employees = self.app.employees.get_all()
        employees = employees[employees["status"] == "Active"]
        if self.dept_var.get() != "All":
            employees = employees[employees["department"] == self.dept_var.get()]
        employees = employees.copy()
        employees["attendance"] = employees["employee_id"].map(marks).fillna(self.NOT_MARKED)
        self.table.show(employees, ["employee_id", "name", "department", "designation",
                                    "attendance"], tag_column="attendance")
        marked = int((employees["attendance"] != self.NOT_MARKED).sum())
        self.info.configure(text=f"{marked} of {len(employees)} active employees marked on {day}.")

    def _selected_ids(self):
        ids = [row["employee_id"] for row in self.table.selected_rows()]
        if not ids:
            raise ValidationError("Select one or more employees in the table first "
                                  "(Ctrl+click or Shift+click for several).")
        return ids

    @safe_action
    def mark_selected(self, status):
        marks = {emp_id: status for emp_id in self._selected_ids()}
        count = self.app.attendance.mark_many(self.date_var.get(), marks,
                                              valid_ids=self.app.employees.ids())
        self.app.set_status(f"Marked {count} employee(s) as {status}.")
        self.load()

    @safe_action
    def mark_all_present(self):
        rows = [r for r in self._all_rows() if r["attendance"] == self.NOT_MARKED]
        if not rows:
            raise ValidationError("There are no unmarked employees to mark.")
        marks = {row["employee_id"]: "Present" for row in rows}
        count = self.app.attendance.mark_many(self.date_var.get(), marks,
                                              valid_ids=self.app.employees.ids())
        self.app.set_status(f"Marked {count} unmarked employee(s) as Present.")
        self.load()

    def _all_rows(self):
        tree = self.table.tree
        columns = tree["columns"]
        return [dict(zip(columns, tree.item(item, "values"))) for item in tree.get_children()]

    @safe_action
    def clear_marks(self):
        removed = self.app.attendance.remove_marks(self.date_var.get(), self._selected_ids())
        self.app.set_status(f"Removed {removed} attendance record(s).")
        self.load()


class SearchTab(ttk.Frame):
    LEVELS = ["All", "Low", "Average", "High", "No Data"]
    COLUMNS = ["employee_id", "name", "department", "designation", "emp_status", "Present",
               "Late", "Half-Day", "Leave", "Absent", "working_days", "attendance_pct", "level"]

    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.query_var = tk.StringVar()
        self.status_var = tk.StringVar(value="All")
        self.level_var = tk.StringVar(value="All")
        self.result = pd.DataFrame()

        box = ttk.LabelFrame(self, text="Search employees", padding=8)
        box.pack(fill="x")
        ttk.Label(box, text="Name / ID / email / designation").grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(box, textvariable=self.query_var, width=30)
        entry.grid(row=1, column=0, padx=(0, 10))
        entry.bind("<Return>", lambda _e: self.search())
        ttk.Label(box, text="Employment status").grid(row=0, column=1, sticky="w")
        ttk.Combobox(box, textvariable=self.status_var, width=12, state="readonly",
                     values=["All"] + config.EMPLOYEE_STATUSES).grid(row=1, column=1, padx=(0, 10))
        ttk.Label(box, text="Attendance level").grid(row=0, column=2, sticky="w")
        ttk.Combobox(box, textvariable=self.level_var, width=12, state="readonly",
                     values=self.LEVELS).grid(row=1, column=2, padx=(0, 10))
        ttk.Button(box, text="Search", command=self.search).grid(row=1, column=3, padx=3)
        ttk.Button(box, text="Reset", command=self.reset).grid(row=1, column=4, padx=3)
        ttk.Button(box, text="Export CSV", command=self.export).grid(row=1, column=5, padx=3)

        self.filters = FilterBar(self, app, show_thresholds=True)
        self.filters.pack(fill="x", pady=8)
        self.info = ttk.Label(self, foreground="#555")
        self.info.pack(anchor="w")
        self.table = DataTable(self, height=14)
        self.table.pack(fill="both", expand=True)
        self.table.tree.bind("<Double-1>", self.show_history)

    def refresh(self):
        self.filters.refresh_departments()
        self.search()

    @safe_action
    def search(self):
        filt = self.filters.get_filters()
        low, high = self.app.get_thresholds()
        people = self.app.employees.search(self.query_var.get(), filt["department"],
                                           self.status_var.get())
        summary = analytics.employee_summary(
            self.app.attendance.get_all(), people, filt["start"], filt["end"],
            only_active=False, low=low, high=high)
        if self.level_var.get() != "All":
            summary = summary[summary["level"] == self.level_var.get()]
        self.result = summary.reset_index(drop=True)
        self.table.show(self.result, self.COLUMNS, tag_column="level")
        self.info.configure(
            text=f"{len(self.result)} employee(s) found for "
                 f"{analytics.period_label(filt['start'], filt['end'])}. "
                 "Double-click a row to see that employee's daily records.")

    def reset(self):
        self.query_var.set("")
        self.status_var.set("All")
        self.level_var.set("All")
        self.filters.reset()
        self.search()

    @safe_action
    def export(self):
        if self.result.empty:
            raise ValidationError("There are no results to export.")
        path = analytics.export_report_csv(self.result, "employee_search")
        messagebox.showinfo("Exported", f"Results saved to:\n{path}")

    @safe_action
    def show_history(self, _event=None):
        rows = self.table.selected_rows()
        if not rows:
            return
        filt = self.filters.get_filters()
        emp_id, name = rows[0]["employee_id"], rows[0]["name"]
        history = self.app.attendance.get_for_employee(emp_id, filt["start"], filt["end"])
        window = tk.Toplevel(self)
        window.title(f"Attendance records - {name} ({emp_id})")
        window.geometry("360x480")
        counts = history["status"].value_counts().to_dict()
        text = ", ".join(f"{status}: {counts.get(status, 0)}" for status in config.ATTENDANCE_STATUSES)
        ttk.Label(window, text=text or "No records in this period.", padding=8).pack(anchor="w")
        table = DataTable(window, height=18)
        table.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        table.show(history[["date", "status"]], tag_column="status")


class AnalyticsTab(ttk.Frame):
    PERSON_COLUMNS = ["employee_id", "name", "department", "Present", "Late", "Half-Day",
                      "Leave", "Absent", "working_days", "attendance_pct", "level"]

    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.filters = FilterBar(self, app, show_period_b=True, show_thresholds=True)
        self.filters.pack(fill="x")

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=8)
        for text, command in (("Low attendance", self.show_low),
                              ("High attendance", self.show_high),
                              ("Department comparison", self.show_departments),
                              ("Period comparison: departments", self.show_period_departments),
                              ("Period comparison: employees", self.show_period_employees),
                              ("Statistics", self.show_statistics)):
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=3)

        self.heading = ttk.Label(self, text="Choose an analysis above.", style="Heading.TLabel")
        self.heading.pack(anchor="w")
        self.info = ttk.Label(self, foreground="#555", wraplength=1000, justify="left")
        self.info.pack(anchor="w", pady=(0, 4))
        self.table = DataTable(self, height=16)
        self.table.pack(fill="both", expand=True)

    def refresh(self):
        self.filters.refresh_departments()

    def _show(self, heading, df, info="", columns=None, tag_column=None):
        self.heading.configure(text=heading)
        self.info.configure(text=info)
        self.table.show(df, columns, tag_column)

    def _summary(self):
        filt = self.filters.get_filters()
        low, high = self.app.get_thresholds()
        summary = analytics.employee_summary(
            self.app.attendance.get_all(), self.app.employees.get_all(),
            filt["start"], filt["end"], filt["department"], low=low, high=high)
        return summary, filt, low, high

    @safe_action
    def show_low(self):
        summary, filt, low, _ = self._summary()
        result = analytics.low_attendance(summary, low)
        self._show(f"Employees below {low:g}% attendance ({analytics.period_label(filt['start'], filt['end'])})",
                   result, f"{len(result)} of {len(summary)} active employees are below the threshold.",
                   self.PERSON_COLUMNS, "level")

    @safe_action
    def show_high(self):
        summary, filt, _, high = self._summary()
        result = analytics.high_attendance(summary, high)
        self._show(f"Employees with {high:g}% attendance or more ({analytics.period_label(filt['start'], filt['end'])})",
                   result, f"{len(result)} of {len(summary)} active employees reach the threshold.",
                   self.PERSON_COLUMNS, "level")

    @safe_action
    def show_departments(self):
        summary, filt, _, _ = self._summary()
        result = analytics.department_summary(summary)
        best = result.iloc[0]["department"] if not result.empty else "-"
        self._show(f"Department comparison ({analytics.period_label(filt['start'], filt['end'])})",
                   result, f"Best department: {best}. Attendance % is weighted by working days.")

    def _period_data(self):
        filt = self.filters.get_filters(require_periods=True)
        low, high = self.app.get_thresholds()
        return analytics.period_comparison(
            self.app.attendance.get_all(), self.app.employees.get_all(),
            filt["start"], filt["end"], filt["start_b"], filt["end_b"],
            filt["department"], low, high) + (filt,)

    @staticmethod
    def _period_text(overall, filt):
        return (f"Overall: A ({analytics.period_label(filt['start'], filt['end'])}) = "
                f"{overall['period_a']:.1f}%,  B ({analytics.period_label(filt['start_b'], filt['end_b'])}) = "
                f"{overall['period_b']:.1f}%,  change = {overall['change']:+.1f} points.")

    @safe_action
    def show_period_departments(self):
        _, depts, overall, filt = self._period_data()
        self._show("Period comparison by department", depts, self._period_text(overall, filt))

    @safe_action
    def show_period_employees(self):
        people, _, overall, filt = self._period_data()
        self._show("Period comparison by employee (biggest decline first)", people,
                   self._period_text(overall, filt), tag_column="trend")

    @safe_action
    def show_statistics(self):
        summary, filt, low, high = self._summary()
        stats = analytics.basic_statistics(summary, low, high)
        table = pd.DataFrame({"statistic": list(stats), "value": list(stats.values())})
        self._show(f"Attendance statistics ({analytics.period_label(filt['start'], filt['end'])})",
                   table, "Calculated with NumPy over each active employee's attendance %."
                   if stats else "No attendance data for these filters.")


class ReportsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.chart_var = tk.StringVar(value=visualization.CHART_TYPES[0])
        self.filters = FilterBar(self, app, show_period_b=True, show_thresholds=True)
        self.filters.pack(fill="x")

        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=8)
        ttk.Label(controls, text="Chart").pack(side="left")
        ttk.Combobox(controls, textvariable=self.chart_var, width=40, state="readonly",
                     values=visualization.CHART_TYPES).pack(side="left", padx=6)
        ttk.Button(controls, text="Generate", command=self.generate).pack(side="left", padx=3)
        ttk.Button(controls, text="Save chart as PNG", command=self.save_chart).pack(side="left", padx=3)
        ttk.Button(controls, text="Export employee report (CSV)",
                   command=self.export_csv).pack(side="left", padx=3)

        self.chart = ChartPanel(self)
        self.chart.pack(fill="both", expand=True)

    def refresh(self):
        self.filters.refresh_departments()

    @safe_action
    def generate(self):
        filt = self.filters.get_filters()
        low, high = self.app.get_thresholds()
        figure = visualization.create_chart(
            self.chart_var.get(), self.app.attendance.get_all(),
            self.app.employees.get_all(), filt, low, high)
        self.chart.show(figure)
        self.app.set_status(f"Generated: {self.chart_var.get()}")

    @safe_action
    def save_chart(self):
        if self.chart.figure is None:
            raise ValidationError("Generate a chart first.")
        path = visualization.save_figure(self.chart.figure, self.chart_var.get())
        messagebox.showinfo("Chart saved", f"Saved to:\n{path}")

    @safe_action
    def export_csv(self):
        filt = self.filters.get_filters()
        low, high = self.app.get_thresholds()
        summary = analytics.employee_summary(
            self.app.attendance.get_all(), self.app.employees.get_all(),
            filt["start"], filt["end"], filt["department"], low=low, high=high)
        path = analytics.export_report_csv(summary, "attendance_report")
        messagebox.showinfo("Report exported", f"Saved to:\n{path}")


# ================================================================== main app
class AttendanceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Employee Attendance Analysis & Management System")
        self.geometry("1200x780")
        self.minsize(1000, 650)

        self.employees = EmployeeManager()
        self.attendance = AttendanceManager()
        self.low_var = tk.StringVar(value=f"{config.LOW_THRESHOLD:g}")
        self.high_var = tk.StringVar(value=f"{config.HIGH_THRESHOLD:g}")
        self.status_text = tk.StringVar(value="Ready.")
        self._build_styles()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)
        self.tabs = {}
        for title, tab_class in (("Dashboard", DashboardTab), ("Employees", EmployeesTab),
                                 ("Attendance", AttendanceTab), ("Search & Filter", SearchTab),
                                 ("Analytics", AnalyticsTab), ("Reports", ReportsTab)):
            self.tabs[title] = tab_class(self.notebook, self)
            self.notebook.add(self.tabs[title], text=f"  {title}  ")
        ttk.Label(self, textvariable=self.status_text, relief="sunken",
                  anchor="w", padding=3).pack(fill="x", side="bottom")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.after(100, self.tabs["Dashboard"].refresh)

    def _build_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Card.TFrame", background="#eef3fa", relief="solid", borderwidth=1)
        style.configure("CardValue.TLabel", background="#eef3fa", foreground="#1f3a5f",
                        font=("Helvetica", 18, "bold"))
        style.configure("CardCaption.TLabel", background="#eef3fa", foreground="#555")
        style.configure("Heading.TLabel", font=("Helvetica", 12, "bold"))
        style.configure("Treeview", rowheight=24)

    def _on_tab_changed(self, _event=None):
        self.nametowidget(self.notebook.select()).refresh()

    def set_status(self, message):
        self.status_text.set(message)

    def get_thresholds(self):
        """Validated (low, high) thresholds typed by the user."""
        low = parse_percentage(self.low_var.get(), "Low threshold")
        high = parse_percentage(self.high_var.get(), "High threshold")
        validate_thresholds(low, high)
        return low, high

    def safe_thresholds(self):
        """Like get_thresholds, but falls back to the defaults on bad input."""
        try:
            return self.get_thresholds()
        except ValidationError:
            return config.LOW_THRESHOLD, config.HIGH_THRESHOLD
