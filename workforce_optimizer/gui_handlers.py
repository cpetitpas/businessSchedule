import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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

    create_treeview(emp_frame, emp_path, has_index=True)
    create_treeview(req_frame, req_path, has_index=False)
    create_treeview(limits_frame, limits_path, has_index=False)

    adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)

def save_input_data(emp_path, req_path, limits_path, emp_frame, req_frame, limits_frame):
    """
    Save the edited data from Treeview widgets back to their respective CSV files.
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

    try:
        emp_tree = next((w for w in emp_frame.winfo_children()[0].winfo_children() if isinstance(w, ttk.Treeview)), None)
        if emp_tree:
            emp_df = tree_to_df(emp_tree, has_index=True)
            emp_df.index.name = "Employee/Input"
            emp_df.to_csv(emp_path)
            logging.info(f"Saved Employee Data to {emp_path}")

        req_tree = next((w for w in req_frame.winfo_children()[0].winfo_children() if isinstance(w, ttk.Treeview)), None)
        if req_tree:
            req_df = tree_to_df(req_tree, has_index=True)
            req_df.index.name = "Day/Required"
            req_df.to_csv(req_path)
            logging.info(f"Saved Personnel Required to {req_path}")

        limits_tree = next((w for w in limits_frame.winfo_children()[0].winfo_children() if isinstance(w, ttk.Treeview)), None)
        if limits_tree:
            limits_df = tree_to_df(limits_tree, has_index=False)
            limits_df.to_csv(limits_path, index=False)
            logging.info(f"Saved Hard Limits to {limits_path}")

        messagebox.showinfo("Success", "Input data saved successfully to CSV files.")
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
    row_id = item if has_index else tree.index(item)

    current_value = tree.set(item, col_name)

    entry = tk.Entry(tree)
    entry.insert(0, current_value)
    entry.bind("<Return>", lambda e: update_cell())
    entry.bind("<FocusOut>", lambda e: update_cell())
    
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
    cell_value = tree.set(item, col)
    names = [n.strip() for n in cell_value.split(',') if n.strip()]
    
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
    
    dialog = tk.Toplevel()
    dialog.title(f"Edit Employees - {area}")
    dialog.geometry("300x400")
    
    tk.Label(dialog, text="Current Employees:").pack(pady=5)
    lb = tk.Listbox(dialog, height=10)
    for name in names:
        lb.insert(tk.END, name)
    lb.pack(pady=5, fill="both", expand=True)
    
    def add_employee():
        add_win = tk.Toplevel(dialog)
        add_win.title("Add Employee")
        add_win.geometry("200x150")
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
        tk.Button(add_win, text="Add", command=confirm_add).pack(pady=5)
    
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
    
    tk.Button(dialog, text="Add Employee", command=add_employee).pack(pady=5)
    tk.Button(dialog, text="Delete Employee", command=delete_employee).pack(pady=5)
    tk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=5)

def save_schedule_changes(bar_frame, kitchen_frame, start_date, root):
    """
    Save edited schedule data from Treeview widgets to CSV files with correct format (no blank lines between weeks).
    """
    areas = {"Bar": bar_frame, "Kitchen": kitchen_frame}
    save_messages = []
    for area, frame in areas.items():
        # Find all Treeviews recursively in the frame
        week_trees = find_treeviews(frame)
        if not week_trees:
            save_messages.append(f"No schedule data for {area}.")
            continue
        
        output_file = f"{area}_schedule_{start_date.strftime('%Y-%m-%d')}.csv"
        try:
            if messagebox.askyesno("Confirm Overwrite", f"Overwrite {output_file}? Select No to save as new file."):
                pass
            else:
                output_file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile=output_file)
                if not output_file:
                    save_messages.append(f"Save cancelled for {area}.")
                    continue
            with open(output_file, 'w', newline='') as f:
                for w, tree in enumerate(week_trees):
                    columns = tree["columns"]
                    f.write(','.join(f'"{col}"' if ',' in col else col for col in columns) + '\n')
                    for item in tree.get_children():
                        values = tree.item(item)['values']
                        f.write(','.join(f'"{v}"' if ',' in str(v) else str(v) for v in values) + '\n')
            save_messages.append(f"Saved {area} schedule to {output_file}")
        except Exception as e:
            save_messages.append(f"Failed to save {area} schedule: {str(e)}")
            logging.error(f"Failed to save {area} schedule: {str(e)}")
    
    messagebox.showinfo("Save Complete", "\n".join(save_messages))

def generate_schedule(emp_file_path, req_file_path, limits_file_path, start_date_entry, num_weeks_var, bar_frame, kitchen_frame, summary_text, viz_frame, root, notebook):
    """
    Generate and display the schedule based on input files and parameters.
    """
    global all_listboxes
    all_listboxes = []
    
    try:
        start_date = start_date_entry.get_date()
        num_weeks = num_weeks_var.get()
        if num_weeks < 1:
            messagebox.showerror("Error", "Number of weeks must be at least 1")
            return

        result = load_csv(emp_file_path, req_file_path, limits_file_path, start_date, num_weeks)
        if result is None:
            return
        employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days = result

        relaxed_rules = []
        prob = None
        for relax_day in [True, False]:
            for relax_shift in [True, False]:
                for relax_weekend in [True, False]:
                    for relax_min_shifts in [True, False]:
                        prob, x = solve_schedule(
                            employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas,
                            constraints, min_shifts, max_shifts, max_weekend_days, start_date,
                            relax_day, relax_shift, relax_weekend, relax_min_shifts, num_weeks
                        )
                        if prob.status == pulp.LpStatusOptimal:
                            relaxed_rules = []
                            if relax_day:
                                relaxed_rules.append("Day Weights")
                            if relax_shift:
                                relaxed_rules.append("Shift Weight")
                            if relax_weekend:
                                relaxed_rules.append("Max Number of Weekend Days")
                            if relax_min_shifts:
                                relaxed_rules.append("Min Shifts per Week")
                            break
                    else:
                        continue
                    break
                else:
                    continue
                break
            else:
                continue
            break

        if prob.status != pulp.LpStatusOptimal:
            messagebox.showerror("Error", "Failed to find an optimal schedule")
            return

        summary_data = []
        overall_total_shifts = 0
        weekly_assignments = {area: [{s: {d: [] for d in days} for s in shifts} for _ in range(num_weeks)] for area in areas}
        for e in employees:
            total_shifts = 0
            week_shifts = [0] * num_weeks
            for w in range(num_weeks):
                for d in days:
                    for s in shifts:
                        for a in work_areas[e]:
                            if pulp.value(x[e][w][d][s][a]) == 1:
                                weekly_assignments[a][w][s][d].append(e)
                                total_shifts += 1
                                week_shifts[w] += 1
            summary_data.append({
                "Employee": e,
                "Total Shifts": total_shifts,
                **{f"Week {i+1}": week_shifts[i] for i in range(num_weeks)}
            })
            overall_total_shifts += total_shifts
        summary_df = pd.DataFrame(summary_data)
        employees_sorted = sorted(employees)
        summary_df = summary_df.set_index("Employee").loc[employees_sorted].reset_index()

        save_messages = []
        for area in areas:
            area_frame = bar_frame if area == "Bar" else kitchen_frame
            for widget in area_frame.winfo_children():
                widget.destroy()

            weekly_trees = []
            week_start = start_date
            for w in range(num_weeks):
                week_dates = [(week_start + datetime.timedelta(days=d)).strftime("%a, %b %d, %y") for d in range(7)]
                columns = ["Day/Shift"] + week_dates

                week_frame = tk.Frame(area_frame)
                week_frame.pack(pady=5, fill="both", expand=True)
                tk.Label(week_frame, text=f"{area} Schedule - Week {w + 1} ({week_start.strftime('%b %d, %Y')} - {(week_start + datetime.timedelta(days=6)).strftime('%b %d, %Y')})").pack()

                tree_frame = tk.Frame(week_frame)
                tree_frame.pack(fill="both", expand=True)

                tree = ttk.Treeview(tree_frame, show="headings", height=2)
                tree_vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
                tree_hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
                tree.configure(yscrollcommand=tree_vsb.set, xscrollcommand=tree_hsb.set)
                tree.pack(side="left", fill="both", expand=True)
                tree_vsb.pack(side="right", fill="y")
                tree_hsb.pack(side="bottom", fill="x")

                tree["columns"] = columns
                for col in columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=100, minwidth=100, stretch=1, anchor="center")

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

                tree.bind("<Double-1>", lambda event, a=area, t=tree: edit_schedule_cell(t, event, a, emp_file_path))

                weekly_trees.append(tree)
                all_listboxes.append(tree)
                week_start += datetime.timedelta(days=7)

            try:
                output_file = f"{area}_schedule_{start_date.strftime('%Y-%m-%d')}.csv"
                if messagebox.askyesno("Confirm Overwrite", f"Overwrite {output_file}? Select No to save as new file."):
                    pass
                else:
                    output_file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile=output_file)
                    if not output_file:
                        save_messages.append(f"Save cancelled for {area}.")
                        continue
                with open(output_file, 'w', newline='') as f:
                    for w, tree in enumerate(weekly_trees):
                        columns = tree["columns"]
                        f.write(','.join(f'"{col}"' if ',' in col else col for col in columns) + '\n')
                        for item in tree.get_children():
                            values = tree.item(item)['values']
                            f.write(','.join(f'"{v}"' if ',' in str(v) else str(v) for v in values) + '\n')
                save_messages.append(f"Saved {area} schedule to {output_file}")
            except Exception as e:
                save_messages.append(f"Failed to save {area} schedule: {str(e)}")
                logging.error(f"Failed to save {area} schedule: {str(e)}")

        try:
            output_file = f"Summary_report_{start_date.strftime('%Y-%m-%d')}.csv"
            if messagebox.askyesno("Confirm Overwrite", f"Overwrite {output_file}? Select No to save as new file."):
                pass
            else:
                output_file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile=output_file)
                if not output_file:
                    save_messages.append("Save cancelled for summary report.")
            summary_df.to_csv(output_file, index=False)
            save_messages.append(f"Saved summary report to {output_file}")
        except Exception as e:
            save_messages.append(f"Failed to save summary report: {str(e)}")
            logging.error(f"Failed to save summary report: {str(e)}")

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
            for _, row in summary_df.iterrows():
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
            
            viz_frame.figure = fig
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create visualization: {e}")
            logging.error(f"Failed to create visualization: {str(e)}")
            tk.Label(viz_frame, text="Visualization failed.").pack()
            plt.close('all')

        adjust_column_widths(root, all_listboxes, all_input_trees, notebook, summary_text)
        
        message = "\n".join(save_messages) + "\n\n" + violations_str
        messagebox.showinfo("Schedule Generation Complete", message)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate schedule: {str(e)}")
        logging.error(f"Failed to generate schedule: {str(e)}")