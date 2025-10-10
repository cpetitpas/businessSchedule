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
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Global variables for drag-and-drop
all_listboxes = []
floating_label = None

def start_drag(event):
    global floating_label
    widget = event.widget
    widget.dragged_item = widget.curselection()
    if widget.dragged_item:
        widget.dragged_item = widget.dragged_item[0]
        widget.selected_item = widget.get(widget.dragged_item)
        
        floating_label = tk.Label(widget.master, text=widget.selected_item, bg="yellow", relief="solid")
        
        x_offset = widget.master.winfo_pointerx() - widget.master.winfo_rootx()
        y_offset = widget.master.winfo_pointery() - widget.master.winfo_rooty()
        floating_label.place(x=x_offset, y=y_offset)

def on_drag(event):
    global floating_label
    if floating_label:
        x_offset = event.widget.master.winfo_pointerx() - event.widget.master.winfo_rootx()
        y_offset = event.widget.master.winfo_pointery() - event.widget.master.winfo_rooty()
        floating_label.place(x=x_offset, y=y_offset)

def on_drop(event):
    global floating_label, all_listboxes
    source = event.widget
    target = None
    
    if floating_label:
        floating_label.place_forget()
    
    # Find target listbox
    for lst in all_listboxes:
        if lst.winfo_containing(event.x_root, event.y_root) == lst:
            target = lst
            break
    
    if target and source != target and source.selected_item:
        source.delete(source.dragged_item)
        target.insert("end", source.selected_item)
    
    if floating_label:
        floating_label.destroy()
        floating_label = None

def apply_changes(listboxes_dict, employees, num_weeks, areas, shifts, days, work_areas, max_weekend_days, start_date, dates, relaxed_message, employee_message, summary_text, viz_frame):
    # Reconstruct x as dict with int values
    x = {e: {w: {d: {s: {a: 0 for a in work_areas.get(e, [])} for s in shifts} for d in days} for w in range(num_weeks)} for e in employees}
    
    for w in range(num_weeks):
        for a in areas:
            for s in shifts:
                for d_idx in range(7):
                    lb = listboxes_dict[w][a][s][d_idx]
                    emps = lb.get(0, 'end')
                    day_name = dates[w * 7 + d_idx].strftime('%a')
                    for e in emps:
                        if e in x and a in x[e][w][day_name][s]:
                            x[e][w][day_name][s][a] = 1
    
    violations = validate_weekend_constraints(x, employees, days, shifts, work_areas, max_weekend_days, start_date, num_weeks)
    violation_message = "\n".join(violations) if violations else "None"
    message = (
        f"Schedule updated! ({relaxed_message})\n"
        f"{employee_message}\n"
        f"Weekend constraint violations:\n{violation_message}"
    )
    messagebox.showinfo("Success", message)
    logging.info("Manual schedule update: %s", message)
    
    # Regenerate CSVs
    date_str = datetime.now().strftime('%Y-%m-%d')
    bar_schedule = []
    kitchen_schedule = []
    for w in range(num_weeks):
        week_cols = [dates[w * 7 + i].strftime('%a, %b %d, %y') for i in range(7)]
        bar_schedule.extend([
            ["Day/Shift"] + week_cols,
            ["Morning"] + [", ".join(listboxes_dict[w]['Bar']['Morning'][i].get(0, 'end')) for i in range(7)],
            ["Evening"] + [", ".join(listboxes_dict[w]['Bar']['Evening'][i].get(0, 'end')) for i in range(7)],
            []
        ])
        kitchen_schedule.extend([
            ["Day/Shift"] + week_cols,
            ["Morning"] + [", ".join(listboxes_dict[w]['Kitchen']['Morning'][i].get(0, 'end')) for i in range(7)],
            ["Evening"] + [", ".join(listboxes_dict[w]['Kitchen']['Evening'][i].get(0, 'end')) for i in range(7)],
            []
        ])
    
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
    
    # Update summary report
    summary_text.delete("1.0", tk.END)
    summary = generate_summary(x, employees, num_weeks, days, shifts, work_areas, violations, relaxed_message, date_str)
    summary_text.insert(tk.END, summary)
    
    # Update visualization
    for widget in viz_frame.winfo_children():
        widget.destroy()
    generate_visualization(x, employees, num_weeks, days, shifts, work_areas, viz_frame)

def generate_schedule(emp_file_var, req_file_var, limits_file_var, start_date_entry, num_weeks_var, bar_frame, kitchen_frame, all_listboxes_ref, summary_text, viz_frame):
    global all_listboxes
    all_listboxes = all_listboxes_ref  # Assign the passed reference to the global variable
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
    all_listboxes.clear()
    
    # Clear summary and viz
    summary_text.delete("1.0", tk.END)
    for widget in viz_frame.winfo_children():
        widget.destroy()
    
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
        
        # Dict for listboxes: listboxes[w][a][s][d_idx] = lb
        listboxes_dict = {w: {a: {s: [None] * 7 for s in shifts} for a in areas} for w in range(num_weeks)}
        
        for w in range(num_weeks):
            week_cols = [d.strftime('%a, %b %d, %y') for d in dates[w * 7:(w + 1) * 7]]
            
            for a_idx, a in enumerate(areas):
                frame = bar_frame if a == 'Bar' else kitchen_frame
                tk.Label(frame, text=f"{a} Schedule Week {w+1}").pack(pady=5)
                
                # Day headers
                day_frame = tk.Frame(frame)
                tk.Label(day_frame, text="Shift/Day", width=10).pack(side='left')
                for col in week_cols:
                    tk.Label(day_frame, text=col, width=15).pack(side='left')
                day_frame.pack()
                
                for s in shifts:
                    shift_frame = tk.Frame(frame)
                    tk.Label(shift_frame, text=s, width=10).pack(side='left')
                    
                    for d_idx in range(7):
                        lb = tk.Listbox(shift_frame, height=3, width=15, selectmode='single')
                        lb.pack(side='left')
                        listboxes_dict[w][a][s][d_idx] = lb
                        all_listboxes.append(lb)
                        
                        # Bind drag events
                        lb.bind("<ButtonPress-1>", start_drag)
                        lb.bind("<B1-Motion>", on_drag)
                        lb.bind("<ButtonRelease-1>", on_drop)
                        
                        # Populate
                        d = dates[w * 7 + d_idx]
                        day_name = d.strftime('%a')
                        assigned = [e for e in employees if a in work_areas[e] and pulp.value(x[e][w][day_name][s][a]) == 1]
                        for e in assigned:
                            lb.insert('end', e)
                    
                    shift_frame.pack(pady=5)
        
        # Add Apply Changes button
        apply_button = tk.Button(bar_frame.master, text="Apply Changes", command=lambda: apply_changes(listboxes_dict, employees, num_weeks, areas, shifts, days, work_areas, max_weekend_days, start_date, dates, relaxed_message, employee_message, summary_text, viz_frame))
        apply_button.pack(pady=10)
        
        # Generate initial CSVs as before
        bar_schedule = []
        kitchen_schedule = []
        for w in range(num_weeks):
            week_cols = [dates[w * 7 + i].strftime('%a, %b %d, %y') for i in range(7)]
            bar_schedule.extend([
                ["Day/Shift"] + week_cols,
                ["Morning"] + [", ".join(listboxes_dict[w]['Bar']['Morning'][i].get(0, 'end')) for i in range(7)],
                ["Evening"] + [", ".join(listboxes_dict[w]['Bar']['Evening'][i].get(0, 'end')) for i in range(7)],
                []
            ])
            kitchen_schedule.extend([
                ["Day/Shift"] + week_cols,
                ["Morning"] + [", ".join(listboxes_dict[w]['Kitchen']['Morning'][i].get(0, 'end')) for i in range(7)],
                ["Evening"] + [", ".join(listboxes_dict[w]['Kitchen']['Evening'][i].get(0, 'end')) for i in range(7)],
                []
            ])
        
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
        
        # Generate summary report
        summary = generate_summary(x, employees, num_weeks, days, shifts, work_areas, violations, relaxed_message, date_str)
        summary_text.insert(tk.END, summary)
        
        # Generate visualization
        generate_visualization(x, employees, num_weeks, days, shifts, work_areas, viz_frame)
        
    else:
        error_message = (
            f"No feasible schedule found even after relaxing all constraints.\n"
            f"Check staffing requirements or employee availability.\n"
            f"{employee_message}"
        )
        messagebox.showerror("Error", error_message)
        logging.error(error_message)
    
    logging.debug("Exiting generate_schedule")

def generate_summary(x, employees, num_weeks, days, shifts, work_areas, violations, relaxed_message, date_str):
    summary_lines = ["Summary Report\n"]
    summary_lines.append(f"Relaxed Constraints: {relaxed_message}\n")
    summary_lines.append("Weekend Violations:\n" + ("\n".join(violations) if violations else "None") + "\n")
    
    total_shifts = {e: 0 for e in employees}
    weekly_shifts = {e: [0] * num_weeks for e in employees}
    for e in employees:
        for w in range(num_weeks):
            for d in days:
                for s in shifts:
                    for a in work_areas.get(e, []):
                        if pulp.value(x[e][w][d][s][a]) == 1:
                            weekly_shifts[e][w] += 1
                            total_shifts[e] += 1
    summary_lines.append("Total Shifts per Employee:\n")
    for e, total in sorted(total_shifts.items(), key=lambda item: item[1], reverse=True):
        summary_lines.append(f"{e}: {total}\n")
    summary_lines.append("\nWeekly Shifts:\n")
    for e in employees:
        summary_lines.append(f"{e}: {weekly_shifts[e]}\n")
    
    summary_str = "".join(summary_lines)
    with open(f"Summary_report_{date_str}.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Employee", "Total Shifts"] + [f"Week {w+1}" for w in range(num_weeks)])
        for e in employees:
            writer.writerow([e, total_shifts[e]] + weekly_shifts[e])
    logging.info("Summary report saved to Summary_report_%s.csv", date_str)
    return summary_str

def generate_visualization(x, employees, num_weeks, days, shifts, work_areas, viz_frame):
    total_shifts = {e: 0 for e in employees}
    for e in employees:
        for w in range(num_weeks):
            for d in days:
                for s in shifts:
                    for a in work_areas.get(e, []):
                        if pulp.value(x[e][w][d][s][a]) == 1:
                            total_shifts[e] += 1
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(total_shifts.keys(), total_shifts.values(), color='#1f77b4')
    ax.set_xlabel("Employees")
    ax.set_ylabel("Total Shifts")
    ax.set_title("Total Shifts per Employee")
    ax.tick_params(axis='x', rotation=45)
    plt.tight_layout()
    
    canvas = FigureCanvasTkAgg(fig, master=viz_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    plt.close(fig)  # Close the figure to free memory

def display_input_data(emp_file_var, req_file_var, limits_file_var, emp_text, req_text, limits_text, notebook, summary_text):
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
    adjust_column_widths(tk._default_root, [], notebook, emp_text, req_text, limits_text, summary_text)  # Ensure tabs resize after loading data
    logging.debug("Exiting display_input_data")