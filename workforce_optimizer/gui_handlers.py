import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import datetime
from tkcalendar import Calendar
from solver import solve_schedule, validate_weekend_constraints
from data_loader import load_csv
from constants import DAYS, SHIFTS, AREAS
import pulp
import math
import logging
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from utils import min_employees_to_avoid_weekend_violations, adjust_column_widths

# Global list to store Treeview widgets for dynamic column width adjustment
all_input_trees = []
all_listboxes = []

def display_input_data(emp_path, req_path, limits_path, emp_frame, req_frame, limits_frame, root, notebook, summary_text):
    """
    Load CSV files into Treeview widgets for all input tabs (Employee Data, Personnel Required, Hard Limits).
    """
    global all_input_trees, all_listboxes  # Declare globals at the start
    all_input_trees = []  # Reset the global list

    def create_treeview(frame, csv_file, has_index=True):
        for widget in frame.winfo_children():
            widget.destroy()

        try:
            df = pd.read_csv(csv_file, index_col=0 if has_index else None)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load {csv_file}: {e}")
            return None

        # Configure parent frame for expansion
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        # Create Treeview with scrollbars
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

        # Bind mouse wheel for vertical scrolling anywhere in the widget
        def _on_mousewheel(event):
            if event.delta:
                tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:  # Linux scroll up
                tree.yview_scroll(-1, "units")
            elif event.num == 5:  # Linux scroll down
                tree.yview_scroll(1, "units")
        tree.bind("<MouseWheel>", _on_mousewheel)  # Windows and Mac
        tree.bind("<Button-4>", _on_mousewheel)    # Linux scroll up
        tree.bind("<Button-5>", _on_mousewheel)    # Linux scroll down

        # Set up columns
        columns = list(df.columns)
        if has_index:
            index_name = df.index.name or "Index"
            columns = [index_name] + columns

        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=100)

        # Insert data
        for idx, row in df.iterrows():
            values = ['' if pd.isna(val) else str(val) for val in row]
            if has_index:
                values = [str(idx)] + values
            tree.insert("", "end", iid=str(idx) if has_index else f"row_{idx}", values=values)

        # Bind double-click event
        tree.bind("<Double-1>", lambda event: on_tree_double_click(tree, event, has_index))
        return tree

    create_treeview(emp_frame, emp_path, has_index=True)
    create_treeview(req_frame, req_path, has_index=False)
    create_treeview(limits_frame, limits_path, has_index=False)

    adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)

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
    row_id = item if has_index else tree.index(item)

    # Get current value
    current_value = tree.set(item, col_name)
    if pd.isna(current_value) or current_value == "NaN":
        current_value = ""

    # Open date picker for "Must have off" row (Employee Data only)
    if has_index and "must have off" in row_id.lower():
        open_date_picker_dialog(tree, item, col_name, current_value)
    else:
        # Open entry dialog with validation
        open_entry_dialog(tree, item, col_name, current_value, row_id)
    pass

def open_entry_dialog(tree, item, col_name, current_value, row_id):
    """
    Open a simple entry dialog for editing non-date cells with validation.
    The dialog appears at the cursor position.
    """
    dialog = tk.Toplevel()
    dialog.title("Edit Cell")
    dialog.geometry("300x100")

    # Place dialog at cursor position
    try:
        x = tree.winfo_pointerx()
        y = tree.winfo_pointery()
        dialog.geometry(f"+{x}+{y}")
    except Exception:
        pass  # Fallback to default if unable to get pointer position

    tk.Label(dialog, text=f"Edit {col_name} for {row_id}").pack(pady=5)
    entry = tk.Entry(dialog)
    entry.insert(0, current_value)
    entry.pack(pady=5)

    def save():
        new_value = entry.get()
        # Validate numeric fields
        if any(keyword in row_id.lower() for keyword in ["shifts", "weekend"]):
            if new_value:
                try:
                    float(new_value)
                except ValueError:
                    messagebox.showerror("Error", f"{row_id} must be a number")
                    return
        # Validate shift preferences
        if row_id.lower() == "shift weight" and new_value:
            if new_value.lower() not in ["morning", "evening", ""]:
                messagebox.showerror("Error", f"Shift Weight must be 'Morning', 'Evening', or empty")
                return
        # Validate day preferences
        if row_id.lower() == "day weights" and new_value:
            days = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
            if new_value:
                input_days = [d.strip().lower() for d in new_value.split(",")]
                invalid_days = [d for d in input_days if d and d not in days]
                if invalid_days:
                    messagebox.showerror("Error", f"Invalid days in Day Weights: {invalid_days}")
                    return
        # Validate work area
        if row_id.lower() == "work area" and new_value:
            if new_value not in ["Bar", "Kitchen", ""]:
                messagebox.showerror("Error", f"Work Area must be 'Bar', 'Kitchen', or empty")
                return
        tree.set(item, col_name, new_value)
        dialog.destroy()

    tk.Button(dialog, text="Save", command=save).pack(pady=5)
    dialog.transient(tree.winfo_toplevel())
    dialog.grab_set()

def open_date_picker_dialog(tree, item, col_name, current_value):
    """
    Open a date picker dialog for editing 'Must have off' dates.
    The dialog appears near the cursor and supports vertical scrolling.
    """
    dialog = tk.Toplevel()
    dialog.title("Select Dates")
    dialog.geometry("400x400")

    # Place dialog at cursor position
    try:
        x = tree.winfo_pointerx()
        y = tree.winfo_pointery()
        dialog.geometry(f"+{x}+{y}")
    except Exception:
        pass  # Fallback to default if unable to get pointer position

    # Create a canvas with vertical scrollbar for the dialog content
    canvas = tk.Canvas(dialog, borderwidth=0, background="#f0f0f0")
    vscroll = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vscroll.set)
    vscroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    content_frame = ttk.Frame(canvas)
    canvas.create_window((0, 0), window=content_frame, anchor="nw")
    
    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    
    content_frame.bind("<Configure>", on_frame_configure)
    
    def on_canvas_configure(event):
        canvas.itemconfig("all", width=event.width)
    
    canvas.bind("<Configure>", on_canvas_configure)

    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    content_frame.bind("<Configure>", on_frame_configure)

    ttk.Label(content_frame, text=f"Select dates for {col_name}").pack(pady=5)

    # Parse current dates, handling multiple formats
    def parse_date(date_str):
        try:
            return datetime.datetime.strptime(date_str, "%m/%d/%Y").date()
        except ValueError:
            try:
                return datetime.datetime.strptime(date_str, "%m-%d-%Y").date()
            except ValueError:
                return None

    if current_value and current_value != "NaN":
        selected_dates = [d.strip() for d in current_value.split(",")]
        selected_dates = [parse_date(d) for d in selected_dates if d and parse_date(d)]
    else:
        selected_dates = []

    # Create listbox to display selected dates
    date_listbox = tk.Listbox(content_frame, height=5)
    date_listbox.pack(pady=5, fill=tk.BOTH, expand=True)
    for date in selected_dates:
        date_listbox.insert(tk.END, date.strftime("%m/%d/%Y"))

    # Calendar widget for selecting new dates
    cal = Calendar(content_frame, selectmode="day", date_pattern="mm/dd/yyyy")
    cal.pack(pady=5)

    def add_date():
        selected_date = cal.get_date()
        if selected_date not in date_listbox.get(0, tk.END):
            date_listbox.insert(tk.END, selected_date)

    def remove_date():
        try:
            selected_idx = date_listbox.curselection()[0]
            date_listbox.delete(selected_idx)
        except IndexError:
            pass

    def save():
        dates = date_listbox.get(0, tk.END)
        new_value = ", ".join(dates) if dates else ""
        tree.set(item, col_name, new_value)
        dialog.destroy()

    ttk.Button(content_frame, text="Add Date", command=add_date).pack(pady=5)
    ttk.Button(content_frame, text="Remove Selected Date", command=remove_date).pack(pady=5)
    ttk.Button(content_frame, text="Save", command=save).pack(pady=5)
    dialog.transient(tree.winfo_toplevel())
    dialog.grab_set()

def parse_table_text_to_csv(emp_path, req_path, limits_path, emp_frame, req_frame, limits_frame):
    """
    Save Treeview content to CSV files.
    """
    for tree in all_input_trees:
        csv_file = None
        has_index = False
        index_label = None
        parent = tree.master.master  # tree.master is the inner frame, master.master is the tab frame

        if parent == emp_frame:
            csv_file = emp_path
            has_index = True
            index_label = 'Employee/Input'
        elif parent == req_frame:
            csv_file = req_path
            has_index = False
            index_label = 'Day/Required'
        elif parent == limits_frame:
            csv_file = limits_path
            has_index = False
            index_label = None  # No index label for limits

        if csv_file is None:
            continue

        try:
            columns = tree["columns"]
            items = tree.get_children()
            data = []
            indices = []

            for item in items:
                values = [tree.set(item, col) for col in columns]  # Collect values using tree.set to ensure all columns
                data.append(values)
                if has_index:
                    indices.append(item)  # Use iid as index

            if has_index:
                df = pd.DataFrame(data, index=indices, columns=columns)
                df.to_csv(csv_file, index=True, index_label=index_label)
            else:
                df = pd.DataFrame(data, columns=columns)
                df.to_csv(csv_file, index=False)

            logging.debug(f"Saved {csv_file}")
            messagebox.showinfo("Success", f"Saved {csv_file}")
        except Exception as e:
            logging.error(f"Failed to save {csv_file}: {str(e)}")
            messagebox.showerror("Error", f"Failed to save {csv_file}: {str(e)}")

def generate_schedule(emp_file_var, req_file_var, limits_file_var, start_date_entry, num_weeks_var,
                      bar_frame, kitchen_frame, summary_text, viz_frame, root, notebook):
    """
    Generate the schedule using the solver and display results.
    """
    global all_listboxes, all_input_trees  # Declare globals at the start

    emp_path = emp_file_var.get()
    req_path = req_file_var.get()
    limits_path = limits_file_var.get()
    if not all([emp_path, req_path, limits_path]):
        messagebox.showerror("Error", "Please select all CSV files.")
        return

    try:
        start_date = start_date_entry.get_date()
    except ValueError:
        messagebox.showerror("Error", "Invalid start date format.")
        return

    num_weeks = num_weeks_var.get()
    if num_weeks < 1:
        messagebox.showerror("Error", "Number of weeks must be at least 1.")
        return

    data = load_csv(emp_path, req_path, limits_path, start_date, num_weeks_var)
    if data is None:
        return
    employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days = data

    relaxed_rules = []
    relax_params = [
        ("Day Weights", {"relax_day": False}),
        ("Shift Weight", {"relax_shift": False}),
        ("Max Number of Weekend Days", {"relax_weekend": False}),
        ("Min Shifts per Week", {"relax_min_shifts": False})
    ]
    prob = None
    x = None
    for rule, params in relax_params:
        prob, x = solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days, start_date, num_weeks=num_weeks, **params)
        if prob.status == pulp.LpStatusOptimal:
            break
        relaxed_rules.append(rule)

    if prob.status != pulp.LpStatusOptimal:
        messagebox.showerror("Error", "No feasible solution found even after relaxing all rules.")
        return

    weekly_assignments = {area: {} for area in areas}
    for area in areas:
        weekly_assignments[area] = {}
        for w in range(num_weeks):
            weekly_assignments[area][w] = {shift: {day: [] for day in days} for shift in shifts}

    for e in employees:
        for w in range(num_weeks):
            for i, d in enumerate(days):
                for s in shifts:
                    for a in work_areas[e]:
                        if pulp.value(x[e][w][d][s][a]) == 1:
                            weekly_assignments[a][w][s][d].append(e)

    summary_rows = []
    overall_total_shifts = 0
    employees_sorted = sorted(employees)
    for emp in employees_sorted:
        week_shifts = [
            sum(pulp.value(x[emp][w][d][s][a]) for d in days for s in shifts for a in work_areas[emp])
            for w in range(num_weeks)
        ]
        total_shifts = sum(week_shifts)
        row = [emp, total_shifts] + week_shifts
        summary_rows.append(row)
        overall_total_shifts += total_shifts

    headers = ['Employee', 'Total Shifts'] + [f'Week {i+1}' for i in range(num_weeks)]
    summary_df = pd.DataFrame(summary_rows, columns=headers)

    save_messages = []
    summary_csv_filename = f"Summary_report_{start_date.strftime('%Y-%m-%d')}.csv"
    try:
        summary_df.to_csv(summary_csv_filename, index=False)
        save_messages.append(f"Saved {summary_csv_filename}")
    except Exception as e:
        save_messages.append(f"Failed to save {summary_csv_filename}: {e}")

    for area in areas:
        csv_rows = []
        for w in range(num_weeks):
            week_start = start_date + datetime.timedelta(days=w * 7)
            header_row = ["Day/Shift"]
            for i, day in enumerate(days):
                date = week_start + datetime.timedelta(days=i)
                date_str = date.strftime("%a, %b %d, %y").replace(" 0", " ")
                header_row.append(date_str)
            csv_rows.append(header_row)
            morning_row = ["Morning"]
            for day in days:
                employees = ", ".join(sorted(weekly_assignments[area][w]["Morning"][day]))
                morning_row.append(employees)
            csv_rows.append(morning_row)
            evening_row = ["Evening"]
            for day in days:
                employees = ", ".join(sorted(weekly_assignments[area][w]["Evening"][day]))
                evening_row.append(employees)
            csv_rows.append(evening_row)
        
        max_cols = max(len(row) for row in csv_rows)
        df_data = []
        for row in csv_rows:
            padded_row = row + [""] * (max_cols - len(row))
            df_data.append(padded_row)
        
        df = pd.DataFrame(df_data)
        csv_filename = f"{area}_schedule_{start_date.strftime('%Y-%m-%d')}.csv"
        try:
            df.to_csv(csv_filename, index=False, header=False)
            save_messages.append(f"Saved {csv_filename}")
        except Exception as e:
            save_messages.append(f"Failed to save {csv_filename}: {e}")

    all_listboxes.clear()
    for area, frame in [("Bar", bar_frame), ("Kitchen", kitchen_frame)]:
        for child in frame.winfo_children():
            child.destroy()
        
        # Configure the frame to expand
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        
        # Create container for the weekly Treeviews
        tree_container = ttk.Frame(frame)
        tree_container.grid(row=0, column=0, sticky="nsew")
        tree_container.rowconfigure(0, weight=1)
        tree_container.columnconfigure(0, weight=1)
        
        # Create canvas and scrollbar for vertical scrolling of weeks
        canvas = tk.Canvas(tree_container)
        v_scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        canvas.configure(yscrollcommand=v_scrollbar.set)
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.grid(row=0, column=0, sticky="nsew")
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Bind configure events for scrolling and resizing
        def on_frame_configure(event, canvas=canvas):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", on_frame_configure)
        
        def on_canvas_configure(event, canvas=canvas, canvas_window=canvas_window):
            canvas.itemconfig(canvas_window, width=event.width)
        
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Create one Treeview per week
        weekly_trees = []
        for w in range(num_weeks):
            week_start = start_date + datetime.timedelta(days=w * 7)
            
            # Create frame for the week
            week_frame = ttk.Frame(scrollable_frame)
            week_frame.pack(fill="x", pady=5, expand=True)
            week_frame.columnconfigure(0, weight=1)
            
            # Create Treeview for the week
            tree = ttk.Treeview(week_frame, show="headings", height=3)
            tree_vsb = ttk.Scrollbar(week_frame, orient="vertical", command=tree.yview)
            tree_hsb = ttk.Scrollbar(week_frame, orient="horizontal", command=tree.xview)
            tree.configure(yscrollcommand=tree_vsb.set, xscrollcommand=tree_hsb.set)
            tree.grid(row=0, column=0, sticky="nsew")
            tree_vsb.grid(row=0, column=1, sticky="ns")
            tree_hsb.grid(row=1, column=0, sticky="ew")
            week_frame.rowconfigure(0, weight=1)
            
            # Define columns
            columns = ["Row"] + [day for day in days]
            tree["columns"] = columns
            for col in columns:
                header_text = col if col == "Row" else (week_start + datetime.timedelta(days=days.index(col))).strftime("%a, %b %d")
                tree.heading(col, text=header_text)
                # Set initial width; adjust_column_widths will refine
                tree.column(col, width=100, minwidth=100, stretch=1, anchor="center")
            
            # Insert data into Treeview
            tree.insert("", "end", iid=f"header_{w}", values=["Day/Shift"] + [""] * len(days))
            morning_values = ["Morning"]
            for day in days:
                employees = ", ".join(sorted(weekly_assignments[area][w]["Morning"][day]))
                morning_values.append(employees)
            tree.insert("", "end", iid=f"morning_{w}", values=morning_values)
            evening_values = ["Evening"]
            for day in days:
                employees = ", ".join(sorted(weekly_assignments[area][w]["Evening"][day]))
                evening_values.append(employees)
            tree.insert("", "end", iid=f"evening_{w}", values=evening_values)
            
            weekly_trees.append(tree)
            all_listboxes.append(tree)
        
    violations = validate_weekend_constraints(x, employees, days, shifts, work_areas, max_weekend_days, start_date, num_weeks)
    violations_str = "No weekend violations." if not violations else "Weekend Violations:\n" + "\n".join(violations)

    min_emps = min_employees_to_avoid_weekend_violations(required, max_weekend_days, areas, num_weeks)
    min_str = "Minimum employees needed to avoid weekend violations: " + ", ".join(f"{a}: {min_emps[a]}" for a in areas)

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
        
        fig_width = max(10, len(employees_sorted) * 0.5)
        fig, axs = plt.subplots(1, 2, figsize=(fig_width + 5, 6), gridspec_kw={'width_ratios': [3, 1]})
        
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
        week_data = {f'Week {i+1}': [] for i in range(num_weeks)}
        for index, row in summary_df.iterrows():
            for i in range(num_weeks):
                week_data[f'Week {i+1}'].append(row[f'Week {i+1}'])
        
        bottom = np.zeros(len(employees_sorted))
        for i, (week, data) in enumerate(week_data.items()):
            axs[0].bar(employees_sorted, data, label=week, bottom=bottom, color=colors[i % len(colors)])
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
        viz_canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Store the figure to close it later
        viz_frame.figure = fig  # Attach figure to viz_frame for cleanup
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create visualization: {e}")
        tk.Label(viz_frame, text="Visualization failed.").pack()
        plt.close('all')  # Close any figures in case of error

    adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)

    message = "\n".join(save_messages) + "\n\n" + violations_str
    messagebox.showinfo("Schedule Generation Complete", message)