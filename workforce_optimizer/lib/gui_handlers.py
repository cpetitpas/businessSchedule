# gui_handlers.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import datetime
from tkcalendar import Calendar
from .solver import solve_schedule
from .data_loader import load_csv
from .utils import user_output_dir, user_data_dir
import pulp
import math
import logging
import matplotlib.pyplot as plt
import numpy as np
import os
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from .utils import min_employees_to_avoid_weekend_violations, adjust_column_widths, user_output_dir
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

# Global list to store Treeview widgets for dynamic column width adjustment
all_input_trees = []
all_listboxes = []

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

def save_input_data(emp_var, req_var, limits_var, emp_frame, req_frame, limits_frame, root):
    """
    Save the edited data from Treeview widgets back to their respective CSV files with overwrite prompt and option to save as a different filename.
    Update the variables if saved to a new filename.
    """
    data_dir = user_data_dir()

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
        """Get filename with overwrite/skip/save-as options."""
        if os.path.exists(default_path):
            response = messagebox.askyesnocancel(
                f"File Exists: {file_type}",
                f"File already exists:\n{os.path.basename(default_path)}\n\n"
                f"Yes: Overwrite\n"
                f"No: Save As\n"
                f"Cancel: Skip this file"
            )
           
            if response is None: # Cancel
                return False
            elif response: # Yes - overwrite
                return default_path
            else: # No - save as
                new_filename = filedialog.asksaveasfilename(
                    parent=root,
                    title=f"Save {file_type} As",
                    initialdir=data_dir,
                    initialfile=os.path.basename(default_path),
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )
                return new_filename if new_filename else False
        return default_path
   
    save_messages = []
    try:
        # Employee Data
        emp_tree = next((w for w in emp_frame.winfo_children()[0].winfo_children() if isinstance(w, ttk.Treeview)), None)
        if emp_tree:
            orig_emp_path = emp_var.get()
            if orig_emp_path:
                emp_basename = os.path.basename(orig_emp_path)
                emp_path = os.path.join(data_dir, emp_basename)
                filename = get_save_filename(emp_path, "Employee Data")
                if filename and filename is not False:
                    emp_df = tree_to_df(emp_tree, has_index=False)
                    emp_df.to_csv(filename, index=False)
                    save_messages.append(f"Saved Employee Data to {filename}")
                    logging.info(f"Saved Employee Data to {filename}")
                    if filename != orig_emp_path:
                        emp_var.set(filename)
       
        # Personnel Required
        req_tree = next((w for w in req_frame.winfo_children()[0].winfo_children() if isinstance(w, ttk.Treeview)), None)
        if req_tree:
            orig_req_path = req_var.get()
            if orig_req_path:
                req_basename = os.path.basename(orig_req_path)
                req_path = os.path.join(data_dir, req_basename)
                filename = get_save_filename(req_path, "Personnel Required")
                if filename and filename is not False:
                    req_df = tree_to_df(req_tree, has_index=False)
                    req_df.to_csv(filename, index=False)
                    save_messages.append(f"Saved Personnel Required to {filename}")
                    logging.info(f"Saved Personnel Required to {filename}")
                    if filename != orig_req_path:
                        req_var.set(filename)
       
        # Hard Limits
        limits_tree = next((w for w in limits_frame.winfo_children()[0].winfo_children() if isinstance(w, ttk.Treeview)), None)
        if limits_tree:
            orig_limits_path = limits_var.get()
            if orig_limits_path:
                limits_basename = os.path.basename(orig_limits_path)
                limits_path = os.path.join(data_dir, limits_basename)
                filename = get_save_filename(limits_path, "Hard Limits")
                if filename and filename is not False:
                    limits_df = tree_to_df(limits_tree, has_index=False)
                    limits_df.to_csv(filename, index=False)
                    save_messages.append(f"Saved Hard Limits to {filename}")
                    logging.info(f"Saved Hard Limits to {filename}")
                    if filename != orig_limits_path:
                        limits_var.set(filename)
       
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
    if col_idx == 0 and has_index == False:
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
    col_name = tree.heading(col)['text'] # Get the column header text (includes date)
    shift_name = tree.set(item, tree["columns"][0]) # Get the shift name
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
    # Create dialog with standard look
    dialog = tk.Toplevel()
    dialog.title(f"Edit Employees - {area}")
    dialog.geometry("350x450")

    # Position dialog near cursor
    root_window = tree.winfo_toplevel()
    cursor_x = root_window.winfo_pointerx()
    cursor_y = root_window.winfo_pointery()
    
    # Adjust position to keep dialog on screen
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    dialog_width = 350
    dialog_height = 450
    x = min(cursor_x + 10, screen_width - dialog_width)
    y = min(cursor_y + 10, screen_height - dialog_height)
    x = max(0, x)
    y = max(0, y)
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    # Set icon to match standard dialogs
    try:
        from main import resource_path  # Import from main.py
        dialog.iconbitmap(resource_path(r'icons\teamwork.ico'))
    except Exception as e:
        # Fallback: use default
        pass
    
    # Make dialog transient and modal
    dialog.transient(root_window)
    dialog.grab_set()
    
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
        
        # Set icon to match standard dialogs
        try:
            from main import resource_path  # Import from main.py
            add_win.iconbitmap(resource_path(r'icons\teamwork.ico'))
        except Exception as e:
            # Fallback: use default
            pass
        
        # Make dialog transient and modal
        add_win.transient(dialog)
        add_win.grab_set()
        
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

def save_schedule_changes(start_date, root, schedule_container, areas):
    """
    Save schedule changes to CSV files with overwrite prompt and option to save as a different filename.
    """
    def get_save_filename(default_path, file_type):
        """Get filename with overwrite/skip/save-as options."""
        if os.path.exists(default_path):
            response = messagebox.askyesnocancel(
                f"File Exists: {file_type}",
                f"File already exists:\n{os.path.basename(default_path)}\n\n"
                f"Yes: Overwrite\n"
                f"No: Save As\n"
                f"Cancel: Skip this file"
            )
            
            if response is None:  # Cancel
                return False
            elif response:  # Yes - overwrite
                return default_path
            else:  # No - save as
                new_filename = filedialog.asksaveasfilename(
                    parent=root,
                    title=f"Save {file_type} As",
                    initialdir=user_output_dir(),
                    initialfile=os.path.basename(default_path),
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )
                return new_filename if new_filename else False
                
                def confirm_save_as():
                    filename = filename_entry.get().strip()
                    if not filename:
                        messagebox.showerror("Error", "Filename cannot be empty.")
                        return
                    if not filename.lower().endswith(".csv"):
                        filename += ".csv"
                    # If no directory specified, use user_output_dir
                    if not os.path.dirname(filename):
                        filename = os.path.join(user_output_dir(), filename)
                    choice[0] = filename
                    save_dialog.destroy()
                
                def cancel_save_as():
                    choice[0] = False
                    save_dialog.destroy()
                
                button_frame = tk.Frame(save_dialog)
                button_frame.pack(pady=10)
                tk.Button(button_frame, text="Save", command=confirm_save_as).pack(side=tk.LEFT, padx=5)
                tk.Button(button_frame, text="Cancel", command=cancel_save_as).pack(side=tk.LEFT, padx=5)
                
                save_dialog.grab_set()
                root.wait_window(save_dialog)
                return choice[0]
        return default_path

    save_messages = []
    start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date() if isinstance(start_date, str) else start_date
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    start_weekday = start_date.weekday()
    actual_days = [day_names[(start_weekday + k) % 7] for k in range(7)]
    
    try:
        # Find all area frames and their treeviews
        for area in areas:
            area_trees = []
            # Look for area frames in schedule_container
            found_area_label = False
            for widget in schedule_container.winfo_children():
                # Check if this is the label for our area
                if isinstance(widget, tk.Label) and widget.cget("text") == f"{area} Schedule":
                    found_area_label = True
                    continue
                # If we found the label, the next Frame contains this area's treeviews
                if found_area_label and isinstance(widget, tk.Frame):
                    # Find treeviews in this frame
                    for child in widget.winfo_children():
                        if isinstance(child, tk.Frame):
                            for grandchild in child.winfo_children():
                                if isinstance(grandchild, ttk.Frame):
                                    for ggchild in grandchild.winfo_children():
                                        if isinstance(ggchild, ttk.Treeview):
                                            area_trees.append(ggchild)
                    # Stop after processing this area's frame
                    found_area_label = False
                    break
            
            if area_trees:
                # Determine number of weeks from number of trees
                num_weeks = len(area_trees)
                
                # Default filename - ensure it's in user_output_dir
                default_filename = os.path.join(user_output_dir(), f"{area}_schedule_{start_date:%Y-%m-%d}.csv")
                
                # Get filename with overwrite check
                filename = get_save_filename(default_filename, f"{area} Schedule")
                
                if filename and filename is not False:  # filename is False when skipped
                    try:
                        # Save with header for each week
                        with open(filename, "w") as f:
                            for week in range(1, num_weeks + 1):
                                tree = area_trees[week-1]
                                week_start = start_date + datetime.timedelta(days=(week-1)*7)
                                week_end = week_start + datetime.timedelta(days=6)
                                # Write header with area name and date range
                                f.write(f'"{area} Schedule ({week_start:%b %d, %Y} - {week_end:%b %d, %Y})"\n')
                                # Write column headers
                                f.write("Day/Shift," + ",".join(f'"{actual_days[k]}, {week_start + datetime.timedelta(days=k):%b %d, %y}"' for k in range(7)) + "\n")
                                # Write data rows
                                for item in tree.get_children():
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
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save schedule changes: {str(e)}")
        logging.error(f"Failed to save schedule changes: {str(e)}")

def create_schedule_treeview(parent, week, start_date, shifts, actual_days):
    """
    Create a Treeview for a specific week in a schedule frame.
    """
    week_frame = tk.Frame(parent, name=f"week{week}")
    week_frame.pack(pady=5, fill="both", expand=False)
    week_start = start_date + datetime.timedelta(days=(week-1)*7)
    week_end = week_start + datetime.timedelta(days=6)
    tk.Label(week_frame, text=f"Week {week} ({week_start:%b %d, %Y} - {week_end:%b %d, %Y})").pack()

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

    columns = ["Day/Shift"] + actual_days
    tree["columns"] = columns
    tree.heading("Day/Shift", text="Day/Shift")
    for k, day in enumerate(actual_days):
        date = week_start + datetime.timedelta(days=k)
        tree.heading(day, text=f"{day}, {date:%b %d, %y}")
        tree.column(day, anchor="center", width=100)
    tree.column("Day/Shift", anchor="w", width=100)

    for shift in shifts:
        tree.insert("", "end", iid=shift, values=[shift] + [""] * len(actual_days))

    return tree

def save_area_schedule(treeviews, filename, start_date, num_weeks, actual_days, area):
    with open(filename, "w") as f:
        for week in range(1, num_weeks + 1):
            tree = treeviews[week-1]
            week_start = start_date + datetime.timedelta(days=(week-1)*7)
            week_end = week_start + datetime.timedelta(days=6)
            f.write(f'"{area} Schedule ({week_start:%b %d, %Y} - {week_end:%b %d, %Y})"\n')
            f.write("Day/Shift," + ",".join(f'"{actual_days[k]}, {week_start + datetime.timedelta(days=k):%b %d, %y}"' for k in range(7)) + "\n")
            for item in tree.get_children():
                values = [tree.set(item, "Day/Shift")] + [tree.set(item, actual_days[k]) for k in range(7)]
                f.write(",".join(f'"{v}"' for v in values) + "\n")
            f.write("\n")

def generate_schedule(emp_var, req_var, limits_var, start_date_entry, num_weeks_var,
                      summary_text, viz_frame, root, notebook, schedule_container,
                      emp_frame, req_frame, limits_frame):
    """
    Generate and display schedules for dynamic work areas, with visualizations.
    """
    global all_listboxes, schedule_trees
    
    # Prompt user to save input data before generating schedule
    response = messagebox.askyesnocancel(
        "Save Input Data",
        "Would you like to save your input data before generating the schedule?\n\n"
        "Yes: Save input data and proceed\n"
        "No: Proceed without saving\n"
        "Cancel: Cancel schedule generation"
    )
    
    if response is None:  # Cancel
        return
    elif response:  # Yes - save input data
        try:
            save_input_data(emp_var, req_var, limits_var, emp_frame, req_frame, limits_frame, root)
        except Exception as e:
            messagebox.showwarning("Warning", f"Failed to save input data: {e}\n\nProceeding with schedule generation.")
            logging.error(f"Failed to save input data before schedule generation: {e}")
    
    # Continue with schedule generation
    emp_path = emp_var.get()
    req_path = req_var.get()
    limits_path = limits_var.get()
    all_listboxes = []
    schedule_trees = {} # Global for save_schedule_changes
    try:
        start_date = start_date_entry.get_date()
    except tk.TclError:
        messagebox.showerror("Error", "Invalid date entry widget. Please restart the application.")
        return
    num_weeks = num_weeks_var.get()
    if num_weeks < 1:
        messagebox.showerror("Error", "Number of weeks must be at least 1")
        return
    try:
        # === CLEAR UI ===
        for widget in schedule_container.winfo_children():
            widget.destroy()
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        start_weekday = start_date.weekday()
        actual_days = [day_names[(start_weekday + k) % 7] for k in range(7)]
        result = load_csv(emp_path, req_path, limits_path, start_date, num_weeks)
        if result is None:
            return
        employees, _, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days = result
        # === SOLVE ===
        prob, x, result_dict = solve_schedule(
            employees, range(7), shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints,
            min_shifts, max_shifts, max_weekend_days, start_date, num_weeks=num_weeks
        )
        # -------------------------------------------------
        # 1. CAPACITY REPORT – ALWAYS available in result_dict
        # -------------------------------------------------
        capacity_report = result_dict.get("capacity_report", "")
        # === FAILURE PATH (prob is None) ===
        if prob is None:
            # Show message box (unchanged)
            error_msg = result_dict.get("error", "Unknown solver error.")
            messagebox.showerror("No Feasible Schedule", error_msg)
            logging.error(error_msg)
            # === BUILD FAILURE REPORT ONCE — DO NOT INCLUDE capacity_report AGAIN ===
            min_emps, min_str, _ = min_employees_to_avoid_weekend_violations(
                max_weekend_days, areas, [], work_areas, employees
            )
            # ---- UI ----
            summary_text.delete(1.0, tk.END)
            report_lines = []
            # ONLY the capacity_report (once)
            if capacity_report:
                report_lines.append(capacity_report)
                report_lines.append("")
            # Add failure banner and **do not re-add** any part of error_msg that contains the report
            report_lines.extend([
                "SOLVER FAILED TO FIND A FEASIBLE SCHEDULE",
                "",
                "The schedule cannot be created due to insufficient staffing capacity.",
                "",
                "Possible fixes (from solver):",
            ])
            # Extract only the "Possible fixes" part from error_msg (skip the capacity report part)
            if "Possible fixes:" in error_msg:
                fixes_part = error_msg.split("Possible fixes:", 1)[1]
                report_lines.extend(
                    line.strip() for line in fixes_part.splitlines() if line.strip()
                )
            report_lines.extend(["", min_str.strip()])
            # Insert into UI
            summary_text.insert(tk.END, "\n".join(report_lines) + "\n")
            # ---- FILE ----
            summary_file = os.path.join(user_output_dir(), f"Summary_report_{start_date:%Y-%m-%d}.csv")
            try:
                with open(summary_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(report_lines))
                logging.info(f"Saved failure summary to {summary_file}")
            except Exception as e:
                logging.error(f"Failed to save failure summary: {e}")
            adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)
            return
        # === NON-OPTIMAL STATUS ===
        if prob.status != pulp.LpStatusOptimal:
            status_msg = pulp.LpStatus[prob.status]
            messagebox.showerror("Solver Error", f"Failed to find optimal solution: {status_msg}")
            logging.error("Solver status: %s", status_msg)
            return
        # === SUCCESS PATH (unchanged below) ===
        violations = result_dict.get("violations", [])
        violations_str = "Weekend constraint violations:\n" + ("\n".join(violations) if violations else "None")
        save_messages = []
        schedule_trees = {area: [] for area in areas}
        for area in areas:
            area_label = tk.Label(schedule_container, text=f"{area} Schedule", font=("Arial", 12, "bold"))
            area_label.pack(pady=(15 if area == areas[0] else 20, 5), anchor="center")
            area_frame = tk.Frame(schedule_container)
            area_frame.pack(pady=5, fill="both", expand=True)
            for week in range(1, num_weeks + 1):
                tree = create_schedule_treeview(area_frame, week, start_date, shifts, actual_days)
                schedule_trees[area].append(tree)
                all_listboxes.append(tree)
                area_schedule = result_dict.get(f"{area.lower()}_schedule", [])
                for e, date_str, day, s, a in area_schedule:
                    if a != area: continue
                    date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    week_idx = (date_obj - start_date).days // 7 + 1
                    if week_idx != week: continue
                    k = (date_obj - (start_date + datetime.timedelta(days=(week-1)*7))).days
                    if 0 <= k < 7:
                        current = tree.set(s, actual_days[k])
                        tree.set(s, actual_days[k], f"{current}, {e}" if current else e)
                tree.bind("<Double-1>", lambda e, t=tree, a=area, emp=emp_path: edit_schedule_cell(t, e, a, emp))
            # Auto-save
            filename = os.path.join(user_output_dir(), f"{area}_schedule_{start_date:%Y-%m-%d}.csv")
            try:
                save_area_schedule(schedule_trees[area], filename, start_date, num_weeks, actual_days, area)
                save_messages.append(f"Saved {area} schedule to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save {area} schedule: {e}")
        # === Summary Report (UI) ===
        min_emps, min_str, violations = min_employees_to_avoid_weekend_violations(
            max_weekend_days, areas, violations, work_areas, employees,
            start_date=start_date, num_weeks=num_weeks, result_dict=result_dict
        )
        violations_str = "Weekend constraint violations:\n" + ("\n".join(violations) if violations else "None")
        summary_text.delete(1.0, tk.END)
        # 1. Capacity report first (only once)
        if capacity_report:
            summary_text.insert(tk.END, capacity_report + "\n\n")
        # 2. Weekend info
        summary_text.insert(tk.END, violations_str + "\n\n")
        summary_text.insert(tk.END, min_str + "\n\n")
        # 3. Employee shift summary
        summary_text.insert(tk.END, "Employee Shift Summary:\n")
        summary_text.insert(tk.END, f"{'Employee':<20} {'Total':<8} {'Weeks':<20}\n")
        summary_text.insert(tk.END, "-" * 48 + "\n")
        # Build employee shift counts
        summary_df = pd.DataFrame(index=employees, columns=["Employee", "Total Shifts"] + [f"Week {i+1}" for i in range(num_weeks)])
        summary_df["Employee"] = employees
        shift_counts = {e: {w: 0 for w in range(num_weeks)} for e in employees}
        for area in areas:
            for e, date_str, _, _, a in result_dict.get(f"{area.lower()}_schedule", []):
                if a != area: continue
                date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                week_idx = (date_obj - start_date).days // 7
                if 0 <= week_idx < num_weeks:
                    shift_counts[e][week_idx] += 1
        total_shifts = 0
        for e in employees:
            weekly = [shift_counts[e][w] for w in range(num_weeks)]
            summary_df.loc[e, [f"Week {i+1}" for i in range(num_weeks)]] = weekly
            total = sum(weekly)
            summary_df.loc[e, "Total Shifts"] = total
            total_shifts += total
            weeks = ", ".join(str(int(summary_df.loc[e, f"Week {i+1}"])) for i in range(num_weeks))
            summary_text.insert(tk.END, f"{e:<20} {int(total):<8} {weeks}\n")
        summary_text.insert(tk.END, f"\n{'Overall Total Shifts':<20} {total_shifts}\n")
        # === Save Summary Report to file ===
        summary_file = os.path.join(user_output_dir(), f"Summary_report_{start_date:%Y-%m-%d}.csv")
        try:
            file_lines = []
            if capacity_report:
                file_lines.append(capacity_report)
                file_lines.append("")
            file_lines.append(violations_str)
            file_lines.append("")
            file_lines.append(min_str.strip())
            file_lines.append("")
            file_lines.append("Employee Shift Summary:")
            file_lines.append(f"{'Employee':<20} {'Total':<8} {'Weeks':<20}")
            file_lines.append("-" * 48)
            for e in employees:
                weeks = ", ".join(str(int(summary_df.loc[e, f"Week {i+1}"])) for i in range(num_weeks))
                file_lines.append(f"{e:<20} {int(summary_df.loc[e, 'Total Shifts']):<8} {weeks}")
            file_lines.append(f"\n{'Overall Total Shifts':<20} {total_shifts}")
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write("\n".join(file_lines))
            save_messages.append(f"Saved summary to {summary_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save summary: {e}")
        # === Visualizations ===
        try:
            for child in viz_frame.winfo_children():
                child.destroy()
            active = [e for e in employees if summary_df.loc[e, "Total Shifts"] > 0]
            fig, axs = plt.subplots(2, 2, figsize=(max(10, len(active)*0.5)+5, 10),
                                  gridspec_kw={'width_ratios': [3, 1], 'height_ratios': [1, 1]})
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
            # Plot 1
            week_data = {f'Week {i+1}': [int(summary_df.loc[e, f'Week {i+1}']) for e in active] for i in range(num_weeks)}
            bottom = np.zeros(len(active))
            for i, (week, data) in enumerate(week_data.items()):
                axs[0,0].bar(active, data, label=week, bottom=bottom, color=colors[i % len(colors)])
                bottom += data
            axs[0,0].set_title('Shifts per Employee (by Week)')
            axs[0,0].legend()
            axs[0,0].tick_params(axis='x', rotation=45, labelsize=8)
            # Plot 2
            axs[0,1].bar(week_data.keys(), [sum(d) for d in week_data.values()], color=colors[:num_weeks])
            axs[0,1].set_title('Total Shifts per Week')
            # Plot 3
            area_counts = {a: [0]*len(active) for a in areas}
            for i, e in enumerate(active):
                for area in areas:
                    area_counts[area][i] = sum(1 for entry in result_dict.get(f"{area.lower()}_schedule", []) if entry[0] == e)
            bottom = np.zeros(len(active))
            for i, (area, data) in enumerate(area_counts.items()):
                axs[1,0].bar(active, data, label=area, bottom=bottom, color=colors[i % len(colors)])
                bottom += data
            axs[1,0].set_title('Shifts per Employee (by Area)')
            axs[1,0].legend()
            axs[1,0].tick_params(axis='x', rotation=45, labelsize=8)
            # Plot 4
            axs[1,1].bar(areas, [sum(d) for d in area_counts.values()], color=colors[:len(areas)])
            axs[1,1].set_title('Total Shifts per Area')
            plt.tight_layout()
            canvas = FigureCanvasTkAgg(fig, viz_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)
            viz_frame.figure = fig
        except Exception as e:
            messagebox.showerror("Error", f"Visualization failed: {e}")
            tk.Label(viz_frame, text="Visualization failed.").pack()
        adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)
        messagebox.showinfo("Success", "\n".join(save_messages) + "\n\n" + violations_str + "\n\n" + min_str)
    except Exception as e:
        messagebox.showerror("Error", f"Unexpected error: {str(e)}")
        logging.error(f"generate_schedule error: {e}", exc_info=True)