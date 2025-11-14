import pandas as pd
from datetime import datetime
import logging
from tkinter import messagebox

def load_csv(emp_file, req_file, limits_file, start_date, num_weeks_var):
    logging.debug("Entering load_csv with emp_file=%s, req_file=%s, limits_file=%s", emp_file, req_file, limits_file)
    invalid_dates = []
    try:
        # === Load Employee Data ===
        emp_df = pd.read_csv(emp_file, index_col=0)
        emp_df.index = emp_df.index.astype(str).str.strip().str.lower()
        logging.debug("Employee Data CSV loaded: %s", emp_df.to_string())

        if emp_df.index.isna().any() or "" in emp_df.index:
            raise ValueError("Employee_Data.csv has invalid or missing index values")

        employees = [col for col in emp_df.columns if pd.notna(col) and isinstance(col, str) and col.strip()]
        if not employees:
            raise ValueError("No valid employee columns found in Employee_Data.csv")
        logging.debug("Employees: %s", employees)

        # === Load Hard Limits (to get Shifts & Work Areas) ===
        limits_df = pd.read_csv(limits_file)
        logging.debug("Hard Limits CSV loaded: %s", limits_df.to_string())
        if limits_df.empty:
            raise ValueError("Hard_Limits.csv is empty")

        # ---- Shifts ----
        if "Shifts" not in limits_df.columns:
            raise ValueError("Shifts column missing in Hard_Limits.csv")
        shift_str = limits_df["Shifts"].iloc[0]
        if pd.isna(shift_str):
            raise ValueError("Shifts column is empty in Hard_Limits.csv")
        shifts = [s.strip() for s in shift_str.split(",")]
        if not shifts:
            raise ValueError("No valid shifts found in Hard_Limits.csv")
        logging.debug("Shifts: %s", shifts)

        # ---- Work Areas (DYNAMIC) ----
        if "Work Areas" not in limits_df.columns:
            raise ValueError("Work Areas column missing in Hard_Limits.csv")
        areas_str = limits_df["Work Areas"].iloc[0]
        if pd.isna(areas_str):
            raise ValueError("Work Areas column is empty in Hard_Limits.csv")
        areas = [a.strip() for a in areas_str.split(",")]
        if not areas:
            raise ValueError("No valid work areas found in Hard_Limits.csv")
        logging.debug("Work Areas: %s", areas)

        # === Employee Work Area Assignment (Hard Constraint) ===
        work_areas = {}
        area_row = "work area"
        if area_row not in emp_df.index:
            raise ValueError("Cannot find 'Work Area' row in Employee_Data.csv")
        for emp in employees:
            area = str(emp_df.loc[area_row, emp]).strip()
            if pd.notna(area) and area in areas:
                work_areas[emp] = [area]
            else:
                raise ValueError(f"Invalid or missing work area for {emp}: '{area}' (valid: {areas})")
        logging.debug("Work areas: %s", work_areas)

        # === Shift Preferences ===
        shift_prefs = {}
        shift_row = "preferred shift"
        if shift_row not in emp_df.index:
            raise ValueError("Cannot find 'Preferred Shift' row in Employee_Data.csv")
        for emp in employees:
            shift = str(emp_df.loc[shift_row, emp]).strip().lower()
            shift_prefs[emp] = {s: 0 for s in shifts}
            if pd.notna(shift) and shift:
                matched = next((s for s in shifts if s.lower() == shift), None)
                if matched:
                    shift_prefs[emp][matched] = 10
                else:
                    logging.warning("Invalid shift preference '%s' for %s", shift, emp)
        logging.debug("Shift preferences: %s", shift_prefs)

        # === Day Preferences ===
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        day_prefs = {}
        day_row = "preferred days"
        if day_row not in emp_df.index:
            raise ValueError("Cannot find 'Preferred Days' row in Employee_Data.csv")
        for emp in employees:
            day_str = emp_df.loc[day_row, emp]
            preferred_days = []
            if pd.notna(day_str):
                try:
                    preferred_days = [d.strip() for d in str(day_str).split(", ")]
                    preferred_days = [d for d in preferred_days if d in days]
                except Exception as e:
                    logging.warning("Failed to parse preferred days for %s: %s", emp, str(e))
            day_prefs[emp] = {d: 10 if d in preferred_days else 0 for d in days}

        # === Must-Off Dates ===
        must_off = {}
        must_off_row = "must have off"
        if must_off_row in emp_df.index:
            for emp in employees:
                off_str = emp_df.loc[must_off_row, emp]
                if pd.notna(off_str):
                    try:
                        off_dates = [(emp, d.strip()) for d in str(off_str).split(", ")]
                        for _, d in off_dates:
                            try:
                                datetime.strptime(d, "%m/%d/%Y")
                            except ValueError:
                                invalid_dates.append(f"{emp}: {d}")
                        must_off[emp] = off_dates
                    except Exception as e:
                        logging.warning("Failed to parse must-off for %s: %s", emp, str(e))
        if invalid_dates:
            messagebox.showwarning("Invalid Dates", "Invalid must-off dates:\n" + "\n".join(invalid_dates))

        # === Min/Max Shifts per Week ===
        def safe_int(val, default, name, emp):
            try:
                return int(val)
            except (ValueError, TypeError):
                logging.warning("Invalid %s for %s, using %d", name, emp, default)
                return default

        min_shifts = {}
        min_row = "min shifts per week"
        if min_row not in emp_df.index:
            raise ValueError("Cannot find 'Min Shifts per Week' row")
        for emp in employees:
            min_shifts[emp] = safe_int(emp_df.loc[min_row, emp], 0, "min shifts", emp)

        max_shifts = {}
        max_row = "max shifts per week"
        if max_row not in emp_df.index:
            raise ValueError("Cannot find 'Max Shifts per Week' row")
        for emp in employees:
            max_shifts[emp] = safe_int(emp_df.loc[max_row, emp], 7, "max shifts", emp)

        max_weekend_days = {}
        weekend_row = "max number of weekend days"
        if weekend_row not in emp_df.index:
            raise ValueError("Cannot find 'Max Number of Weekend Days' row")
        for emp in employees:
            max_weekend_days[emp] = safe_int(emp_df.loc[weekend_row, emp], 2, "max weekend days", emp)

        # === Personnel Required (must have row per area) ===
        req_df = pd.read_csv(req_file, index_col=0)
        logging.debug("Personnel Required CSV loaded: %s", req_df.to_string())

        if req_df.index.isna().any() or "" in req_df.index:
            raise ValueError("Personnel_Required.csv has invalid or missing index")

        required = {}
        for day in days:
            required[day] = {}
            for area in areas:
                if area not in req_df.index:
                    raise ValueError(f"Missing row for work area '{area}' in Personnel_Required.csv")
                cell = req_df.loc[area, day]
                counts = cell.split("/") if pd.notna(cell) else ["0"] * len(shifts)
                if len(counts) != len(shifts):
                    raise ValueError(f"Expected {len(shifts)} shift counts for {area} on {day}, got {len(counts)}")
                required[day][area] = {shifts[i]: int(c.strip()) for i, c in enumerate(counts)}

        # === Constraints ===
        constraints = {
            "max_shifts_per_day": 1,
            "violate_order": ["Preferred Days", "Preferred Shift", "Max Number of Weekend Days", "Min Shifts per Week"]
        }

        if "Max Number of Shifts per Day" in limits_df.columns:
            val = limits_df["Max Number of Shifts per Day"].iloc[0]
            if pd.notna(val):
                constraints["max_shifts_per_day"] = int(val)

        if "Violate Rules Order" in limits_df.columns:
            val = limits_df["Violate Rules Order"].iloc[0]
            if pd.notna(val) and isinstance(val, str):
                constraints["violate_order"] = [v.strip() for v in val.split(", ")]

        logging.debug("Constraints: %s", constraints)

        return (
            employees, days, shifts, areas, shift_prefs, day_prefs, must_off,
            required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days
        )

    except Exception as e:
        logging.error("Failed to load CSV files: %s", str(e))
        messagebox.showerror("Error", f"Failed to load CSV files: {str(e)}")
        return None