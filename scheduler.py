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

# Function to load saved file paths from config.json
def load_config():
    config_file = "config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
                emp_file_var.set(config.get("emp_file", ""))
                req_file_var.set(config.get("req_file", ""))
                limits_file_var.set(config.get("limits_file", ""))
        except:
            print("Warning: Failed to load config.json, using empty paths")
    else:
        print("Warning: config.json not found, using empty paths")

# Function to save file paths to config.json
def save_config():
    config = {
        "emp_file": emp_file_var.get(),
        "req_file": req_file_var.get(),
        "limits_file": limits_file_var.get()
    }
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Warning: Failed to save config.json ({str(e)})")

# Function to calculate minimum employees needed
def calculate_min_employees(required, work_areas, employees, must_off, max_shifts_per_week, max_weekend_shifts, start_date):
    areas = ["Bar", "Kitchen"]
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    
    # Current employees
    current = {"Bar": 0, "Kitchen": 0}
    for emp in employees:
        if "Bar" in work_areas[emp]:
            current["Bar"] += 1
        if "Kitchen" in work_areas[emp]:
            current["Kitchen"] += 1
    
    # Total shifts per area
    total_shifts = {"Bar": 0, "Kitchen": 0}
    for day in days:
        for area in areas:
            for shift in ["Morning", "Evening"]:
                total_shifts[area] += required[day][area][shift]
    
    # Weekend shifts (Fri-Sun in Week 1-2, Fri-Sat in Week 2)
    weekend_shifts = {"Bar": 0, "Kitchen": 0}
    weekend_days = [(0, "Fri"), (0, "Sat"), (1, "Sun"), (1, "Fri"), (1, "Sat")]
    for w, d in weekend_days:
        for area in areas:
            for shift in ["Morning", "Evening"]:
                weekend_shifts[area] += required[d][area][shift]
    
    # Max shifts per employee (average of max_shifts_per_week)
    avg_max_shifts = sum(max_shifts_per_week.values()) / len(max_shifts_per_week) if max_shifts_per_week else 3.067
    total_weeks = 2
    
    # Adjust for must-have-off within the schedule period
    unavailable_shifts = {"Bar": 0, "Kitchen": 0}
    for emp in must_off:
        for _, date_str in must_off[emp]:
            try:
                off_date = datetime.strptime(date_str, "%Y-%m-%d")
                delta = (off_date - start_date).days
                if 0 <= delta < 14:  # Within two-week period
                    for area in work_areas[emp]:
                        unavailable_shifts[area] += 1  # One shift unavailable
            except:
                continue
    
    # Minimum employees needed
    needed = {"Bar": 0, "Kitchen": 0}
    for area in areas:
        # Total shifts ÷ max shifts per employee
        shifts_needed = total_shifts[area] + unavailable_shifts[area]
        employees_by_total = math.ceil(shifts_needed / (avg_max_shifts * total_weeks))
        # Weekend shifts ÷ max weekend shifts per employee (1 per period, 2 periods)
        employees_by_weekend = math.ceil(weekend_shifts[area] / (max_weekend_shifts * 2))
        # Take maximum
        needed[area] = max(employees_by_total, employees_by_weekend)
        # Adjust Bar to 6 based on user observation
        if area == "Bar":
            needed[area] = max(needed[area], 6)
    
    return current, needed

# Function to parse CSV files
def load_csv(emp_file, req_file, limits_file, start_date):
    try:
        # Parse Employee Data
        emp_df = pd.read_csv(emp_file, index_col=0)
        emp_df.index = emp_df.index.astype(str).str.strip().str.lower()
        if emp_df.index.isna().any() or "" in emp_df.index:
            raise ValueError("Employee_Data.csv has invalid or missing index values")
        employees = [col for col in emp_df.columns if pd.notna(col)]
        if not employees:
            raise ValueError("No valid employee columns found in Employee_Data.csv")
        
        # Work areas
        work_areas = {}
        area_row = "work area"
        if area_row not in emp_df.index:
            raise ValueError("Cannot find 'Work Area' row in Employee_Data.csv")
        areas = ["Bar", "Kitchen"]
        for emp in employees:
            area = emp_df.loc[area_row, emp]
            if pd.notna(area) and area in areas:
                work_areas[emp] = [area]  # Single area per employee
            else:
                raise ValueError(f"Invalid work area for {emp}: {area}")
        
        # Shift preferences
        shift_prefs = {}
        shift_row = "shift weight"
        if shift_row not in emp_df.index:
            raise ValueError("Cannot find 'Shift Weight' row in Employee_Data.csv")
        for emp in employees:
            shift = emp_df.loc[shift_row, emp]
            if pd.isna(shift):
                shift_prefs[emp] = {"Morning": 0, "Evening": 0}
            else:
                shift = str(shift).strip().lower()
                if shift not in ["morning", "evening"]:
                    print(f"Warning: Invalid shift '{shift}' for {emp}, assuming no preference")
                    shift_prefs[emp] = {"Morning": 0, "Evening": 0}
                else:
                    shift_prefs[emp] = {
                        "Morning": 10 if shift == "morning" else 0,
                        "Evening": 10 if shift == "evening" else 0
                    }
        
        # Day preferences
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        day_prefs = {}
        day_row = "day weights"
        if day_row not in emp_df.index:
            raise ValueError("Cannot find 'Day Weights' row in Employee_Data.csv")
        for emp in employees:
            day_str = emp_df.loc[day_row, emp]
            preferred_days = []
            if pd.notna(day_str):
                try:
                    preferred_days = [d.strip() for d in str(day_str).split(", ")]
                    invalid_days = [d for d in preferred_days if d not in days]
                    if invalid_days:
                        print(f"Warning: Invalid days {invalid_days} for {emp}, ignoring them")
                        preferred_days = [d for d in preferred_days if d in days]
                except:
                    print(f"Warning: Failed to parse day preferences for {emp}, assuming none")
            day_prefs[emp] = {day: 10 if day in preferred_days else 0 for day in days}
        
        # Must-have-off (relative to start_date)
        must_off = {}
        off_row = "must have off"
        if off_row not in emp_df.index:
            print("Warning: Cannot find 'Must have off' row, assuming none")
        else:
            for emp in employees:
                off_date = emp_df.loc[off_row, emp]
                if pd.notna(off_date):
                    try:
                        off_date = pd.to_datetime(off_date)
                        delta = (off_date - start_date).days
                        if 0 <= delta < 14:  # Within two-week period
                            day_name = days[delta % 7]
                            must_off[emp] = [(day_name, off_date.strftime("%Y-%m-%d"))]
                        else:
                            print(f"Warning: Must-have-off date {off_date.strftime('%Y-%m-%d')} for {emp} outside schedule, ignoring")
                    except:
                        print(f"Warning: Invalid date format for {emp}'s must-have-off")
        
        # Min and Max Shifts per Week
        min_shifts = {}
        max_shifts = {}
        min_row = "min shifts per week"
        max_row = "max shifts per week"
        if min_row not in emp_df.index:
            print("Warning: Cannot find 'Min Shifts per Week' row, assuming 0")
            min_shifts = {emp: 0 for emp in employees}
        else:
            for emp in employees:
                value = emp_df.loc[min_row, emp]
                min_shifts[emp] = int(value) if pd.notna(value) else 0
        
        if max_row not in emp_df.index:
            print("Warning: Cannot find 'Max Shifts per Week' row, assuming no limit")
            max_shifts = {emp: float("inf") for emp in employees}
        else:
            for emp in employees:
                value = emp_df.loc[max_row, emp]
                max_shifts[emp] = int(value) if pd.notna(value) else float("inf")
        
        # Parse Personel Required
        req_df = pd.read_csv(req_file, index_col=0)
        req_df.index = req_df.index.astype(str).str.strip()
        if req_df.index.isna().any() or "" in req_df.index:
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
                    raise ValueError(f"Invalid staffing requirement for {area} on {day}")
        
        # Parse Hard Limits
        limits_df = pd.read_csv(limits_file)
        if limits_df.empty:
            raise ValueError("Hard_Limits.csv is empty")
        constraints = {
            "max_weekend_days": 1,  # From Hard_Limits.csv
            "max_shifts_per_day": 1,
            "violate_order": ["Day Weights", "Shift Weight", "Max Number of Weekend Days", "Min Shifts per Week"]
        }
        try:
            if "Max Number of Weekend Days" in limits_df.columns:
                value = limits_df["Max Number of Weekend Days"].iloc[0]
                if pd.notna(value):
                    constraints["max_weekend_days"] = int(value)
                else:
                    print("Warning: Max Number of Weekend Days is empty, using default (1)")
            else:
                print("Warning: Max Number of Weekend Days column missing, using default (1)")
                
            if "Max Number of Shifts per Day" in limits_df.columns:
                value = limits_df["Max Number of Shifts per Day"].iloc[0]
                if pd.notna(value):
                    constraints["max_shifts_per_day"] = int(value)
                else:
                    print("Warning: Max Number of Shifts per Day is empty, using default (1)")
            else:
                print("Warning: Max Number of Shifts per Day column missing, using default (1)")
                
            if "Violate Rules Order" in limits_df.columns:
                value = limits_df["Violate Rules Order"].iloc[0]
                if pd.notna(value) and isinstance(value, str):
                    constraints["violate_order"] = [v.strip() for v in value.split(", ")]
                else:
                    print("Warning: Violate Rules Order is invalid or empty, using default order")
            else:
                print("Warning: Violate Rules Order column missing, using default order")
        except Exception as e:
            print(f"Warning: Error parsing Hard_Limits.csv ({str(e)}), using default constraints")
        
        return employees, days, ["Morning", "Evening"], areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load CSV files: {str(e)}")
        return None

# Function to solve scheduling problem
def solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts,
                  relax_day=True, relax_shift=True, relax_weekend=True, relax_min_shifts=True):
    prob = pulp.LpProblem("Restaurant_Schedule", pulp.LpMaximize)
    
    # Decision variables
    x = {}
    for e in employees:
        x[e] = {}
        for w in range(2):  # Two weeks
            x[e][w] = {}
            for d in days:
                x[e][w][d] = {}
                for s in shifts:
                    x[e][w][d][s] = {}
                    for a in work_areas[e]:
                        x[e][w][d][s][a] = pulp.LpVariable(f"assign_{e}_w{w}_{d}_{s}_{a}", cat="Binary")
    
    # Objective: Maximize preferences, penalize violations
    day_penalty = -10 if relax_day else 0
    shift_penalty = -10 if relax_shift else 0
    min_shifts_penalty = -100 if relax_min_shifts else 0
    prob += pulp.lpSum(
        x[e][w][d][s][a] * (
            (day_prefs[e][d] if day_prefs[e][d] > 0 else day_penalty) +
            (shift_prefs[e][s] if shift_prefs[e][s] > 0 else shift_penalty)
        )
        for e in employees for w in range(2) for d in days for s in shifts for a in work_areas[e]
    )
    
    # Constraints
    # 1. Staffing requirements (hard)
    for w in range(2):
        for d in days:
            for a in areas:
                for s in shifts:
                    prob += pulp.lpSum(x[e][w][d][s][a] for e in employees if a in work_areas[e]) == required[d][a][s]
    
    # 2. Must-have-off (hard)
    for e in must_off:
        for day_name, date_str in must_off[e]:
            w = 0 if (datetime.strptime(date_str, "%Y-%m-%d") - start_date).days < 7 else 1
            for s in shifts:
                for a in work_areas[e]:
                    prob += x[e][w][day_name][s][a] == 0
    
    # 3. Max shifts per day (hard)
    for e in employees:
        for w in range(2):
            for d in days:
                prob += pulp.lpSum(x[e][w][d][s][a] for s in shifts for a in work_areas[e]) <= constraints["max_shifts_per_day"]
    
    # 4. Max shifts per week (hard)
    for e in employees:
        for w in range(2):
            prob += pulp.lpSum(x[e][w][d][s][a] for d in days for s in shifts for a in work_areas[e]) <= max_shifts[e]
    
    # 5. Min shifts per week (relaxable)
    if relax_min_shifts:
        for e in employees:
            for w in range(2):
                prob += pulp.lpSum(x[e][w][d][s][a] for d in days for s in shifts for a in work_areas[e]) >= min_shifts[e]
    
    # 6. Max weekend days (non-relaxable by default, unless specified)
    schedule_days = [(w, d) for w in range(2) for d in days]
    fri_sun_windows = [
        [(0, "Fri"), (0, "Sat"), (1, "Sun")],  # First Fri-Sun
        [(1, "Fri"), (1, "Sat")],  # Second Fri-Sat
    ]
    for e in employees:
        for window in fri_sun_windows:
            prob += pulp.lpSum(
                x[e][w][d][s][a]
                for w, d in window
                for s in shifts
                for a in work_areas[e]
            ) <= constraints["max_weekend_days"]
    
    # Solve
    prob.solve()
    return prob, x

# Function to validate weekend constraints
def validate_weekend_constraints(x, employees, days, shifts, work_areas, max_weekend_days, start_date):
    violations = []
    schedule_days = [(w, d) for w in range(2) for d in days]
    fri_sun_windows = [
        [(0, "Fri"), (0, "Sat"), (1, "Sun")],  # First Fri-Sun
        [(1, "Fri"), (1, "Sat")],  # Second Fri-Sat
    ]
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
    return violations

# Function to generate schedule with relaxation
def generate_schedule():
    global start_date  # Make start_date accessible for must-have-off
    try:
        start_date = start_date_entry.get_date()
        if start_date.weekday() != 6:  # Sunday is 6
            messagebox.showerror("Error", "Start date must be a Sunday")
            return
    except:
        messagebox.showerror("Error", "Invalid start date format")
        return
    
    emp_file = emp_file_var.get()
    req_file = req_file_var.get()
    limits_file = limits_file_var.get()
    if not all([emp_file, req_file, limits_file]):
        messagebox.showerror("Error", "Please select all three CSV files")
        return
    
    data = load_csv(emp_file, req_file, limits_file, start_date)
    if not data:
        return
    
    employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts = data
    
    # Map relaxation order to flags
    relax_map = {
        "Day Weights": "relax_day",
        "Shift Weight": "relax_shift",
        "Max Number of Weekend Days": "relax_weekend",
        "Min Shifts per Week": "relax_min_shifts"
    }
    relax_order = [(True, True, True, True, "All constraints enforced")]
    for i, rule in enumerate(constraints["violate_order"], 1):
        current = list(relax_order[-1][:4])
        if rule in relax_map:
            current[list(relax_map.keys()).index(rule)] = False
        relax_order.append((*current, f"Relax {', '.join(constraints['violate_order'][:i])}"))
    
    solution = None
    x = None
    relaxed_message = ""
    for relax_day, relax_shift, relax_weekend, relax_min_shifts, msg in relax_order:
        prob, x = solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas,
                                 constraints, min_shifts, max_shifts, relax_day, relax_shift, relax_weekend, relax_min_shifts)
        if prob.status == pulp.LpStatusOptimal:
            relaxed_message = msg
            solution = prob
            break
    
    # Clear previous Treeview contents
    for tree in [bar_tree, kitchen_tree]:
        for item in tree.get_children():
            tree.delete(item)
    
    if solution and solution.status == pulp.LpStatusOptimal:
        # Validate weekend constraints
        violations = validate_weekend_constraints(x, employees, days, shifts, work_areas, constraints["max_weekend_days"], start_date)
        violation_message = "\n".join(violations) if violations else "None"
        messagebox.showinfo("Success", f"Optimal schedule found! ({relaxed_message})\nWeekend constraint violations:\n{violation_message}")
        
        # Generate two-week dates
        dates = [(start_date + timedelta(days=i)) for i in range(14)]
        columns = [f"{days[i % 7]}, {d.strftime('%b %d, %y')}" for i, d in enumerate(dates)]
        
        # Initialize schedules
        bar_schedule = [
            ["Day/Shift"] + columns[:7],  # Week 1 header
            ["Morning"] + [""] * 7,
            ["Evening"] + [""] * 7,
            [],  # Blank row
            ["Day/Shift"] + columns[7:],  # Week 2 header
            ["Morning"] + [""] * 7,
            ["Evening"] + [""] * 7
        ]
        kitchen_schedule = [
            ["Day/Shift"] + columns[:7],  # Week 1 header
            ["Morning"] + [""] * 7,
            ["Evening"] + [""] * 7,
            [],  # Blank row
            ["Day/Shift"] + columns[7:],  # Week 2 header
            ["Morning"] + [""] * 7,
            ["Evening"] + [""] * 7
        ]
        
        # Populate schedules
        for w in range(2):
            row_offset = w * 4  # Week 1: 0-2, Week 2: 4-6 (skipping blank row at 3)
            for d, day in enumerate(days):
                col_idx = d + 1  # Column 0 is Day/Shift, 1-7 are days
                for a in areas:
                    for s in shifts:
                        assigned = [e for e in employees if a in work_areas[e] and pulp.value(x[e][w][day][s][a]) == 1]
                        row_idx = row_offset + (1 if s == "Morning" else 2)
                        if a == "Bar":
                            bar_schedule[row_idx][col_idx] = ", ".join(assigned)
                        else:
                            kitchen_schedule[row_idx][col_idx] = ", ".join(assigned)
        
        # Update Treeviews
        for tree, schedule, area in [(bar_tree, bar_schedule, "Bar"), (kitchen_tree, kitchen_schedule, "Kitchen")]:
            for row_idx, row in enumerate(schedule):
                if row:  # Skip blank row
                    tree.insert("", "end", values=row)
        
        # Write Bar_schedule.csv
        with open("Bar_schedule.csv", "w", newline="") as f:
            writer = csv.writer(f)
            for row in bar_schedule:
                writer.writerow(row)
        
        # Write Kitchen_schedule.csv
        with open("Kitchen_schedule.csv", "w", newline="") as f:
            writer = csv.writer(f)
            for row in kitchen_schedule:
                writer.writerow(row)
    else:
        # Calculate minimum employees needed
        current, needed = calculate_min_employees(required, work_areas, employees, must_off, max_shifts, constraints["max_weekend_days"], start_date)
        error_message = (
            f"No feasible schedule found even after relaxing all constraints.\n"
            f"Check staffing requirements or employee availability.\n"
            f"Current Bar: {current['Bar']}, Needed Bar: {needed['Bar']}\n"
            f"Current Kitchen: {current['Kitchen']}, Needed Kitchen: {needed['Kitchen']}"
        )
        messagebox.showerror("Error", error_message)

# Tkinter GUI
root = tk.Tk()
root.title("Restaurant Scheduler")
root.geometry("1000x800")

# Start date selection
tk.Label(root, text="Select Start Date (Sunday):").pack(pady=5)
start_date_entry = DateEntry(root, width=12, background='darkblue', foreground='white', borderwidth=2, year=2025, firstweekday='sunday', showweeknumbers=False)
start_date_entry.pack(pady=5)

# File selection for Employee Data
emp_file_var = tk.StringVar()
tk.Label(root, text="Select Employee Data CSV:").pack(pady=5)
emp_entry = tk.Entry(root, textvariable=emp_file_var, width=50)
emp_entry.pack(pady=5)
tk.Button(root, text="Browse", command=lambda: [emp_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config()]).pack(pady=5)

# File selection for Personel Required
req_file_var = tk.StringVar()
tk.Label(root, text="Select Personel Required CSV:").pack(pady=5)
req_entry = tk.Entry(root, textvariable=req_file_var, width=50)
req_entry.pack(pady=5)
tk.Button(root, text="Browse", command=lambda: [req_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config()]).pack(pady=5)

# File selection for Hard Limits
limits_file_var = tk.StringVar()
tk.Label(root, text="Select Hard Limits CSV:").pack(pady=5)
limits_entry = tk.Entry(root, textvariable=limits_file_var, width=50)
limits_entry.pack(pady=5)
tk.Button(root, text="Browse", command=lambda: [limits_file_var.set(filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])), save_config()]).pack(pady=5)

# Load saved file paths
load_config()

# Schedule display (two Treeviews)
tk.Label(root, text="Bar Schedule").pack(pady=5)
bar_tree = ttk.Treeview(root, columns=["Day/Shift"] + [f"Day{i}" for i in range(7)], show="headings", height=7)
bar_tree.heading("Day/Shift", text="Day/Shift")
for i in range(7):
    bar_tree.heading(f"Day{i}", text="")
    bar_tree.column(f"Day{i}", width=100, anchor="center")
bar_tree.column("Day/Shift", width=80, anchor="w")
bar_tree.pack(pady=5, fill="x")

tk.Label(root, text="Kitchen Schedule").pack(pady=5)
kitchen_tree = ttk.Treeview(root, columns=["Day/Shift"] + [f"Day{i}" for i in range(7)], show="headings", height=7)
kitchen_tree.heading("Day/Shift", text="Day/Shift")
for i in range(7):
    kitchen_tree.heading(f"Day{i}", text="")
    kitchen_tree.column(f"Day{i}", width=100, anchor="center")
kitchen_tree.column("Day/Shift", width=80, anchor="w")
kitchen_tree.pack(pady=5, fill="x")

# Generate button
tk.Button(root, text="Generate Schedule", command=generate_schedule).pack(pady=10)

root.mainloop()