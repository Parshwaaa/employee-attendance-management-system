"""Project-wide constants (file locations, allowed values, thresholds)."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
EMPLOYEES_FILE = DATA_DIR / "employees.csv"
ATTENDANCE_FILE = DATA_DIR / "attendance.csv"

DATE_FORMAT = "%Y-%m-%d"

EMPLOYEE_COLUMNS = ["employee_id", "name", "department", "designation",
                    "email", "join_date", "status"]
ATTENDANCE_COLUMNS = ["employee_id", "date", "status"]

EMPLOYEE_STATUSES = ["Active", "Inactive"]
ATTENDANCE_STATUSES = ["Present", "Late", "Half-Day", "Leave", "Absent"]

# How much each attendance status counts towards attendance %.
# "Leave" (approved leave) is not listed: those days are excluded from the
# working-day total, so they neither help nor hurt the percentage.
STATUS_WEIGHTS = {"Present": 1.0, "Late": 1.0, "Half-Day": 0.5, "Absent": 0.0}

DEFAULT_DEPARTMENTS = ["Finance", "HR", "IT", "Marketing", "Operations", "Sales"]

# Employees below LOW are "Low", at or above HIGH are "High", the rest "Average".
LOW_THRESHOLD = 75.0
HIGH_THRESHOLD = 90.0


def ensure_directories():
    """Create the data and reports folders if they do not exist yet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
