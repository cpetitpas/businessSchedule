import pulp
import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkcalendar import DateEntry
import csv
import json
import os
from datetime import datetime, timedelta
import math
import logging
import time

# Configure logging with date and time in filename
log_file = f"workforce_optimizer_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Function to load saved file paths and window geometry from config.json
def load_config():
    logging.debug("Entering load_config")
    config_file = "config.json"
    default_geometry = "1000x600"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
                emp_file_var.set(config.get("emp_file", ""))
                req_file_var.set(config.get("req_file", ""))
                limits_file_var.set(config.get("limits_file", ""))
                geometry = config.get("window_geometry", default_geometry)
                root.geometry(geometry)
                logging.info("Loaded config.json: %s", config)
        except Exception as e:
            logging.warning("Failed to load config.json: %s", str(e))
            print("Warning: Failed to load config.json, using empty paths and default geometry")
            root.geometry(default_geometry)
    else:
        logging.warning("config.json not found, using empty paths and default geometry")
        print("Warning: config.json not found, using empty paths and default geometry")
        root.geometry(default_geometry)
    logging.debug("Exiting load_config")

# Function to save file paths and window geometry to config.json
def save_config():
    logging.debug("Entering save_config")
    config = {
        "emp_file": emp_file_var.get(),
        "req_file": req_file_var.get(),
        "limits_file": limits_file_var.get(),
        "window_geometry": root.geometry()
    }
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        logging.info("Saved config.json: %s", config)
    except Exception as e:
        logging.warning("Failed to save config.json: %s", str(e))
        print(f"Warning: Failed to save config.json ({str(e)})")
    logging.debug("Exiting save_config")

# Function to handle window close
def on_closing():
    logging.debug("Window closing, saving config")
    save_config()
    root.destroy()

# Function to calculate minimum employees needed
def calculate_min_employees(required, work_areas, employees, must_off, max_shifts_per_week, max_weekend_shifts, start_date, num_weeks):
    logging.debug("Entering calculate_min_employees")
    areas = ["Bar", "Kitchen"]
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    
    # Current employees
    current = {"Bar": 0, "Kitchen": 0}
    for emp in employees:
        if "Bar" in work_areas[emp]:
            current["Bar"] += 1
        if "Kitchen" in work_areas[emp]:
            current["Kitchen"] += 1
    logging.info("Current employees: Bar=%d, Kitchen=%d", current["Bar"], current["Kitchen"])
    
    # Total shifts per area
    total_shifts = {"Bar": 0, "Kitchen": 0}
    for day in days:
        for area in areas:
            for shift in ["Morning", "Evening"]:
                total_shifts[area] += required[day][area][shift] * num_weeks
    logging.debug("Total shifts: Bar=%d, Kitchen=%d", total_shifts["Bar"], total_shifts["Kitchen"])
    
    # Weekend shifts
    weekend_shifts = {"Bar": 0, "Kitchen": 0}
    for week in range(num_weeks):
        if week < num_weeks - 1 or num_weeks == 1:
            for day in ["Fri", "Sat", "Sun"]:
                for area in areas:
                    for shift in ["Morning", "Evening"]:
                        weekend_shifts[area] += required[day][area][shift]
        else:
            for day in ["Fri", "Sat"]:
                for area in areas:
                    for shift in ["Morning", "Evening"]:
                        weekend_shifts[area] += required[day][area][shift]
    logging.debug("Weekend shifts: Bar=%d, Kitchen=%d", weekend_shifts["Bar"], weekend_shifts["Kitchen"])
    
    # Max shifts per employee
    avg_max_shifts = sum(max_shifts_per_week.values()) / len(max_shifts_per_week) if max_shifts_per_week else 3.067
    logging.debug("Average max shifts per employee: %.3f", avg_max_shifts)
    
    # Adjust for must-have-off within the schedule period
    unavailable_shifts = {"Bar": 0, "Kitchen": 0}
    for emp in must_off:
        for _, date_str in must_off[emp]:
            try:
                off_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                delta = (off_date - start_date).days
                if 0 <= delta < 7 * num_weeks:
                    for area in work_areas[emp]:
                        unavailable_shifts[area] += 1
            except:
                logging.warning("Invalid must-off date for %s: %s", emp, date_str)
                continue
    logging.debug("Unavailable shifts due to must-off: Bar=%d, Kitchen=%d", unavailable_shifts["Bar"], unavailable_shifts["Kitchen"])
    
    # Minimum employees needed
    needed = {"Bar": 0, "Kitchen": 0}
    for area in areas:
        shifts_needed = total_shifts[area] + unavailable_shifts[area]
        employees_by_total = math.ceil(shifts_needed / (avg_max_shifts * num_weeks))
        employees_by_weekend = math.ceil(weekend_shifts[area] / (max_weekend_shifts * num_weeks))
        needed[area] = max(employees_by_total, employees_by_weekend)
        if area == "Bar" and num_weeks == 2:
            needed[area] = max(needed[area], 6)
    logging.info("Minimum employees needed: Bar=%d, Kitchen=%d", needed["Bar"], needed["Kitchen"])
    
    logging.debug("Exiting calculate_min_employees")
    return current, needed

# Function to parse CSV files
def load_csv(emp_file, req_file, limits_file, start_date):
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
                                day_name = off_date.strftime("%a")
                                must_off[emp].append((day_name, off_date.strftime("%Y-%m-%d")))
                            else:
                                logging.warning("Must-have-off date %s for %s outside schedule, ignoring", off_date.strftime('%Y-%m-%d'), emp)
                                print(f"Warning: Must-have-off date {off_date.strftime('%Y-%m-%d')} for {emp} outside schedule, ignoring")
                        except Exception as e:
                            logging.warning("Exception parsing date '%s' for %s: %s", date_str, emp, str(e))
                            invalid_dates.append(f"{emp}: {date_str}")
        logging.debug("Must have off: %s", must_off)
        
        if invalid_dates:
            messagebox.showwarning("Invalid Dates", "The following must-have-off dates are invalid and will be ignored:\n" + "\n".join(invalid_dates))
        
        min_shifts = {}
        max_shifts = {}
        min_row = "min shifts per week"
        max_row = "max shifts per week"
        if min_row not in emp_df.index:
            logging.warning("Cannot find 'Min Shifts per Week' row, assuming 0")
            print("Warning: Cannot find 'Min Shifts per Week' row, assuming 0")
            min_shifts = {emp: 0 for emp in employees}
        else:
            for emp in employees:
                value = emp_df.loc[min_row, emp]
                min_shifts[emp] = int(value) if pd.notna(value) else 0
        logging.debug("Min shifts per week: %s", min_shifts)
        
        if max_row not in emp_df.index:
            logging.warning("Cannot find 'Max Shifts per Week' row, assuming no limit")
            print("Warning: Cannot find 'Max Shifts per Week' row, assuming no limit")
            max_shifts = {emp: float("inf") for emp in employees}
        else:
            for emp in employees:
                value = emp_df.loc[max_row, emp]
                max_shifts[emp] = int(value) if pd.notna(value) else float("inf")
        logging.debug("Max shifts per week: %s", max_shifts)
        
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
            "max_weekend_days": 1,
            "max_shifts_per_day": 1,
            "violate_order": ["Day Weights", "Shift Weight", "Max Number of Weekend Days", "Min Shifts per Week"]
        }
        try:
            if "Max Number of Weekend Days" in limits_df.columns:
                value = limits_df["Max Number of Weekend Days"].iloc[0]
                if pd.notna(value):
                    constraints["max_weekend_days"] = int(value)
                else:
                    logging.warning("Max Number of Weekend Days is empty, using default (1)")
                    print("Warning: Max Number of Weekend Days is empty, using default (1)")
            else:
                logging.warning("Max Number of Weekend Days column missing, using default (1)")
                print("Warning: Max Number of Weekend Days column missing, using default (1)")
                
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
        return employees, days, ["Morning", "Evening"], areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts
    except Exception as e:
        logging.error("Failed to load CSV files: %s", str(e))
        messagebox.showerror("Error", f"Failed to load CSV files: {str(e)}")
        return None

# Function to solve scheduling problem
def solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts,
                  relax_day=True, relax_shift=True, relax_weekend=True, relax_min_shifts=True, num_weeks=2):
    logging.debug("Entering solve_schedule with relax_day=%s, relax_shift=True, relax_weekend=True, relax_min_shifts=True, num_weeks=2")
    prob = pulp.LpProblem("Restaurant_Schedule", pulp.LpMaximize)
    
    # Create decision variables
    x = {}
    for e in employees:
        x[e] = {}
        for w in range(num_weeks):
            x[e][w] = {}
            for d in days:
                x[e][w][d] = {}
                for s in shifts:
                    x[e][w][d][s] = {}
                    for a in work_areas[e]:
                        x[e][w][d][s][a] = pulp.LpVariable(f"assign_{e}_w{w}_{d}_{s}_{a}", cat="Binary")
    logging.debug("Created %d decision variables for %d employees, %d weeks, %d days, %d shifts",
                  len(employees) * num_weeks * len(days) * len(shifts) * max(len(work_areas[e]) for e in employees),
                  len(employees), num_weeks, len(days), len(shifts))
    
    # Set objective function
    day_penalty = -10 if relax_day else 0
    shift_penalty = -10 if relax_shift else 0
    min_shifts_penalty = -100 if relax_min_shifts else 0
    objective_terms = []
    for e in employees:
        for w in range(num_weeks):
            for d in days:
                for s in shifts:
                    for a in work_areas[e]:
                        coef = (day_prefs[e][d] if day_prefs[e][d] > 0 else day_penalty) + \
                               (shift_prefs[e][s] if shift_prefs[e][s] > 0 else shift_penalty)
                        objective_terms.append((f"assign_{e}_w{w}_{d}_{s}_{a}", coef))
                        prob += x[e][w][d][s][a] * coef
    logging.debug("Objective function set with %d terms, day_penalty=%d, shift_penalty=%d, min_shifts_penalty=%d",
                  len(objective_terms), day_penalty, shift_penalty, min_shifts_penalty)
    for term, coef in objective_terms[:10]:  # Log first 10 for brevity
        logging.debug("Objective term: %s, coefficient=%d", term, coef)
    if len(objective_terms) > 10:
        logging.debug("... and %d more objective terms", len(objective_terms) - 10)
    
    # Staffing requirement constraints
    staffing_constraints = 0
    for w in range(num_weeks):
        for d in days:
            for a in areas:
                for s in shifts:
                    prob += pulp.lpSum(x[e][w][d][s][a] for e in employees if a in work_areas[e]) == required[d][a][s]
                    staffing_constraints += 1
    logging.debug("Added %d staffing requirement constraints", staffing_constraints)
    
    # Must-off constraints
    must_off_constraints = 0
    for e in must_off:
        for _, date_str in must_off[e]:
            delta = (datetime.strptime(date_str, "%Y-%m-%d").date() - start_date).days
            if 0 <= delta < 7 * num_weeks:
                w = delta // 7
                d_idx = delta % 7
                d = days[d_idx]
                for s in shifts:
                    for a in work_areas[e]:
                        prob += x[e][w][d][s][a] == 0
                        must_off_constraints += 1
                logging.debug("Must-off constraint added for %s on %s (week %d, day %s)", e, date_str, w, d)
    logging.debug("Added %d must-off constraints", must_off_constraints)
    
    # Max shifts per day constraints
    max_shifts_day_constraints = 0
    for e in employees:
        for w in range(num_weeks):
            for d in days:
                prob += pulp.lpSum(x[e][w][d][s][a] for s in shifts for a in work_areas[e]) <= constraints["max_shifts_per_day"]
                max_shifts_day_constraints += 1
    logging.debug("Added %d max shifts per day constraints", max_shifts_day_constraints)
    
    # Max shifts per week constraints
    max_shifts_week_constraints = 0
    for e in employees:
        for w in range(num_weeks):
            prob += pulp.lpSum(x[e][w][d][s][a] for d in days for s in shifts for a in work_areas[e]) <= max_shifts[e]
            max_shifts_week_constraints += 1
    logging.debug("Added %d max shifts per week constraints", max_shifts_week_constraints)
    
    # Min shifts per week constraints
    min_shifts_constraints = 0
    if relax_min_shifts:
        for e in employees:
            for w in range(num_weeks):
                prob += pulp.lpSum(x[e][w][d][s][a] for d in days for s in shifts for a in work_areas[e]) >= min_shifts[e]
                min_shifts_constraints += 1
        logging.debug("Added %d min shifts per week constraints", min_shifts_constraints)
    
    # Weekend shift constraints
    schedule_days = [(w, d) for w in range(num_weeks) for d in days]
    fri_sun_windows = []
    for w in range(num_weeks):
        if w < num_weeks - 1 or num_weeks == 1:
            fri_sun_windows.append([(w, "Fri"), (w, "Sat"), (w, "Sun")])
        else:
            fri_sun_windows.append([(w, "Fri"), (w, "Sat")])
    weekend_constraints = 0
    for e in employees:
        for window in fri_sun_windows:
            prob += pulp.lpSum(
                x[e][w][d][s][a]
                for w, d in window
                for s in shifts
                for a in work_areas[e]
            ) <= constraints["max_weekend_days"]
            weekend_constraints += 1
    logging.debug("Added %d weekend shift constraints", weekend_constraints)
    
    # Solve the problem
    start_time = time.time()
    prob.solve()
    end_time = time.time()
    solver_time = end_time - start_time
    logging.info("Solver status: %s, runtime: %.2f seconds", pulp.LpStatus[prob.status], solver_time)
    if prob.status == pulp.LpStatusOptimal:
        logging.info("Objective value: %.2f", pulp.value(prob.objective))
        assigned_shifts = []
        for e in employees:
            for w in range(num_weeks):
                for d in days:
                    for s in shifts:
                        for a in work_areas[e]:
                            if pulp.value(x[e][w][d][s][a]) == 1:
                                assigned_shifts.append(f"{e} assigned to {a}, {d}, {s}, week {w}")
        logging.debug("Assigned shifts: %s", assigned_shifts[:10])
        if len(assigned_shifts) > 10:
            logging.debug("... and %d more assigned shifts", len(assigned_shifts) - 10)
    
    logging.debug("Exiting solve_schedule")
    return prob, x

# Function to validate weekend constraints
def validate_weekend_constraints(x, employees, days, shifts, work_areas, max_weekend_days, start_date, num_weeks):
    logging.debug("Entering validate_weekend_constraints")
    violations = []
    schedule_days = [(w, d) for w in range(num_weeks) for d in days]
    fri_sun_windows = []
    for w in range(num_weeks):
        if w < num_weeks - 1 or num_weeks == 1:
            fri_sun_windows.append([(w, "Fri"), (w, "Sat"), (w, "Sun")])
        else:
            fri_sun_windows.append([(w, "Fri"), (w, "Sat")])
    for e in employees:
        for i, window in enumerate(fri_sun_windows):
            shift_count = sum(
                pulp.value(x[e][w][d][s][a])
                for w, d in window
                for s in shifts
                for a in work_areas[e]
                if pulp.value(x[e][w][d][s][a]) is not None
            )
            if shift_count > max_weekend_days:
                window_dates = " to ".join(
                    f"{d}, {(start_date + timedelta(days=(w * 7 + days.index(d)))).strftime('%b %d, %y')}"
                    for w, d in window
                )
                violations.append(f"{e} has {int(shift_count)} shifts in weekend period {window_dates}")
                logging.warning("Weekend constraint violation: %s has %d shifts in %s", e, int(shift_count), window_dates)
    logging.debug("Exiting validate_weekend_constraints with %d violations", len(violations))
    return violations

# Function to generate schedule with relaxation
def generate_schedule():
    logging.debug("Entering generate_schedule")
    global start_date, num_weeks_var, all_trees
    try:
        start_date = start_date_entry.get_date()
        num_weeks = num_weeks_var.get()
        if not isinstance(num_weeks, int) or num_weeks < 1:
            logging.error("Number of weeks must be an integer >= 1: %s", num_weeks)
            messagebox.showerror("Error", "Number of weeks must be an integer >= 1")
            return
        logging.info("Start date: %s, Number of weeks: %d", start_date.strftime('%Y-%m-%d'), num_weeks)
    except:
        logging.error("Invalid start date or number of weeks")
        messagebox.showerror("Error", "Invalid start date or number of weeks")
        return
    
    emp_file = emp_file_var.get()
    req_file = req_file_var.get()
    limits_file = limits_file_var.get()
    if not all([emp_file, req_file, limits_file]):
        logging.error("Missing CSV files: emp_file=%s, req_file=%s, limits_file=%s", emp_file, req_file, limits_file)
        messagebox.showerror("Error", "Please select all three CSV files")
        return
    
    data = load_csv(emp_file, req_file, limits_file, start_date)
    if not data:
        logging.error("load_csv returned None")
        return
    
    employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts = data
    
    # Calculate current and needed employees
    current, needed = calculate_min_employees(required, work_areas, employees, must_off, max_shifts, constraints["max_weekend_days"], start_date, num_weeks)
    
    relax_map = {
        "Day Weights": "relax_day",
        "Shift Weight": "relax_shift",
        "Max Number of Weekend Days": "relax_weekend",
        "Min Shifts per Week": "relax_min_shifts"
    }
    relax_order = [(True, True, True, True, "All constraints enforced")]
    for i, rule in enumerate(constraints["violate_order"], 1):
        relax_flags = list(relax_order[-1][:4])
        if rule in relax_map:
            idx = list(relax_map.keys()).index(rule)
            relax_flags[idx] = False
        relax_order.append(tuple(relax_flags) + (f"Relax {', '.join(constraints['violate_order'][:i])}",))
    
    solution = None
    x = None
    relaxed_message = ""
    for relax_day, relax_shift, relax_weekend, relax_min_shifts, msg in relax_order:
        logging.debug("Trying relaxation: %s", msg)
        prob, x = solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas,
                                 constraints, min_shifts, max_shifts, relax_day, relax_shift, relax_weekend, relax_min_shifts, num_weeks)
        if prob.status == pulp.LpStatusOptimal:
            relaxed_message = msg
            solution = prob
            logging.info("Optimal schedule found with relaxation: %s", msg)
            break
        else:
            logging.warning("No optimal solution with relaxation: %s", msg)
    
    # Clear existing schedules
    for widget in bar_frame.winfo_children():
        widget.destroy()
    for widget in kitchen_frame.winfo_children():
        widget.destroy()
    all_trees = []
    
    employee_message = (
        f"Current Employees - Bar: {current['Bar']}, Kitchen: {current['Kitchen']}\n"
        f"Minimum Employees Needed - Bar: {needed['Bar']}, Kitchen: {needed['Kitchen']}"
    )
    logging.info(employee_message)
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    if solution and solution.status == pulp.LpStatusOptimal:
        violations = validate_weekend_constraints(x, employees, days, shifts, work_areas, constraints["max_weekend_days"], start_date, num_weeks)
        violation_message = "\n".join(violations) if violations else "None"
        message = (
            f"Optimal schedule found! ({relaxed_message})\n"
            f"{employee_message}\n"
            f"Weekend constraint violations:\n{violation_message}"
        )
        messagebox.showinfo("Success", message)
        logging.info("Schedule generation successful: %s", message)
        
        total_days = 7 * num_weeks
        dates = [(start_date + timedelta(days=i)) for i in range(total_days)]
        start_weekday = start_date.weekday()
        day_names = days[(start_weekday + 1) % 7:] + days[:(start_weekday + 1) % 7]
        columns = [f"{day_names[i % 7]}, {d.strftime('%b %d, %y')}" for i, d in enumerate(dates)]
        
        bar_schedule = []
        kitchen_schedule = []
        for w in range(num_weeks):
            week_cols = columns[w * 7:(w + 1) * 7]
            bar_schedule.extend([
                ["Day/Shift"] + week_cols,
                ["Morning"] + [""] * len(week_cols),
                ["Evening"] + [""] * len(week_cols),
                []
            ])
            kitchen_schedule.extend([
                ["Day/Shift"] + week_cols,
                ["Morning"] + [""] * len(week_cols),
                ["Evening"] + [""] * len(week_cols),
                []
            ])
            # Create Treeview for Bar week
            tk.Label(bar_frame, text=f"Bar Schedule Week {w+1}").pack(pady=5)
            bar_tree = ttk.Treeview(bar_frame, columns=[f"Col{i}" for i in range(8)], show="headings", height=2)
            bar_tree.heading("Col0", text="Day/Shift")
            bar_tree.column("Col0", width=80, anchor="w")
            for i in range(7):
                text = week_cols[i] if i < len(week_cols) else ""
                bar_tree.heading(f"Col{i+1}", text=text)
                bar_tree.column(f"Col{i+1}", width=100, anchor="center")
            all_trees.append(bar_tree)
            # Create Treeview for Kitchen week
            tk.Label(kitchen_frame, text=f"Kitchen Schedule Week {w+1}").pack(pady=5)
            kitchen_tree = ttk.Treeview(kitchen_frame, columns=[f"Col{i}" for i in range(8)], show="headings", height=2)
            kitchen_tree.heading("Col0", text="Day/Shift")
            kitchen_tree.column("Col0", width=80, anchor="w")
            for i in range(7):
                text = week_cols[i] if i < len(week_cols) else ""
                kitchen_tree.heading(f"Col{i+1}", text=text)
                kitchen_tree.column(f"Col{i+1}", width=100, anchor="center")
            all_trees.append(kitchen_tree)
            
            # Fill rows for this week
            for a, tree, schedule in zip(areas, [bar_tree, kitchen_tree], [bar_schedule, kitchen_schedule]):
                morning_row = ["Morning"] + [""] * 7
                evening_row = ["Evening"] + [""] * 7
                row_offset = w * 4 + 1  # Morning row for this week in schedule
                for d_idx in range(7):
                    day_name = day_names[d_idx]
                    col_idx = d_idx + 1
                    for s_idx, s in enumerate(shifts):
                        assigned = [e for e in employees if a in work_areas[e] and pulp.value(x[e][w][day_name][s][a]) == 1]
                        if s == "Morning":
                            morning_row[col_idx] = ", ".join(assigned)
                            schedule[row_offset][col_idx] = ", ".join(assigned)
                        else:
                            evening_row[col_idx] = ", ".join(assigned)
                            schedule[row_offset + 1][col_idx] = ", ".join(assigned)
                tree.insert("", "end", values=morning_row)
                tree.insert("", "end", values=evening_row)
                tree.pack(pady=5, fill="x")
                logging.debug("Schedule for %s Week %d populated", a, w+1)
        
        with open(f"Bar_schedule_{date_str}.csv", "w", newline="") as f:
            writer = csv.writer(f)
            for row in bar_schedule:
                if row:
                    writer.writerow(row)
        logging.info("Bar schedule saved to Bar_schedule_%s.csv", date_str)
        
        with open(f"Kitchen_schedule_{date_str}.csv", "w", newline="") as f:
            writer = csv.writer(f)
            for row in kitchen_schedule:
                if row:
                    writer.writerow(row)
        logging.info("Kitchen schedule saved to Kitchen_schedule_%s.csv", date_str)
        
        # Adjust column widths initially
        adjust_column_widths()
    else:
        error_message = (
            f"No feasible schedule found even after relaxing all constraints.\n"
            f"Check staffing requirements or employee availability.\n"
            f"{employee_message}"
        )
        messagebox.showerror("Error", error_message)
        logging.error(error_message)
    
    logging.debug("Exiting generate_schedule")

# Function to adjust column widths on resize
def adjust_column_widths():
    global all_trees
    width = root.winfo_width()
    for tree in all_trees:
        cols = [c for c in tree["columns"] if c != "Col0"]
        if cols:
            col_width = max(100, (width - 80 - 40) // len(cols))  # Adjust for paddings and scrollbar
            for c in cols:
                tree.column(c, width=col_width)
    # Adjust input data tabs
    notebook.update_idletasks()
    for tab in [emp_text, req_text, limits_text]:
        tab.configure(width=max(50, width // 10))  # Adjust text widget width

# Resize event handler
def on_resize(event):
    if event.widget == root:
        adjust_column_widths()

# Mousewheel event handler
def on_mousewheel(event):
    canvas.yview_scroll(-1 * (event.delta // 120), "units")

# Function to display input data
def display_input_data():
    logging.debug("Entering display_input_data")
    # Employee Data
    emp_file = emp_file_var.get()
    emp_text.delete("1.0", tk.END)
    if emp_file:
        try:
            df = pd.read_csv(emp_file)
            emp_text.insert(tk.END, df.to_string())
            logging.info("Displayed Employee Data: %s", emp_file)
        except Exception as e:
            emp_text.insert(tk.END, f"Error loading file: {str(e)}")
            logging.error("Error loading Employee Data: %s", str(e))
    
    # Personel Required
    req_file = req_file_var.get()
    req_text.delete("1.0", tk.END)
    if req_file:
        try:
            df = pd.read_csv(req_file)
            req_text.insert(tk.END, df.to_string())
            logging.info("Displayed Personel Required: %s", req_file)
        except Exception as e:
            req_text.insert(tk.END, f"Error loading file: {str(e)}")
            logging.error("Error loading Personel Required: %s", str(e))
    
    # Hard Limits
    limits_file = limits_file_var.get()
    limits_text.delete("1.0", tk.END)
    if limits_file:
        try:
            df = pd.read_csv(limits_file)
            limits_text.insert(tk.END, df.to_string())
            logging.info("Displayed Hard Limits: %s", limits_file)
        except Exception as e:
            limits_text.insert(tk.END, f"Error loading file: {str(e)}")
            logging.error("Error loading Hard Limits: %s", str(e))
    adjust_column_widths()  # Ensure tabs resize after loading data
    logging.debug("Exiting display_input_data")

# Tkinter GUI with scrollable canvas
root = tk.Tk()
root.title("Workforce Optimizer")
root.geometry("1000x600")

# Create canvas and scrollbar
canvas = tk.Canvas(root)
scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas)

# Configure canvas
canvas.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)
canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=root.winfo_width())

# Update scroll region and canvas width when frame size changes
def on_frame_configure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))
    canvas.itemconfig(canvas_frame, width=root.winfo_width())

scrollable_frame.bind("<Configure>", on_frame_configure)

# Start date selection
tk.Label(scrollable_frame, text="Select Start Date:").pack(pady=5)
start_date_entry = DateEntry(scrollable_frame, width=12, background='darkblue', foreground='white', borderwidth=2, year=2025, firstweekday='sunday', showweeknumbers=False)
start_date_entry.pack(pady=5)

# Number of weeks input
tk.Label(scrollable_frame, text="Number of Weeks (1 or more):").pack(pady=5)
num_weeks_var = tk.IntVar(value=2)
num_weeks_entry = tk.Entry(scrollable_frame, textvariable=num_weeks_var, width=10)
num_weeks_entry.pack(pady=5)

# File selection for Employee Data
emp_file_var = tk.StringVar()
tk.Label(scrollable_frame, text="Select Employee Data CSV:").pack(pady=5)
emp_entry = tk.Entry(scrollable_frame, textvariable=emp_file_var, width=50)
emp_entry.pack(pady=5)
tk.Button(scrollable_frame, text="Browse", command=lambda: [emp_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config()]).pack(pady=5)

# File selection for Personel Required
req_file_var = tk.StringVar()
tk.Label(scrollable_frame, text="Select Personel Required CSV:").pack(pady=5)
req_entry = tk.Entry(scrollable_frame, textvariable=req_file_var, width=50)
req_entry.pack(pady=5)
tk.Button(scrollable_frame, text="Browse", command=lambda: [req_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config()]).pack(pady=5)

# File selection for Hard Limits
limits_file_var = tk.StringVar()
tk.Label(scrollable_frame, text="Select Hard Limits CSV:").pack(pady=5)
limits_entry = tk.Entry(scrollable_frame, textvariable=limits_file_var, width=50)
limits_entry.pack(pady=5)
tk.Button(scrollable_frame, text="Browse", command=lambda: [limits_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config()]).pack(pady=5)

# Load saved file paths and window geometry
load_config()

# View Input Data button
tk.Button(scrollable_frame, text="View Input Data", command=display_input_data).pack(pady=5)

# Input data tabs
notebook = ttk.Notebook(scrollable_frame)
notebook.pack(pady=10, fill="both", expand=True)

# Employee Data tab
emp_tab = tk.Frame(notebook)
notebook.add(emp_tab, text="Employee Data")
emp_text = tk.Text(emp_tab, wrap="none", height=10)
emp_yscroll = ttk.Scrollbar(emp_tab, orient="vertical", command=emp_text.yview)
emp_xscroll = ttk.Scrollbar(emp_tab, orient="horizontal", command=emp_text.xview)
emp_text.configure(yscrollcommand=emp_yscroll.set, xscrollcommand=emp_xscroll.set)
emp_xscroll.pack(side="bottom", fill="x")
emp_yscroll.pack(side="right", fill="y")
emp_text.pack(side="left", fill="both", expand=True)

# Personel Required tab
req_tab = tk.Frame(notebook)
notebook.add(req_tab, text="Personel Required")
req_text = tk.Text(req_tab, wrap="none", height=10)
req_yscroll = ttk.Scrollbar(req_tab, orient="vertical", command=req_text.yview)
req_xscroll = ttk.Scrollbar(req_tab, orient="horizontal", command=req_text.xview)
req_text.configure(yscrollcommand=req_yscroll.set, xscrollcommand=req_xscroll.set)
req_xscroll.pack(side="bottom", fill="x")
req_yscroll.pack(side="right", fill="y")
req_text.pack(side="left", fill="both", expand=True)

# Hard Limits tab
limits_tab = tk.Frame(notebook)
notebook.add(limits_tab, text="Hard Limits")
limits_text = tk.Text(limits_tab, wrap="none", height=10)
limits_yscroll = ttk.Scrollbar(limits_tab, orient="vertical", command=limits_text.yview)
limits_xscroll = ttk.Scrollbar(limits_tab, orient="horizontal", command=limits_text.xview)
limits_text.configure(yscrollcommand=limits_yscroll.set, xscrollcommand=limits_xscroll.set)
limits_xscroll.pack(side="bottom", fill="x")
limits_yscroll.pack(side="right", fill="y")
limits_text.pack(side="left", fill="both", expand=True)

# Schedule display frames
tk.Label(scrollable_frame, text="Bar Schedule").pack(pady=5)
bar_frame = tk.Frame(scrollable_frame)
bar_frame.pack(pady=5, fill="x")

tk.Label(scrollable_frame, text="Kitchen Schedule").pack(pady=5)
kitchen_frame = tk.Frame(scrollable_frame)
kitchen_frame.pack(pady=5, fill="x")

# Generate button
tk.Button(scrollable_frame, text="Generate Schedule", command=generate_schedule).pack(pady=10)

# Bind events
root.bind("<Configure>", on_resize)
root.bind("<MouseWheel>", on_mousewheel)
root.protocol("WM_DELETE_WINDOW", on_closing)

# Global list for trees
all_trees = []

# Initial resize to ensure input tabs expand
root.update_idletasks()
adjust_column_widths()

logging.info("Application started")
root.mainloop()