# Employee Attendance Analysis & Management System

A desktop application for an HR user to maintain employee and attendance records,
find irregular attendance, and compare departments and time periods.
Built with **Python, Tkinter, Pandas, NumPy and Matplotlib**, with CSV files for storage.

## Run it

```bash
pip install -r requirements.txt      # pandas, numpy, matplotlib
python main.py
```

Tkinter ships with Python. On Linux you may need `sudo apt install python3-tk`.
Sample data (24 employees, 6 departments, Apr-Sep 2026) is already in `data/`.
To reset it: `python generate_sample_data.py` (overwrites the CSV files).
Run the tests with `python -m unittest discover -s tests -v`.

## Project structure

```text
attendance_project/
├── main.py                   entry point
├── gui.py                    all Tkinter windows (tabs, tables, forms)
├── employee_manager.py       employee CRUD, search, filters   (EmployeeManager)
├── attendance_manager.py     attendance records              (AttendanceManager)
├── analytics.py              Pandas/NumPy calculations
├── visualization.py          Matplotlib charts (return Figure objects)
├── validators.py             input validation + ValidationError
├── config.py                 file paths, statuses, thresholds
├── generate_sample_data.py   creates the sample CSV files
├── data/employees.csv, attendance.csv
├── reports/                  exported PNG charts and CSV reports
└── tests/                    unittest test suite (19 tests)
```

The GUI contains no calculations: it collects input, calls the other modules and
displays the result.

## How attendance is calculated

| Status | Counts as |
|---|---|
| Present, Late | 1 day attended |
| Half-Day | 0.5 day attended |
| Absent | 0 days attended |
| Leave (approved) | not counted at all (excluded from working days) |

`Attendance % = attended days / working days x 100`

Levels (thresholds can be changed in the Analytics/Reports/Search tabs; defaults 75 and 90):
**Low** < 75 %, **High** >= 90 %, otherwise **Average**; no records = **No Data**.
Department percentages are weighted by working days (total attended / total working),
not an average of employee averages. Analysis views cover **active** employees only;
the Search tab can also show inactive ones.

## Using the application

| Tab | What it does |
|---|---|
| **Dashboard** | Key numbers (active staff, overall %, low/high counts, last recorded day), department bar chart, status pie chart |
| **Employees** | Add, update, delete employees. Click a row to edit it. IDs (E001...) are generated automatically |
| **Attendance** | Pick a date, select employees (Ctrl/Shift+click for several) and click a status. "Mark all unmarked as Present" is a shortcut |
| **Search & Filter** | Text search plus department, employment status, attendance level and date range. Double-click a row for that employee's daily records. Export results to CSV |
| **Analytics** | Low / high attendance lists, department comparison, **period comparison** (Period A vs Period B, by department and by employee), descriptive statistics |
| **Reports** | 7 chart types, Save as PNG, export an employee report as CSV (both go to `reports/`) |

Dates are typed as `YYYY-MM-DD`. Attendance cannot be marked for future dates.

## Where each assignment requirement is demonstrated

| Requirement | Where |
|---|---|
| Functions, loops, conditionals | every module, e.g. `analytics.employee_summary`, `generate_sample_data.build_tables` |
| Lists, dictionaries, tuples | status lists in `config.py`; `{employee_id: status}` dicts in `AttendanceManager.mark_many`; tuples returned by `analytics.period_comparison` and `EmployeeManager._clean_fields` |
| File handling (CSV) | `EmployeeManager._load/save`, `AttendanceManager._load/save`, `analytics.export_report_csv` |
| Exception handling | `FileNotFoundError`/`EmptyDataError` on load; `ValidationError` everywhere; the `safe_action` decorator in `gui.py` turns errors into message boxes |
| Input validation | `validators.py` (names, emails, real calendar dates, no future dates, 0-100 thresholds, low < high, unique email, valid status, existing employee ID) |
| Pandas | `groupby`, `merge`, `agg`, `unstack`, boolean filtering, `pd.to_datetime` in `analytics.py` and the managers |
| NumPy | `np.select` (levels, trends), `np.divide(..., where=)` (safe percentages), `np.mean/median/std/percentile` in `basic_statistics`, `np.where`, `np.arange` in charts |
| User-defined modules (8) | `config`, `validators`, `employee_manager`, `attendance_manager`, `analytics`, `visualization`, `gui`, `main` |
| Tkinter GUI | `gui.py`: Notebook with 6 tabs, Treeview tables, forms, comboboxes, message boxes, embedded Matplotlib charts |

## Data files

`data/employees.csv`: `employee_id, name, department, designation, email, join_date, status`
`data/attendance.csv`: `employee_id, date, status` (one row per employee per day;
marking a day again overwrites the previous record).

## Possible extensions

Calendar date picker, weekend/holiday handling, late-arrival minutes, PDF reports, user login.
