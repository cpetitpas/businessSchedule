import pulp
import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
from datetime import datetime

# Function to parse Excel file
def load_excel(file_path):
    try:
        xl = pd.ExcelFile(file_path)
        if "Weighted Inputs" not in xl.sheet_names or "Hard Requirements" not in xl.sheet_names:
            raise ValueError("Excel file must contain 'Weighted Inputs' and 'Hard Requirements' sheets")

        # Parse Weighted Inputs (transposed for employee columns)
        weighted_df = xl.parse("Weighted Inputs", index_col=0).T
        employees = weighted_df.columns.tolist()
        
        # Shift preferences
        shift_prefs = {}
        for emp in employees:
            shift = weighted_df.loc["Shift Weight", emp]
            if pd.isna(shift):
                shift_prefs[emp] = {"Morning": 0, "Evening": 0}
            else:
                shift_prefs[emp] = {
                    "Morning": 10 if shift == "Morning" else 0,
                    "Evening": 10 if shift == "Evening" else 0
                }
        
        # Day preferences
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        day_prefs = {}
        for emp in employees:
            day_str = weighted_df.loc["Day Weights", emp]
            preferred_days = day_str.split(", ") if pd.notna(day_str) else []
            day_prefs[emp] = {day: 10 if day in preferred_days else 0 for day in days}
        
        # Must-have-off
        must_off = {}
        for emp in employees:
            off_date = weighted_df.loc["Must have off", emp]
            if pd.notna(off_date):
                try:
                    off_date = pd.to_datetime(off_date)
                    day_name = off_date.strftime("%a")
                    must_off[emp] = [day_name]
                except:
                    print(f"Warning: Invalid date format for {emp}'s must-have-off")
        
        # Parse Hard Requirements
        req_df = xl.parse("Hard Requirements", index_col=0)
        areas = ["Bar", "Kitchen"]
        required = {}
        for day in days:
            required[day] = {}
            for area in areas:
                counts = req_df.loc[area, day].split("/") if pd.notna(req_df.loc[area, day]) else ["0", "0"]
                required[day][area] = {
                    "Morning": int(counts[0]),
                    "Evening": int(counts[1])
                }
        
        # Parse Work Area assignments
        work_areas = {}
        for emp in employees:
            area = req_df.loc["Employee/Work Area", emp]
            work_areas[emp] = [area] if pd.notna(area) else areas
        
        return employees, days, ["Morning", "Evening"], areas, shift_prefs, day_prefs, must_off, required, work_areas
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load Excel file: {str(e)}")
        return None

# Function to solve scheduling problem
def solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas,
                  relax_shift=True, relax_day=True, relax_weekend=True, relax_one_shift=True):
    prob = pulp.LpProblem("Restaurant_Schedule", pulp.LpMaximize)
    
    # Decision variables (only for allowed work areas)
    x = {}
    for e in employees:
        x[e] = {}
        for d in days:
            x[e][d] = {}
            for s in shifts:
                x[e][d][s] = {}
                for a in work_areas[e]:
                    x[e][d][s][a] = pulp.LpVariable(f"assign_{e}_{d}_{s}_{a}", cat="Binary")
    
    # Objective: Maximize preferences, penalize violations
    shift_penalty = -10 if relax_shift else 0
    day_penalty = -10 if relax_day else 0
    prob += pulp.lpSum(
        x[e][d][s][a] * (
            (day_prefs[e][d] if day_prefs[e][d] > 0 else day_penalty) +
            (shift_prefs[e][s] if shift_prefs[e][s] > 0 else shift_penalty)
        )
        for e in employees for d in days for s in shifts for a in work_areas[e]
    )
    
    # Constraints
    # 1. Staffing requirements (hard)
    for d in days:
        for a in areas:
            for s in shifts:
                prob += pulp.lpSum(x[e][d][s][a] for e in employees if a in work_areas[e]) == required[d][a][s]
    
    # 2. Must-have-off (hard)
    for e in must_off:
        for d in must_off[e]:
            for s in shifts:
                for a in work_areas[e]:
                    prob += x[e][d][s][a] == 0
    
    # 3. One shift per day (relaxable)
    if relax_one_shift:
        for e in employees:
            for d in days:
                prob += pulp.lpSum(x[e][d][s][a] for s in shifts for a in work_areas[e]) <= 1
    
    # 4. One shift Fri–Sun (relaxable)
    if relax_weekend:
        weekend_days = ["Fri", "Sat", "Sun"]
        for e in employees:
            prob += pulp.lpSum(x[e][d][s][a] for d in weekend_days for s in shifts for a in work_areas[e]) <= 1
    
    # Solve
    prob.solve()
    return prob, x

# Function to generate schedule with relaxation
def generate_schedule():
    file_path = file_var.get()
    if not file_path:
        messagebox.showerror("Error", "Please select an Excel file")
        return
    
    data = load_excel(file_path)
    if not data:
        return
    
    employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas = data
    
    # Try solving with increasing relaxation
    relaxations = [
        (True, True, True, True, "All constraints enforced"),
        (False, True, True, True, "Relax shift preferences"),
        (False, False, True, True, "Relax shift and day preferences"),
        (False, False, False, True, "Relax shift, day, and Fri–Sun constraints"),
        (False, False, False, False, "Relax all constraints")
    ]
    
    solution = None
    x = None
    relaxed_message = ""
    for relax_shift, relax_day, relax_weekend, relax_one_shift, msg in relaxations:
        prob, x = solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas,
                                 relax_shift, relax_day, relax_weekend, relax_one_shift)
        if prob.status == pulp.LpStatusOptimal:
            relaxed_message = msg
            solution = prob
            break
    
    # Display results
    tree.delete(*tree.get_children())
    if solution and solution.status == pulp.LpStatusOptimal:
        messagebox.showinfo("Success", f"Optimal schedule found! ({relaxed_message})")
        with open("schedule_output.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Day", "Area", "Shift", "Employees"])
            for d in days:
                for a in areas:
                    for s in shifts:
                        assigned = [e for e in employees if a in work_areas[e] and pulp.value(x[e][d][s][a]) == 1]
                        tree.insert("", "end", values=(d, a, s, ", ".join(assigned)))
                        writer.writerow([d, a, s, ", ".join(assigned)])
    else:
        messagebox.showerror("Error", "No feasible schedule found even after relaxing all constraints.")

# Tkinter GUI
root = tk.Tk()
root.title("Restaurant Scheduler")
root.geometry("800x600")

# File selection
file_var = tk.StringVar()
tk.Label(root, text="Select Excel File:").pack(pady=5)
tk.Entry(root, textvariable=file_var, width=50).pack(pady=5)
tk.Button(root, text="Browse", command=lambda: file_var.set(filedialog.askopenfilename(filetypes=[("Excel files", "*.xls *.xlsx")]))).pack(pady=5)

# Schedule display
tree = ttk.Treeview(root, columns=("Day", "Area", "Shift", "Employees"), show="headings")
tree.heading("Day", text="Day")
tree.heading("Area", text="Area")
tree.heading("Shift", text="Shift")
tree.heading("Employees", text="Employees")
tree.pack(pady=10, fill="both", expand=True)

# Generate button
tk.Button(root, text="Generate Schedule", command=generate_schedule).pack(pady=5)

root.mainloop()