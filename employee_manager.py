"""Employee records: load/save, add, update, delete, search and filter."""

import re
from pathlib import Path

import pandas as pd

from config import (DEFAULT_DEPARTMENTS, EMPLOYEE_COLUMNS, EMPLOYEE_STATUSES,
                    EMPLOYEES_FILE)
from validators import (ValidationError, parse_date, validate_choice,
                        validate_email, validate_name, validate_required_text)


class EmployeeManager:
    """Keeps the employee table in a DataFrame and persists it to a CSV file."""

    def __init__(self, filepath=EMPLOYEES_FILE):
        self.filepath = Path(filepath)
        self.df = self._load()

    # ---------- file handling ----------
    def _load(self):
        try:
            df = pd.read_csv(self.filepath, dtype=str, keep_default_na=False)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            df = pd.DataFrame(columns=EMPLOYEE_COLUMNS)
        for column in EMPLOYEE_COLUMNS:          # tolerate older/partial files
            if column not in df.columns:
                df[column] = ""
        return df[EMPLOYEE_COLUMNS].reset_index(drop=True)

    def save(self):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(self.filepath, index=False)

    # ---------- helpers ----------
    def generate_id(self):
        """Next free ID in the form E001, E002, ..."""
        numbers = [int(emp_id[1:]) for emp_id in self.df["employee_id"]
                   if re.fullmatch(r"E\d+", emp_id)]
        return f"E{max(numbers, default=0) + 1:03d}"

    def _clean_fields(self, name, department, designation, email, join_date, status):
        """Validate every field and return them as a tuple (in column order)."""
        return (validate_name(name),
                validate_required_text(department, "Department", 30),
                validate_required_text(designation, "Designation", 40),
                validate_email(email),
                parse_date(join_date, "Join date", allow_future=False),
                validate_choice(status, EMPLOYEE_STATUSES, "Status"))

    def _email_in_use(self, email, ignore_id=None):
        same = self.df["email"].str.lower() == email
        if ignore_id is not None:
            same &= self.df["employee_id"] != ignore_id
        return bool(same.any())

    def _index_of(self, emp_id):
        matches = self.df.index[self.df["employee_id"] == emp_id]
        if len(matches) == 0:
            raise ValidationError(f"Employee {emp_id!r} does not exist.")
        return matches[0]

    # ---------- CRUD ----------
    def add_employee(self, name, department, designation, email, join_date,
                     status="Active"):
        cleaned = self._clean_fields(name, department, designation, email,
                                     join_date, status)
        if self._email_in_use(cleaned[3]):
            raise ValidationError("Another employee already uses this email address.")
        emp_id = self.generate_id()
        row = dict(zip(EMPLOYEE_COLUMNS, (emp_id,) + cleaned))
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
        self.save()
        return emp_id

    def update_employee(self, emp_id, name, department, designation, email,
                        join_date, status):
        index = self._index_of(emp_id)
        cleaned = self._clean_fields(name, department, designation, email,
                                     join_date, status)
        if self._email_in_use(cleaned[3], ignore_id=emp_id):
            raise ValidationError("Another employee already uses this email address.")
        for column, value in zip(EMPLOYEE_COLUMNS[1:], cleaned):
            self.df.at[index, column] = value
        self.save()

    def delete_employee(self, emp_id):
        index = self._index_of(emp_id)
        removed = self.df.loc[index].to_dict()
        self.df = self.df.drop(index).reset_index(drop=True)
        self.save()
        return removed

    # ---------- queries ----------
    def get_all(self):
        return self.df.copy()

    def get_employee(self, emp_id):
        match = self.df[self.df["employee_id"] == emp_id]
        return None if match.empty else match.iloc[0].to_dict()

    def ids(self):
        return set(self.df["employee_id"])

    def departments(self, include_defaults=False):
        names = {d for d in self.df["department"] if d}
        if include_defaults:
            names |= set(DEFAULT_DEPARTMENTS)
        return sorted(names)

    def search(self, query="", department="All", status="All"):
        """Text search over id/name/email/designation plus dropdown filters."""
        result = self.df
        query = query.strip().lower()
        if query:
            mask = pd.Series(False, index=result.index)
            for column in ("employee_id", "name", "email", "designation"):
                mask |= result[column].str.lower().str.contains(query, regex=False)
            result = result[mask]
        if department not in ("", "All"):
            result = result[result["department"] == department]
        if status not in ("", "All"):
            result = result[result["status"] == status]
        return result.reset_index(drop=True)
