import csv
from datetime import datetime, timedelta
import logging
import pulp
import pandas as pd
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk
from data_loader import load_csv
from solver import solve_schedule, validate_weekend_constraints
from utils import calculate_min_employees, adjust_column_widths
from constants import DAYS, SHIFTS, AREAS

def generate_schedule(emp_file_var, req_file_var, limits_file_var, start_date_entry, num_weeks_var, bar_frame, kitchen_frame, all_trees):
    logging.debug("Entering generate_schedule")
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
    
    data = load_csv(emp_file, req_file, limits_file, start_date, num_weeks_var)
    if not data:
        logging.error("load_csv returned None")
        return
    
    employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days = data
    
    # Calculate current and needed employees
    current, needed = calculate_min_employees(required, work_areas, employees, must_off, max_shifts, max_weekend_days, start_date, num_weeks)
    
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
                                 constraints, min_shifts, max_shifts, max_weekend_days, start_date, relax_day, relax_shift, relax_weekend, relax_min_shifts, num_weeks)
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
    all_trees.clear()
    
    employee_message = (
        f"Current Employees - Bar: {current['Bar']}, Kitchen: {current['Kitchen']}\n"
        f"Minimum Employees Needed - Bar: {needed['Bar']}, Kitchen: {needed['Kitchen']}"
    )
    logging.info(employee_message)
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    if solution and solution.status == pulp.LpStatusOptimal:
        violations = validate_weekend_constraints(x, employees, days, shifts, work_areas, max_weekend_days, start_date, num_weeks)
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
        columns = [f"{d.strftime('%a')}, {d.strftime('%b %d, %y')}" for d in dates]
        
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
                    d = dates[w * 7 + d_idx]
                    day_name = d.strftime('%a')
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
    else:
        error_message = (
            f"No feasible schedule found even after relaxing all constraints.\n"
            f"Check staffing requirements or employee availability.\n"
            f"{employee_message}"
        )
        messagebox.showerror("Error", error_message)
        logging.error(error_message)
    
    logging.debug("Exiting generate_schedule")

def display_input_data(emp_file_var, req_file_var, limits_file_var, emp_text, req_text, limits_text, notebook):
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
    from utils import adjust_column_widths
    adjust_column_widths(tk._default_root, [], notebook, emp_text, req_text, limits_text)  # Ensure tabs resize after loading data
    logging.debug("Exiting display_input_data")