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
        employees = [col for col in emp_df.columns if pd.notna(col)]
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
        
        shift_prefs = {}
        shift_row = "shift weight"
        if shift_row not in emp_df.index:
            logging.error("Cannot find 'Shift Weight' row in Employee_Data.csv")
            raise ValueError("Cannot find 'Shift Weight' row in Employee_Data.csv")
        for emp in employees:
            shift = emp_df.loc[shift_row, emp]
            if pd.isna(shift):
                shift_prefs[emp] = {"Morning": 0, "Evening": 0}
            else:
                shift = str(shift).strip().lower()
                if shift not in ["morning", "evening"]:
                    logging.warning("Invalid shift '%s' for %s, assuming no preference", shift, emp)
                    print(f"Warning: Invalid shift '{shift}' for {emp}, assuming no preference")
                    shift_prefs[emp] = {"Morning": 0, "Evening": 0}
                else:
                    shift_prefs[emp] = {
                        "Morning": 10 if shift == "morning" else 0,
                        "Evening": 10 if shift == "evening" else 0
                    }
        logging.debug("Shift preferences: %s", shift_prefs)
        
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
                        logging.warning("Invalid days %s for %s, ignoring them", invalid_days, emp)
                        print(f"Warning: Invalid days {invalid_days} for {emp}, ignoring them")
                        preferred_days = [d for d in preferred_days if d in days]
                except:
                    logging.warning("Failed to parse day preferences for %s, assuming none", emp)
                    print(f"Warning: Failed to parse day preferences for {emp}, assuming none")
            day_prefs[emp] = {day: 10 if day in preferred_days else 0 for day in days}
        logging.debug("Day preferences: %s", day_prefs)
        
        must_off = {}
        off_row = "must have off"
        if off_row not in emp_df.index:
            logging.warning("Cannot find 'Must have off' row, assuming none")
            print("Warning: Cannot find 'Must have off' row, assuming none")
        else:
            for emp in employees:
                off_dates_str = emp_df.loc[off_row, emp]
                if pd.notna(off_dates_str):
                    off_dates = [d.strip() for d in str(off_dates_str).split(',')]
                    must_off[emp] = []
                    for date_str in off_dates:
                        try:
                            # Try parsing date with flexible parsing
                            off_date = pd.to_datetime(date_str, errors='coerce')
                            if pd.isna(off_date):
                                logging.warning("Failed to parse date '%s' for %s", date_str, emp)
                                invalid_dates.append(f"{emp}: {date_str}")
                                continue
                            # Convert to datetime.date for consistency
                            off_date = off_date.date()
                            logging.debug("Parsed date '%s' as %s for %s", date_str, off_date.strftime('%Y-%m-%d'), emp)
                            delta = (off_date - start_date).days
                            if 0 <= delta < 7 * num_weeks_var.get():
                                must_off[emp].append((delta % 7, off_date.strftime("%Y-%m-%d")))
                        except Exception as parse_e:
                            logging.warning("Failed to parse date '%s' for %s: %s", date_str, emp, str(parse_e))
                            invalid_dates.append(f"{emp}: {date_str}")
            if invalid_dates:
                messagebox.showwarning("Warning", "The following must-have-off dates are invalid and will be ignored:\n" + "\n".join(invalid_dates))
        
        min_shifts = {}
        min_row = "min shifts per week"
        if min_row not in emp_df.index:
            logging.warning("Cannot find 'Min Shifts per Week' row, assuming 0")
            print("Warning: Cannot find 'Min Shifts per Week' row, assuming 0")
            min_shifts = {emp: 0 for emp in employees}
        else:
            for emp in employees:
                value = emp_df.loc[min_row, emp]
                min_shifts[emp] = int(value) if pd.notna(value) else 0
        logging.debug("Min shifts per week: %s", min_shifts)
        
        max_shifts = {}
        max_row = "max shifts per week"
        if max_row not in emp_df.index:
            logging.warning("Cannot find 'Max Shifts per Week' row, assuming no limit")
            print("Warning: Cannot find 'Max Shifts per Week' row, assuming no limit")
            max_shifts = {emp: float("inf") for emp in employees}
        else:
            for emp in employees:
                value = emp_df.loc[max_row, emp]
                max_shifts[emp] = int(value) if pd.notna(value) else float("inf")
        logging.debug("Max shifts per week: %s", max_shifts)
        
        max_weekend_days = {}
        weekend_row = "max number of weekend days"
        if weekend_row not in emp_df.index:
            logging.warning("Cannot find 'Max Number of Weekend Days' row, using default 1")
            print("Warning: Cannot find 'Max Number of Weekend Days' row, using default 1")
            max_weekend_days = {emp: 1 for emp in employees}
        else:
            for emp in employees:
                value = emp_df.loc[weekend_row, emp]
                max_weekend_days[emp] = int(value) if pd.notna(value) else 1
        logging.debug("Max weekend days per employee: %s", max_weekend_days)
        
        req_df = pd.read_csv(req_file, index_col=0)
        req_df.index = req_df.index.astype(str).str.strip()
        logging.debug("Personel Required CSV loaded: %s", req_df.to_string())
        if req_df.index.isna().any() or "" in req_df.index:
            logging.error("Personel_Required.csv has invalid or missing index values")
            raise ValueError("Personel_Required.csv has invalid or missing index values")
        required = {}
        for day in days:
            required[day] = {}
            for area in areas:
                counts = req_df.loc[area, day].split("/") if pd.notna(req_df.loc[area, day]) else ["0", "0"]
                try:
                    required[day][area] = {
                        "Morning": int(counts[0]),
                        "Evening": int(counts[1])
                    }
                except:
                    logging.error("Invalid staffing requirement for %s on %s", area, day)
                    raise ValueError(f"Invalid staffing requirement for {area} on {day}")
        logging.debug("Required staffing: %s", required)
        
        limits_df = pd.read_csv(limits_file)
        logging.debug("Hard Limits CSV loaded: %s", limits_df.to_string())
        if limits_df.empty:
            logging.error("Hard_Limits.csv is empty")
            raise ValueError("Hard_Limits.csv is empty")
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
        return employees, days, ["Morning", "Evening"], areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days
    except Exception as e:
        logging.error("Failed to load CSV files: %s", str(e))
        messagebox.showerror("Error", f"Failed to load CSV files: {str(e)}")
        return None