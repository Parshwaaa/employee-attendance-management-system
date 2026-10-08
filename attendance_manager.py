"""Attendance records: one row per employee per day, stored in a CSV file."""

from pathlib import Path

import pandas as pd

from config import ATTENDANCE_COLUMNS, ATTENDANCE_FILE, ATTENDANCE_STATUSES
from validators import ValidationError, parse_date, validate_choice


class AttendanceManager:
    def __init__(self, filepath=ATTENDANCE_FILE):
        self.filepath = Path(filepath)
        self.df = self._load()

    # ---------- file handling ----------
    def _load(self):
        try:
            df = pd.read_csv(self.filepath, dtype=str, keep_default_na=False)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            df = pd.DataFrame(columns=ATTENDANCE_COLUMNS)
        for column in ATTENDANCE_COLUMNS:
            if column not in df.columns:
                df[column] = ""
        df = df[ATTENDANCE_COLUMNS]
        # an employee can only have one record per day - keep the latest one
        df = df.drop_duplicates(subset=["employee_id", "date"], keep="last")
        return df.reset_index(drop=True)

    def save(self):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(self.filepath, index=False)

    # ---------- marking ----------
    def mark_many(self, date_text, marks, valid_ids=None):
        """Insert or overwrite attendance for one day.

        marks: dict {employee_id: status}. Returns the number of records saved.
        """
        date_text = parse_date(date_text, "Attendance date", allow_future=False)
        if not marks:
            raise ValidationError("There is nothing to mark.")
        rows = []
        for emp_id, status in marks.items():
            validate_choice(status, ATTENDANCE_STATUSES, "Attendance status")
            if valid_ids is not None and emp_id not in valid_ids:
                raise ValidationError(f"Employee {emp_id!r} does not exist.")
            rows.append({"employee_id": emp_id, "date": date_text, "status": status})

        replace = (self.df["date"] == date_text) & self.df["employee_id"].isin(list(marks))
        kept = self.df[~replace]
        self.df = (pd.concat([kept, pd.DataFrame(rows)], ignore_index=True)
                   .sort_values(["date", "employee_id"]).reset_index(drop=True))
        self.save()
        return len(rows)

    def mark(self, emp_id, date_text, status, valid_ids=None):
        return self.mark_many(date_text, {emp_id: status}, valid_ids)

    # ---------- removing ----------
    def remove_marks(self, date_text, emp_ids):
        date_text = parse_date(date_text, "Attendance date")
        remove = (self.df["date"] == date_text) & self.df["employee_id"].isin(list(emp_ids))
        count = int(remove.sum())
        if count:
            self.df = self.df[~remove].reset_index(drop=True)
            self.save()
        return count

    def delete_employee_records(self, emp_id):
        remove = self.df["employee_id"] == emp_id
        count = int(remove.sum())
        if count:
            self.df = self.df[~remove].reset_index(drop=True)
            self.save()
        return count

    # ---------- queries ----------
    def get_all(self):
        return self.df.copy()

    def get_for_date(self, date_text):
        """Return {employee_id: status} for one day."""
        date_text = parse_date(date_text, "Attendance date")
        day = self.df[self.df["date"] == date_text]
        return dict(zip(day["employee_id"], day["status"]))

    def get_for_employee(self, emp_id, start=None, end=None):
        records = self.df[self.df["employee_id"] == emp_id]
        if start:
            records = records[records["date"] >= start]
        if end:
            records = records[records["date"] <= end]
        return records.sort_values("date").reset_index(drop=True)

    def count_for_employee(self, emp_id):
        return int((self.df["employee_id"] == emp_id).sum())

    def date_range(self):
        """(first_date, last_date) as strings, or (None, None) if empty."""
        if self.df.empty:
            return None, None
        return self.df["date"].min(), self.df["date"].max()
