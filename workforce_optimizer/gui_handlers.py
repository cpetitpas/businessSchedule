import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import datetime
from tkcalendar import Calendar
from solver import solve_schedule, validate_weekend_constraints
from data_loader import load_csv
from constants import AREAS
import pulp
import math
import logging
import matplotlib.pyplot as plt
import numpy as np
import os
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from utils import min_employees_to_avoid_weekend_violations, adjust_column_widths

logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

# Global list to store Treeview widgets for dynamic column width adjustment
all_input_trees = []
all_listboxes = []

def find_treeviews(widget):
    """
    Recursively find all ttk.Treeview widgets in the widget and its descendants.
    """
    treeviews = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Treeview):
            treeviews.append(child)
        else:
            treeviews.extend(find_treeviews(child))
    return treeviews

def display_input_data(emp_path, req_path, limits_path, emp_frame, req_frame, limits_frame, root, notebook, summary_text):
    """
    Load CSV files into Treeview widgets for all input tabs (Employee Data, Personnel Required, Hard Limits).
    """
    global all_input_trees, all_listboxes
    all_input_trees = []

    def create_treeview(frame, csv_file, has_index=True):
        for widget in frame.winfo_children():
            widget.destroy()

        try:
            df = pd.read_csv(csv_file, index_col=0 if has_index else None)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load {csv_file}: {e}")
            return None

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        tree_frame = ttk.Frame(frame)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree = ttk.Treeview(tree_frame, show="headings")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        all_input_trees.append(tree)

        def _on_mousewheel(event):
            if event.delta:
                tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                tree.yview_scroll(-1, "units")
            elif event.num == 5:
                tree.yview_scroll(1, "units")
        tree.bind("<MouseWheel>", _on_mousewheel)
        tree.bind("<Button-4>", _on_mousewheel)
        tree.bind("<Button-5>", _on_mousewheel)

        columns = list(df.columns)
        if has_index:
            index_name = df.index.name or "Index"
            columns = [index_name] + columns

        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=100)

        for idx, row in df.iterrows():
            values = ['' if pd.isna(val) else str(val) for val in row]
            if has_index:
                values = [str(idx)] + values
            tree.insert("", "end", iid=str(idx) if has_index else f"row_{idx}", values=values)

        tree.bind("<Double-1>", lambda event: on_tree_double_click(tree, event, has_index))
        return tree

    create_treeview(emp_frame, emp_path, has_index=False)
    create_treeview(req_frame, req_path, has_index=False)
    create_treeview(limits_frame, limits_path, has_index=True)

    adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)

def save_input_data(emp_path, req_path, limits_path, emp_frame, req_frame, limits_frame, root):
    """
    Save the edited data from Treeview widgets back to their respective CSV files with overwrite prompt and option to save as a different filename.
    """
    def tree_to_df(tree, has_index=True):
        columns = tree["columns"]
        data = []
        index = []
        for item in tree.get_children():
            values = [tree.set(item, col) for col in columns]
            if has_index:
                index.append(values[0])
                data.append(values[1:])
            else:
                data.append(values)
        if has_index:
            return pd.DataFrame(data, index=index, columns=columns[1:])
        return pd.DataFrame(data, columns=columns)

    def get_save_filename(default_path, file_type):
        """Get filename with overwrite check and new filename option."""
        if os.path.exists(default_path):
            if not messagebox.askyesno("Overwrite?", f"File {default_path} already exists. Overwrite?"):
                # Create dialog for new filename
                dialog = tk.Toplevel(root)
                dialog.title(f"Save {file_type} As")
                dialog.geometry("400x150")
                
                # Center the dialog relative to the root window
                dialog.transient(root)
                dialog.update_idletasks()
                x = root.winfo_x() + (root.winfo_width() // 2) - (dialog.winfo_width() // 2)
                y = root.winfo_y() + (root.winfo_height() // 2) - (dialog.winfo_height() // 2)
                dialog.geometry(f"400x150+{x}+{y}")
                
                tk.Label(dialog, text="Enter filename:").pack(pady=5)
                filename_entry = tk.Entry(dialog)
                filename_entry.insert(0, default_path)
                filename_entry.pack(pady=5, fill="x", padx=10)
                
                save_clicked = [False]  # Use list to modify in nested function
                def save_new_filename():
                    nonlocal default_path
                    filename = filename_entry.get().strip()
                    if not filename:
                        messagebox.showerror("Error", "Filename cannot be empty.")
                        return
                    if not filename.lower().endswith(".csv"):
                        filename += ".csv"
                    default_path = filename
                    save_clicked[0] = True
                    dialog.destroy()
                
                def cancel_save():
                    save_clicked[0] = None  # Indicate cancellation
                    dialog.destroy()
                
                tk.Button(dialog, text="Save", command=save_new_filename).pack(pady=5)
                tk.Button(dialog, text="Cancel", command=cancel_save).pack(pady=5)
                
                dialog.transient(root)
                dialog.grab_set()
                root.wait_window(dialog)
                
                if save_clicked[0] is None:
                    return None  # User canceled
        
        return default_path

    save_messages = []
    
    try:
        # Employee Data
        emp_tree = next((w for w in emp_frame.winfo_children()[0].winfo_children() if isinstance(w, ttk.Treeview)), None)
        if emp_tree:
            filename = get_save_filename(emp_path, "Employee Data")
            if filename:
                emp_df = tree_to_df(emp_tree, has_index=True)
                emp_df.index.name = "Employee/Input"
                emp_df.to_csv(filename)
                save_messages.append(f"Saved Employee Data to {filename}")
                logging.info(f"Saved Employee Data to {filename}")

        # Personnel Required
        req_tree = next((w for w in req_frame.winfo_children()[0].winfo_children() if isinstance(w, ttk.Treeview)), None)
        if req_tree:
            filename = get_save_filename(req_path, "Personnel Required")
            if filename:
                req_df = tree_to_df(req_tree, has_index=True)
                req_df.index.name = "Day/Required"
                req_df.to_csv(filename)
                save_messages.append(f"Saved Personnel Required to {filename}")
                logging.info(f"Saved Personnel Required to {filename}")

        # Hard Limits
        limits_tree = next((w for w in limits_frame.winfo_children()[0].winfo_children() if isinstance(w, ttk.Treeview)), None)
        if limits_tree:
            filename = get_save_filename(limits_path, "Hard Limits")
            if filename:
                limits_df = tree_to_df(limits_tree, has_index=False)
                limits_df.to_csv(filename, index=False)
                save_messages.append(f"Saved Hard Limits to {filename}")
                logging.info(f"Saved Hard Limits to {filename}")

        if save_messages:
            messagebox.showinfo("Success", "\n".join(save_messages))
        else:
            messagebox.showwarning("Warning", "No input data was saved.")
            
    except Exception as e:
        logging.error(f"Failed to save input data: {str(e)}")
        messagebox.showerror("Error", f"Failed to save input data: {str(e)}")

def on_tree_double_click(tree, event, has_index):
    """
    Handle double-click on Treeview to edit cell content.
    """
    item = tree.identify_row(event.y)
    column = tree.identify_column(event.x)
    if not item or not column:
        return

    col_idx = int(column.replace('#', '')) - 1
    col_name = tree["columns"][col_idx]
    
    # Don't allow editing the first column for tables with index (Employee Data, Personnel Required)
    # Only allow first column editing for Hard Limits (has_index=False)
    if col_idx == 0 and has_index:
        return

    current_value = tree.set(item, col_name)

    entry = tk.Entry(tree)
    entry.insert(0, current_value)
    entry.bind("<Return>", lambda _: update_cell())
    entry.bind("<FocusOut>", lambda _: update_cell())
    
    def update_cell():
        new_value = entry.get()
        tree.set(item, col_name, new_value)
        entry.destroy()

    x, y, width, height = tree.bbox(item, column)
    entry.place(x=x, y=y, width=width, height=height)
    entry.focus_set()

def edit_schedule_cell(tree, event, area, emp_file_path):
    """
    Handle double-click on schedule Treeview to add or remove employees.
    """
    item = tree.identify_row(event.y)
    col = tree.identify_column(event.x)
    if not item or not col:
        return
    
    col_idx = int(col.replace('#', '')) - 1
    
    # Don't allow editing the first column (Day/Shift headers)
    if col_idx == 0:
        return
    
    # Highlight the selected cell
    tree.selection_set(item)
    tree.focus(item)
    
    cell_value = tree.set(item, col)
    col_name = tree.heading(col)['text']  # Get the column header text (includes date)
    shift_name = tree.set(item, tree["columns"][0])  # Get the shift name
    names = [n.strip() for n in cell_value.split(',') if n.strip()]
    logging.info(f"Editing {area} schedule cell ({item}, {col}) with current names: {names}")
    
    try:
        emp_df = pd.read_csv(emp_file_path, index_col="Employee/Input")
        emp_df = emp_df.transpose()
        available = emp_df[emp_df['Work Area'] == area].index.tolist()
        if not available:
            messagebox.showerror("Error", f"No employees found for {area} in {emp_file_path}")
            return
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load employee data from {emp_file_path}: {e}")
        return
    
    # Position dialog near cursor
    root_window = tree.winfo_toplevel()
    cursor_x = root_window.winfo_pointerx()
    cursor_y = root_window.winfo_pointery()
    
    dialog = tk.Toplevel()
    dialog.title(f"Edit Employees - {area}")
    dialog.geometry("350x450")
    
    # Position near cursor, but ensure it stays on screen
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    dialog_width = 350
    dialog_height = 450
    
    # Adjust position to keep dialog on screen
    x = min(cursor_x + 10, screen_width - dialog_width)
    y = min(cursor_y + 10, screen_height - dialog_height)
    x = max(0, x)
    y = max(0, y)
    
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    # Add date and shift information
    info_frame = tk.Frame(dialog)
    info_frame.pack(pady=5)
    tk.Label(info_frame, text=f"Shift: {shift_name}", font=("Arial", 10, "bold")).pack()
    tk.Label(info_frame, text=f"Date: {col_name}", font=("Arial", 9)).pack()
    
    tk.Label(dialog, text="Current Employees:").pack(pady=5)
    lb = tk.Listbox(dialog, height=10)
    for name in names:
        lb.insert(tk.END, name)
    lb.pack(pady=5, fill="both", expand=True)
    
    def add_employee():
        add_win = tk.Toplevel(dialog)
        add_win.title("Add Employee")
        add_win.geometry("250x200")
        
        # Position add dialog relative to main dialog
        dialog_x = dialog.winfo_x()
        dialog_y = dialog.winfo_y()
        add_win.geometry(f"250x200+{dialog_x + 50}+{dialog_y + 50}")
        
        info_frame = tk.Frame(add_win)
        info_frame.pack(pady=5)
        tk.Label(info_frame, text=f"Shift: {shift_name}", font=("Arial", 10, "bold")).pack()
        tk.Label(info_frame, text=f"Date: {col_name}", font=("Arial", 9)).pack()
        
        tk.Label(add_win, text="Select Employee:").pack(pady=5)
        combo = ttk.Combobox(add_win, values=sorted([n for n in available if n not in names]))
        combo.pack(pady=5)
        
        def confirm_add():
            new_name = combo.get()
            if new_name:
                if new_name not in names:
                    names.append(new_name)
                    lb.insert(tk.END, new_name)
                    update_cell()
                    logging.info(f"Added {new_name} to {area} schedule cell ({item}, {col})")
                else:
                    messagebox.showwarning("Warning", f"{new_name} is already assigned to this shift.")
            add_win.destroy()
        
        button_frame = tk.Frame(add_win)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Add", command=confirm_add).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=add_win.destroy).pack(side=tk.LEFT, padx=5)
    
    def delete_employee():
        sel = lb.curselection()
        if sel:
            del_name = lb.get(sel[0])
            if messagebox.askyesno("Confirm Delete", f"Delete {del_name}?"):
                names.remove(del_name)
                lb.delete(sel[0])
                update_cell()
                logging.info(f"Removed {del_name} from {area} schedule cell ({item}, {col})")
    
    def update_cell():
        new_value = ", ".join(names)
        tree.set(item, col, new_value)
        logging.info(f"Updated {area} schedule cell ({item}, {col}) to '{new_value}'")
    
    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=10)
    tk.Button(button_frame, text="Add Employee", command=add_employee).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Delete Employee", command=delete_employee).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

def save_schedule_changes(bar_frame, kitchen_frame, start_date, root):
    """
    Save schedule changes to CSV files with overwrite prompt and option to save as a different filename.
    """
    save_messages = []
    start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date() if isinstance(start_date, str) else start_date
    date_str = start_date.strftime("%Y-%m-%d")
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    start_weekday = start_date.weekday()
    actual_days = [day_names[(start_weekday + k) % 7] for k in range(7)]
    
    for area, frame in [("Bar", bar_frame), ("Kitchen", kitchen_frame)]:
        treeviews = find_treeviews(frame)
        if not treeviews:
            messagebox.showwarning("Warning", f"No schedule data for {area} to save.")
            continue
        
        default_filename = f"{area}_schedule_{date_str}.csv"
        filename = default_filename
        
        # Check if file exists before prompting
        if os.path.exists(default_filename):
            if not messagebox.askyesno("Overwrite?", f"File {default_filename} already exists. Overwrite?"):
                # Create dialog for new filename
                dialog = tk.Toplevel(root)
                dialog.title(f"Save {area} Schedule As")
                dialog.geometry("300x150")
                
                # Center the dialog relative to the root window
                dialog.transient(root)
                dialog.update_idletasks()
                x = root.winfo_x() + (root.winfo_width() // 2) - (dialog.winfo_width() // 2)
                y = root.winfo_y() + (root.winfo_height() // 2) - (dialog.winfo_height() // 2)
                dialog.geometry(f"300x150+{x}+{y}")
                
                tk.Label(dialog, text="Enter filename:").pack(pady=5)
                filename_entry = tk.Entry(dialog)
                filename_entry.insert(0, default_filename)
                filename_entry.pack(pady=5, fill="x", padx=10)
                
                save_clicked = [False]  # Use list to modify in nested function
                def save_new_filename():
                    nonlocal filename
                    filename = filename_entry.get().strip()
                    if not filename:
                        messagebox.showerror("Error", "Filename cannot be empty.")
                        return
                    if not filename.lower().endswith(".csv"):
                        filename += ".csv"
                    save_clicked[0] = True
                    dialog.destroy()
                
                def cancel_save():
                    dialog.destroy()
                
                tk.Button(dialog, text="Save", command=save_new_filename).pack(pady=5)
                tk.Button(dialog, text="Cancel", command=cancel_save).pack(pady=5)
                
                dialog.transient(root)
                dialog.grab_set()
                root.wait_window(dialog)
                
                if not save_clicked[0]:
                    logging.info(f"User canceled saving {area} schedule.")
                    continue  # Skip saving this area if canceled
        
        try:
            with open(filename, "w") as f:
                for tree in treeviews:
                    parent_frame = tree.master.master  # Get the week_frame (parent of tree_frame)
                    week_name = parent_frame.winfo_name()  # Get the name like 'week1'
                    if not week_name.startswith("week"):
                        raise ValueError(f"Unexpected frame name: {week_name}")
                    week = int(week_name.replace("week", ""))
                    f.write("Day/Shift," + ",".join(f'"{actual_days[k]}, {start_date + datetime.timedelta(days=(week-1)*7 + k):%b %d, %y}"' for k in range(7)) + "\n")
                    for item in tree.get_children():  # Iterate over row IDs (shifts)
                        values = [tree.set(item, "Day/Shift")] + [tree.set(item, actual_days[k]) for k in range(7)]
                        f.write(",".join(f'"{v}"' for v in values) + "\n")
                    f.write("\n")
            save_messages.append(f"Saved {area} schedule to {filename}")
            logging.info(f"Saved {area} schedule to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save {area} schedule: {e}")
            logging.error(f"Failed to save {area} schedule: {str(e)}")
    
    if save_messages:
        messagebox.showinfo("Success", "\n".join(save_messages))
    else:
        messagebox.showwarning("Warning", "No schedules were saved.")

def generate_schedule(emp_path, req_path, limits_path, start_date_entry, num_weeks_var, bar_frame, kitchen_frame, summary_text, viz_frame, root, notebook):
    """
    Generate and display schedules for Bar and Kitchen.
    """
    global all_listboxes
    all_listboxes = []
    start_date = start_date_entry.get_date()
    num_weeks = num_weeks_var.get()
    if num_weeks < 1:
        messagebox.showerror("Error", "Number of weeks must be at least 1")
        return
    
    try:
        # Compute actual_days for consistency
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        start_weekday = start_date.weekday()
        actual_days = [day_names[(start_weekday + k) % 7] for k in range(7)]
        day_offsets = range(7)
        
        result = load_csv(emp_path, req_path, limits_path, start_date, num_weeks)
        if result is None:
            return
        employees, _, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days = result
        
        prob, x, result = solve_schedule(
            employees, day_offsets, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints,
            min_shifts, max_shifts, max_weekend_days, start_date, num_weeks=num_weeks
        )
        
        if prob.status != pulp.LpStatusOptimal:
            messagebox.showerror("Error", "Failed to generate a feasible schedule.")
            logging.error("Solver failed to find an optimal solution: %s", pulp.LpStatus[prob.status])
            return
        
        violations = result.get("violations", [])
        violations_str = "Weekend constraint violations:\n" + ("\n".join(violations) if violations else "None")
        
        save_messages = []
        for area in areas:
            frame = bar_frame if area == "Bar" else kitchen_frame
            for widget in frame.winfo_children():
                widget.destroy()
            
            for week in range(1, num_weeks + 1):
                week_frame = tk.Frame(frame, name=f"week{week}")
                week_frame.pack(pady=5, fill="both", expand=False)
                week_start = start_date + datetime.timedelta(days=(week-1)*7)
                week_end = week_start + datetime.timedelta(days=6)
                tk.Label(week_frame, text=f"{area} Schedule - Week {week} ({week_start:%b %d, %Y} - {week_end:%b %d, %Y})").pack()
                
                tree_frame = ttk.Frame(week_frame)
                tree_frame.pack(fill="both", expand=False)
                tree = ttk.Treeview(tree_frame, show="headings", height=len(shifts))
                vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
                hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
                tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
                tree.grid(row=0, column=0, sticky="nsew")
                vsb.grid(row=0, column=1, sticky="ns")
                hsb.grid(row=1, column=0, sticky="ew")
                tree_frame.rowconfigure(0, weight=1)
                tree_frame.columnconfigure(0, weight=1)
                all_listboxes.append(tree)
                
                columns = ["Day/Shift"] + actual_days
                tree["columns"] = columns
                tree.heading("Day/Shift", text="Day/Shift")
                for k, day in enumerate(actual_days):
                    tree.heading(day, text=f"{day}, {week_start + datetime.timedelta(days=k):%b %d, %y}")
                    tree.column(day, anchor="center", width=100)
                tree.column("Day/Shift", anchor="w", width=100)
                
                for shift in shifts:
                    tree.insert("", "end", shift, values=[shift] + [""] * len(actual_days))
                
                for entry in result[f"{area.lower()}_schedule"]:
                    e, date_str, day, s, a = entry
                    if a == area:
                        week_idx = (datetime.datetime.strptime(date_str, "%Y-%m-%d").date() - start_date).days // 7 + 1
                        if week_idx == week:
                            k = (datetime.datetime.strptime(date_str, "%Y-%m-%d").date() - (start_date + datetime.timedelta(days=(week-1)*7))).days
                            if 0 <= k < 7:
                                current = tree.set(s, actual_days[k])
                                new_value = f"{current}, {e}" if current else e
                                tree.set(s, actual_days[k], new_value)
                
                tree.bind("<Double-1>", lambda e, t=tree, a=area: edit_schedule_cell(t, e, a, emp_path))
            
            filename = f"{area}_schedule_{start_date:%Y-%m-%d}.csv"
            try:
                with open(filename, "w") as f:
                    for week in range(1, num_weeks + 1):
                        tree = find_treeviews(frame.winfo_children()[week-1])[0]
                        f.write("Day/Shift," + ",".join(f'"{actual_days[k]}, {start_date + datetime.timedelta(days=(week-1)*7 + k):%b %d, %y}"' for k in range(7)) + "\n")
                        for shift in shifts:
                            values = [shift] + [tree.set(shift, actual_days[k]) for k in range(7)]
                            f.write(",".join(f'"{v}"' for v in values) + "\n")
                        f.write("\n")
                save_messages.append(f"Saved {area} schedule to {filename}")
                logging.info(f"Saved {area} schedule to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save {area} schedule: {e}")
                logging.error(f"Failed to save {area} schedule: {str(e)}")
        
        summary_df = pd.DataFrame(index=employees, columns=["Employee", "Total Shifts"] + [f"Week {i+1}" for i in range(num_weeks)])
        summary_df["Employee"] = employees
        overall_total_shifts = 0
        for e in employees:
            total_shifts = 0
            for w in range(num_weeks):
                week_shifts = sum(pulp.value(x[e][w][k][s][a]) for k in day_offsets for s in shifts for a in work_areas[e])
                summary_df.loc[e, f"Week {w+1}"] = week_shifts
                total_shifts += week_shifts
            summary_df.loc[e, "Total Shifts"] = total_shifts
            overall_total_shifts += total_shifts
        summary_df = summary_df.sort_values("Employee")
        
        summary_filename = f"Summary_report_{start_date:%Y-%m-%d}.csv"
        try:
            summary_df.to_csv(summary_filename, index=False)
            save_messages.append(f"Saved summary to {summary_filename}")
            logging.info(f"Saved summary to {summary_filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save summary report: {e}")
            logging.error(f"Failed to save summary report: {str(e)}")
        
        relaxed_rules = []
        if constraints["violate_order"]:
            for rule in constraints["violate_order"]:
                flag = f"relax_{rule.lower().replace(' ', '_')}"
                if flag in locals() and locals()[flag]:
                    relaxed_rules.append(rule)
        
        # Calculate minimum employees needed based on violations
        min_emps, min_str = min_employees_to_avoid_weekend_violations(max_weekend_days, areas, violations, work_areas, employees)

        summary_text.delete(1.0, tk.END)
        if relaxed_rules:
            summary_text.insert(tk.END, f"Relaxed rules: {', '.join(relaxed_rules)}\n\n")
        summary_text.insert(tk.END, violations_str + "\n\n")
        summary_text.insert(tk.END, min_str + "\n\n")

        summary_text.insert(tk.END, "Employee Shift Summary:\n")
        summary_text.insert(tk.END, f"{'Employee':<20} {'Total':<8} {'Weeks':<20}\n")
        summary_text.insert(tk.END, "-" * 48 + "\n")
        for index, row in summary_df.iterrows():
            week_str = ", ".join(str(int(row[f'Week {i+1}'])) for i in range(num_weeks))
            summary_text.insert(tk.END, f"{row['Employee']:<20} {int(row['Total Shifts']):<8} {week_str}\n")
        summary_text.insert(tk.END, f"\n{'Overall Total Shifts':<20} {overall_total_shifts}\n\n")

        try:
            for child in viz_frame.winfo_children():
                child.destroy()
            
            fig_width = max(10, len(employees) * 0.5)
            fig, axs = plt.subplots(1, 2, figsize=(fig_width + 5, 6), gridspec_kw={'width_ratios': [3, 1]})
            
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
            week_data = {f'Week {i+1}': [] for i in range(num_weeks)}
            for _, row in summary_df.iterrows():
                for i in range(num_weeks):
                    week_data[f'Week {i+1}'].append(row[f'Week {i+1}'])
            
            bottom = np.zeros(len(employees))
            for i, (week, data) in enumerate(week_data.items()):
                axs[0].bar(employees, data, label=week, bottom=bottom, color=colors[i % len(colors)])
                bottom += np.array(data)
            
            axs[0].set_xlabel('Employees')
            axs[0].set_ylabel('Shifts')
            axs[0].set_title('Shifts per Employee (Stacked by Week)')
            axs[0].legend()
            axs[0].tick_params(axis='x', rotation=45, labelsize=8)
            
            total_per_week = [sum(week_data[week]) for week in week_data]
            axs[1].bar(week_data.keys(), total_per_week, color=colors[:len(week_data)])
            axs[1].set_xlabel('Weeks')
            axs[1].set_ylabel('Total Shifts')
            axs[1].set_title('Total Shifts per Week')
            axs[1].tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            
            viz_canvas = FigureCanvasTkAgg(fig, master=viz_frame)
            viz_canvas.draw()
            viz_canvas.get_tk_widget().pack(fill='both', expand=False)
            
            viz_frame.figure = fig
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create visualization: {e}")
            logging.error(f"Failed to create visualization: {str(e)}")
            tk.Label(viz_frame, text="Visualization failed.").pack()
            plt.close('all')

        adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)
        
        message = "\n".join(save_messages) + "\n\n" + violations_str + "\n\n" + min_str
        messagebox.showinfo("Schedule Generation Complete", message)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate schedule: {str(e)}")
        logging.error(f"Failed to generate schedule: {str(e)}")