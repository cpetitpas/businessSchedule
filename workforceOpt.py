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
def calculate_min_employees(required, work_areas, employees, must_off, max_shifts_per_week, max_weekend_shifts, start_date, num_weeks):
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
                total_shifts[area] += required[day][area][shift] * num_weeks
    
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
    
    # Max shifts per employee
    avg_max_shifts = sum(max_shifts_per_week.values()) / len(max_shifts_per_week) if max_shifts_per_week else 3.067
    
    # Adjust for must-have-off within the schedule period
    unavailable_shifts = {"Bar": 0, "Kitchen": 0}
    for emp in must_off:
        for _, date_str in must_off[emp]:
            try:
                off_date = datetime.strptime(date_str, "%Y-%m-%d")
                delta = (off_date - start_date).days
                if 0 <= delta < 7 * num_weeks:
                    for area in work_areas[emp]:
                        unavailable_shifts[area] += 1
            except:
                continue
    
    # Minimum employees needed
    needed = {"Bar": 0, "Kitchen": 0}
    for area in areas:
        shifts_needed = total_shifts[area] + unavailable_shifts[area]
        employees_by_total = math.ceil(shifts_needed / (avg_max_shifts * num_weeks))
        employees_by_weekend = math.ceil(weekend_shifts[area] / (max_weekend_shifts * num_weeks))
        needed[area] = max(employees_by_total, employees_by_weekend)
        if area == "Bar" and num_weeks == 2:
            needed[area] = max(needed[area], 6)
    
    return current, needed

# Function to parse CSV files
def load_csv(emp_file, req_file, limits_file, start_date):
    try:
        emp_df = pd.read_csv(emp_file, index_col=0)
        emp_df.index = emp_df.index.astype(str).str.strip().str.lower()
        if emp_df.index.isna().any() or "" in emp_df.index:
            raise ValueError("Employee_Data.csv has invalid or missing index values")
        employees = [col for col in emp_df.columns if pd.notna(col)]
        if not employees:
            raise ValueError("No valid employee columns found in Employee_Data.csv")
        
        work_areas = {}
        area_row = "work area"
        if area_row not in emp_df.index:
            raise ValueError("Cannot find 'Work Area' row in Employee_Data.csv")
        areas = ["Bar", "Kitchen"]
        for emp in employees:
            area = emp_df.loc[area_row, emp]
            if pd.notna(area) and area in areas:
                work_areas[emp] = [area]
            else:
                raise ValueError(f"Invalid work area for {emp}: {area}")
        
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
        
        must_off = {}
        off_row = "must have off"
        if off_row not in emp_df.index:
            print("Warning: Cannot find 'Must have off' row, assuming none")
        else:
            for emp in employees:
                off_dates_str = emp_df.loc[off_row, emp]
                if pd.notna(off_dates_str):
                    off_dates = [d.strip() for d in str(off_dates_str).split(',')]
                    must_off[emp] = []
                    for date_str in off_dates:
                        try:
                            off_date = pd.to_datetime(date_str)
                            delta = (off_date - start_date).days
                            if 0 <= delta < 7 * num_weeks_var.get():
                                day_name = off_date.strftime("%a")
                                must_off[emp].append((day_name, off_date.strftime("%Y-%m-%d")))
                            else:
                                print(f"Warning: Must-have-off date {off_date.strftime('%Y-%m-%d')} for {emp} outside schedule, ignoring")
                        except:
                            print(f"Warning: Invalid date format '{date_str}' for {emp}'s must-have-off")
        
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
        
        limits_df = pd.read_csv(limits_file)
        if limits_df.empty:
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
                  relax_day=True, relax_shift=True, relax_weekend=True, relax_min_shifts=True, num_weeks=2):
    prob = pulp.LpProblem("Restaurant_Schedule", pulp.LpMaximize)
    
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
    
    day_penalty = -10 if relax_day else 0
    shift_penalty = -10 if relax_shift else 0
    min_shifts_penalty = -100 if relax_min_shifts else 0
    prob += pulp.lpSum(
        x[e][w][d][s][a] * (
            (day_prefs[e][d] if day_prefs[e][d] > 0 else day_penalty) +
            (shift_prefs[e][s] if shift_prefs[e][s] > 0 else shift_penalty)
        )
        for e in employees for w in range(num_weeks) for d in days for s in shifts for a in work_areas[e]
    )
    
    for w in range(num_weeks):
        for d in days:
            for a in areas:
                for s in shifts:
                    prob += pulp.lpSum(x[e][w][d][s][a] for e in employees if a in work_areas[e]) == required[d][a][s]
    
    for e in must_off:
        for _, date_str in must_off[e]:
            delta = (datetime.strptime(date_str, "%Y-%m-%d") - start_date).days
            if 0 <= delta < 7 * num_weeks:
                w = delta // 7
                d = days[delta % 7]
                for s in shifts:
                    for a in work_areas[e]:
                        prob += x[e][w][d][s][a] == 0
    
    for e in employees:
        for w in range(num_weeks):
            for d in days:
                prob += pulp.lpSum(x[e][w][d][s][a] for s in shifts for a in work_areas[e]) <= constraints["max_shifts_per_day"]
    
    for e in employees:
        for w in range(num_weeks):
            prob += pulp.lpSum(x[e][w][d][s][a] for d in days for s in shifts for a in work_areas[e]) <= max_shifts[e]
    
    if relax_min_shifts:
        for e in employees:
            for w in range(num_weeks):
                prob += pulp.lpSum(x[e][w][d][s][a] for d in days for s in shifts for a in work_areas[e]) >= min_shifts[e]
    
    schedule_days = [(w, d) for w in range(num_weeks) for d in days]
    fri_sun_windows = []
    for w in range(num_weeks):
        if w < num_weeks - 1 or num_weeks == 1:
            fri_sun_windows.append([(w, "Fri"), (w, "Sat"), (w, "Sun")])
        else:
            fri_sun_windows.append([(w, "Fri"), (w, "Sat")])
    for e in employees:
        for window in fri_sun_windows:
            prob += pulp.lpSum(
                x[e][w][d][s][a]
                for w, d in window
                for s in shifts
                for a in work_areas[e]
            ) <= constraints["max_weekend_days"]
    
    prob.solve()
    return prob, x

# Function to validate weekend constraints
def validate_weekend_constraints(x, employees, days, shifts, work_areas, max_weekend_days, start_date, num_weeks):
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
    return violations

# Function to generate schedule with relaxation
def generate_schedule():
    global start_date, num_weeks_var, all_trees
    try:
        start_date = start_date_entry.get_date()
        num_weeks = num_weeks_var.get()
        if not isinstance(num_weeks, int) or num_weeks < 1:
            messagebox.showerror("Error", "Number of weeks must be an integer >= 1")
            return
    except:
        messagebox.showerror("Error", "Invalid start date or number of weeks")
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
            idx = list(relax_map.keys()).index(rule)
            current[idx] = False
        relax_order.append(tuple(current) + (f"Relax {', '.join(constraints['violate_order'][:i])}",))
    
    solution = None
    x = None
    relaxed_message = ""
    for relax_day, relax_shift, relax_weekend, relax_min_shifts, msg in relax_order:
        prob, x = solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas,
                                 constraints, min_shifts, max_shifts, relax_day, relax_shift, relax_weekend, relax_min_shifts, num_weeks)
        if prob.status == pulp.LpStatusOptimal:
            relaxed_message = msg
            solution = prob
            break
    
    # Clear existing schedules
    for widget in bar_frame.winfo_children():
        widget.destroy()
    for widget in kitchen_frame.winfo_children():
        widget.destroy()
    all_trees = []
    
    if solution and solution.status == pulp.LpStatusOptimal:
        violations = validate_weekend_constraints(x, employees, days, shifts, work_areas, constraints["max_weekend_days"], start_date, num_weeks)
        violation_message = "\n".join(violations) if violations else "None"
        messagebox.showinfo("Success", f"Optimal schedule found! ({relaxed_message})\nWeekend constraint violations:\n{violation_message}")
        
        total_days = 7 * num_weeks
        dates = [(start_date + timedelta(days=i)) for i in range(total_days)]
        start_weekday = start_date.weekday()
        day_names = days[start_weekday:] + days[:start_weekday]
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
            bar_tree = ttk.Treeview(bar_frame, columns=["Day/Shift"] + [f"Day{i}" for i in range(7)], show="headings", height=2)
            bar_tree.heading("Day/Shift", text="Day/Shift")
            bar_tree.column("Day/Shift", width=80, anchor="w")
            for i in range(7):
                text = week_cols[i] if i < len(week_cols) else ""
                bar_tree.heading(f"Day{i}", text=text)
                bar_tree.column(f"Day{i}", width=100, anchor="center")
            all_trees.append(bar_tree)
            # Create Treeview for Kitchen week
            tk.Label(kitchen_frame, text=f"Kitchen Schedule Week {w+1}").pack(pady=5)
            kitchen_tree = ttk.Treeview(kitchen_frame, columns=["Day/Shift"] + [f"Day{i}" for i in range(7)], show="headings", height=2)
            kitchen_tree.heading("Day/Shift", text="Day/Shift")
            kitchen_tree.column("Day/Shift", width=80, anchor="w")
            for i in range(7):
                text = week_cols[i] if i < len(week_cols) else ""
                kitchen_tree.heading(f"Day{i}", text=text)
                kitchen_tree.column(f"Day{i}", width=100, anchor="center")
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
        
        with open("Bar_schedule.csv", "w", newline="") as f:
            writer = csv.writer(f)
            for row in bar_schedule:
                if row:
                    writer.writerow(row)
        
        with open("Kitchen_schedule.csv", "w", newline="") as f:
            writer = csv.writer(f)
            for row in kitchen_schedule:
                if row:
                    writer.writerow(row)
        
        # Adjust column widths initially
        adjust_column_widths()
    else:
        current, needed = calculate_min_employees(required, work_areas, employees, must_off, max_shifts, constraints["max_weekend_days"], start_date, num_weeks)
        error_message = (
            f"No feasible schedule found even after relaxing all constraints.\n"
            f"Check staffing requirements or employee availability.\n"
            f"Current Bar: {current['Bar']}, Needed Bar: {needed['Bar']}\n"
            f"Current Kitchen: {current['Kitchen']}, Needed Kitchen: {needed['Kitchen']}"
        )
        messagebox.showerror("Error", error_message)

# Function to adjust column widths on resize
def adjust_column_widths():
    global all_trees
    width = root.winfo_width()
    for tree in all_trees:
        cols = [c for c in tree["columns"] if c != "Day/Shift"]
        if cols:
            col_width = max(100, (width - 80 - 40) // len(cols))  # Adjust for paddings and scrollbar
            for c in cols:
                tree.column(c, width=col_width)

# Resize event handler
def on_resize(event):
    if event.widget == root:
        adjust_column_widths()

# Mousewheel event handler
def on_mousewheel(event):
    canvas.yview_scroll(-1 * (event.delta // 120), "units")

# Function to display input data
def display_input_data():
    # Employee Data
    emp_file = emp_file_var.get()
    emp_text.delete("1.0", tk.END)
    if emp_file:
        try:
            df = pd.read_csv(emp_file)
            emp_text.insert(tk.END, df.to_string())
        except Exception as e:
            emp_text.insert(tk.END, f"Error loading file: {str(e)}")
    
    # Personel Required
    req_file = req_file_var.get()
    req_text.delete("1.0", tk.END)
    if req_file:
        try:
            df = pd.read_csv(req_file)
            req_text.insert(tk.END, df.to_string())
        except Exception as e:
            req_text.insert(tk.END, f"Error loading file: {str(e)}")
    
    # Hard Limits
    limits_file = limits_file_var.get()
    limits_text.delete("1.0", tk.END)
    if limits_file:
        try:
            df = pd.read_csv(limits_file)
            limits_text.insert(tk.END, df.to_string())
        except Exception as e:
            limits_text.insert(tk.END, f"Error loading file: {str(e)}")

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
canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

# Update scroll region when frame size changes
def on_frame_configure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))

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

# Load saved file paths
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

# Global list for trees
all_trees = []

root.mainloop()