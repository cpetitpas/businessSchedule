import pandas as pd
from datetime import datetime
import logging
from tkinter import messagebox

def load_csv(emp_file, req_file, limits_file, start_date, num_weeks_var):
    logging.debug("Entering load_csv with emp_file=%s, req_file=%s, limits_file=%s", emp_file, req_file, limits_file)
    invalid_dates = []
    try:
        emp_df = pd.read_csv(emp_file, index_col=0)
        emp_df.index = emp_df.index.astype(str).str.strip().str.lower()
        logging.debug("Employee Data CSV loaded: %s", emp_df.to_string())
        if emp_df.index.isna().any() or "" in emp_df.index:
            logging.error("Employee_Data.csv has invalid or missing index values")
            raise ValueError("Employee_Data.csv has invalid or missing index values")
        employees = [col for col in emp_df.columns if pd.notna(col) and isinstance(col, str) and col.strip()]
        if not employees:
            logging.error("No valid employee columns found in Employee_Data.csv")
            raise ValueError("No valid employee columns found in Employee_Data.csv")
        logging.debug("Employees: %s", employees)
        
        work_areas = {}
        area_row = "work area"
        if area_row not in emp_df.index:
            logging.error("Cannot find 'Work Area' row in Employee_Data.csv")
            raise ValueError("Cannot find 'Work Area' row in Employee_Data.csv")
        areas = ["Bar", "Kitchen"]
        for emp in employees:
            area = emp_df.loc[area_row, emp]
            if pd.notna(area) and area in areas:
                work_areas[emp] = [area]
            else:
                logging.error("Invalid work area for %s: %s", emp, area)
                raise ValueError(f"Invalid work area for {emp}: {area}")
        logging.debug("Work areas: %s", work_areas)
        
        # Load shifts from Hard_Limits.csv
        limits_df = pd.read_csv(limits_file)
        logging.debug("Hard Limits CSV loaded: %s", limits_df.to_string())
        if limits_df.empty:
            logging.error("Hard_Limits.csv is empty")
            raise ValueError("Hard_Limits.csv is empty")
        if "Shifts" not in limits_df.columns:
            logging.error("Shifts column missing in Hard_Limits.csv")
            raise ValueError("Shifts column missing in Hard_Limits.csv")
        shift_str = limits_df["Shifts"].iloc[0]
        if pd.isna(shift_str):
            logging.error("Shifts column is empty in Hard_Limits.csv")
            raise ValueError("Shifts column is empty in Hard_Limits.csv")
        shifts = [s.strip() for s in shift_str.split(",")]
        if not shifts:
            logging.error("No valid shifts found in Hard_Limits.csv")
            raise ValueError("No valid shifts found in Hard_Limits.csv")
        logging.debug("Shifts: %s", shifts)
        
        shift_prefs = {}
        shift_row = "shift weight"
        if shift_row not in emp_df.index:
            logging.error("Cannot find 'Shift Weight' row in Employee_Data.csv")
            raise ValueError("Cannot find 'Shift Weight' row in Employee_Data.csv")
        for emp in employees:
            shift = emp_df.loc[shift_row, emp]
            shift_prefs[emp] = {s: 0 for s in shifts}
            if pd.notna(shift):
                shift = str(shift).strip().lower()
                if shift in [s.lower() for s in shifts]:
                    shift_prefs[emp][next(s for s in shifts if s.lower() == shift)] = 10
                else:
                    logging.warning("Invalid shift '%s' for %s, assuming no preference", shift, emp)
                    print(f"Warning: Invalid shift '{shift}' for {emp}, assuming no preference")
            logging.debug("Shift preferences for %s: %s", emp, shift_prefs[emp])
        
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        day_prefs = {}
        day_row = "day weights"
        if day_row not in emp_df.index:
            logging.error("Cannot find 'Day Weights' row in Employee_Data.csv")
            raise ValueError("Cannot find 'Day Weights' row in Employee_Data.csv")
        for emp in employees:
            day_str = emp_df.loc[day_row, emp]
            preferred_days = []
            if pd.notna(day_str):
                try:
                    preferred_days = [d.strip() for d in str(day_str).split(", ")]
                    invalid_days = [d for d in preferred_days if d not in days]
                    if invalid_days:
                        logging.warning("Invalid days for %s: %s, ignoring them", emp, invalid_days)
                        print(f"Warning: Invalid days for {emp}: {invalid_days}, ignoring them")
                        preferred_days = [d for d in preferred_days if d in days]
                except Exception as e:
                    logging.warning("Failed to parse day weights for %s: %s", emp, str(e))
                    print(f"Warning: Failed to parse day weights for {emp}: {str(e)}")
                    preferred_days = []
            day_prefs[emp] = {d: 10 if d in preferred_days else 0 for d in days}
        
        must_off = {}
        must_off_row = "must have off"
        if must_off_row in emp_df.index:
            for emp in employees:
                off_str = emp_df.loc[must_off_row, emp]
                if pd.notna(off_str):
                    try:
                        off_dates = [(emp, d.strip()) for d in str(off_str).split(", ")]
                        for e, d in off_dates:
                            try:
                                datetime.strptime(d, "%m/%d/%Y")
                            except ValueError:
                                invalid_dates.append(f"{e}: {d}")
                        must_off[emp] = off_dates
                    except Exception as e:
                        logging.warning("Failed to parse must-off for %s: %s", emp, str(e))
                        print(f"Warning: Failed to parse must-off for {emp}: {str(e)}")
        if invalid_dates:
            messagebox.showwarning("Invalid Dates", "Invalid must-off dates detected:\n" + "\n".join(invalid_dates))
        logging.debug("Must-off: %s", must_off)
        
        min_shifts = {}
        min_shifts_row = "min shifts per week"
        if min_shifts_row not in emp_df.index:
            logging.error("Cannot find 'Min Shifts per Week' row in Employee_Data.csv")
            raise ValueError("Cannot find 'Min Shifts per Week' row in Employee_Data.csv")
        for emp in employees:
            try:
                min_shifts[emp] = int(emp_df.loc[min_shifts_row, emp])
            except (ValueError, TypeError):
                logging.warning("Invalid min shifts for %s, assuming 0", emp)
                print(f"Warning: Invalid min shifts for {emp}, assuming 0")
                min_shifts[emp] = 0
        logging.debug("Min shifts: %s", min_shifts)
        
        max_shifts = {}
        max_shifts_row = "max shifts per week"
        if max_shifts_row not in emp_df.index:
            logging.error("Cannot find 'Max Shifts per Week' row in Employee_Data.csv")
            raise ValueError("Cannot find 'Max Shifts per Week' row in Employee_Data.csv")
        for emp in employees:
            try:
                max_shifts[emp] = int(emp_df.loc[max_shifts_row, emp])
            except (ValueError, TypeError):
                logging.warning("Invalid max shifts for %s, assuming 7", emp)
                print(f"Warning: Invalid max shifts for {emp}, assuming 7")
                max_shifts[emp] = 7
        logging.debug("Max shifts: %s", max_shifts)
        
        max_weekend_days = {}
        max_weekend_row = "max number of weekend days"
        if max_weekend_row not in emp_df.index:
            logging.error("Cannot find 'Max Number of Weekend Days' row in Employee_Data.csv")
            raise ValueError("Cannot find 'Max Number of Weekend Days' row in Employee_Data.csv")
        for emp in employees:
            try:
                max_weekend_days[emp] = int(emp_df.loc[max_weekend_row, emp])
            except (ValueError, TypeError):
                logging.warning("Invalid max weekend days for %s, assuming 2", emp)
                print(f"Warning: Invalid max weekend days for {emp}, assuming 2")
                max_weekend_days[emp] = 2
        logging.debug("Max weekend days: %s", max_weekend_days)
        
        req_df = pd.read_csv(req_file, index_col=0)
        logging.debug("Personel Required CSV loaded: %s", req_df.to_string())
        if req_df.index.isna().any() or "" in req_df.index:
            logging.error("Personel_Required.csv has invalid or missing index values")
            raise ValueError("Personel_Required.csv has invalid or missing index values")
        required = {}
        for day in days:
            required[day] = {}
            for area in areas:
                counts = req_df.loc[area, day].split("/") if pd.notna(req_df.loc[area, day]) else ["0"] * len(shifts)
                if len(counts) != len(shifts):
                    logging.error("Invalid number of shift counts for %s on %s: expected %d, got %d", area, day, len(shifts), len(counts))
                    raise ValueError(f"Invalid number of shift counts for {area} on {day}: expected {len(shifts)}, got {len(counts)}")
                try:
                    required[day][area] = {shifts[i]: int(count) for i, count in enumerate(counts)}
                except (IndexError, ValueError):
                    logging.error("Invalid staffing requirement for %s on %s: %s", area, day, req_df.loc[area, day])
                    raise ValueError(f"Invalid staffing requirement for {area} on {day}")
        logging.debug("Required staffing: %s", required)
        
        constraints = {
            "max_shifts_per_day": 1,
            "violate_order": ["Day Weights", "Shift Weight", "Max Number of Weekend Days", "Min Shifts per Week"]
        }
        try:
            if "Max Number of Shifts per Day" in limits_df.columns:
                value = limits_df["Max Number of Shifts per Day"].iloc[0]
                if pd.notna(value):
                    constraints["max_shifts_per_day"] = int(value)
                else:
                    logging.warning("Max Number of Shifts per Day is empty, using default (1)")
                    print("Warning: Max Number of Shifts per Day is empty, using default (1)")
            else:
                logging.warning("Max Number of Shifts per Day column missing, using default (1)")
                print("Warning: Max Number of Shifts per Day column missing, using default (1)")
                
            if "Violate Rules Order" in limits_df.columns:
                value = limits_df["Violate Rules Order"].iloc[0]
                if pd.notna(value) and isinstance(value, str):
                    constraints["violate_order"] = [v.strip() for v in value.split(", ")]
                else:
                    logging.warning("Violate Rules Order is invalid or empty, using default order")
                    print("Warning: Violate Rules Order is invalid or empty, using default order")
            else:
                logging.warning("Violate Rules Order column missing, using default order")
                print("Warning: Violate Rules Order column missing, using default order")
        except Exception as e:
            logging.warning("Error parsing Hard_Limits.csv: %s", str(e))
            print(f"Warning: Error parsing Hard_Limits.csv ({str(e)}), using default constraints")
        logging.debug("Constraints: %s", constraints)
        
        logging.debug("Exiting load_csv")
        return employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days
    except Exception as e:
        logging.error("Failed to load CSV files: %s", str(e))
        messagebox.showerror("Error", f"Failed to load CSV files: {str(e)}")
        return None