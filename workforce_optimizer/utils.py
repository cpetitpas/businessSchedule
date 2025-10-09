import math
from datetime import datetime, timedelta
import logging
import tkinter as tk
from tkinter import ttk

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

def adjust_column_widths(root, all_trees, notebook, emp_text, req_text, limits_text):
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

def on_resize(event, root, all_trees, notebook, emp_text, req_text, limits_text):
    if event.widget == root:
        adjust_column_widths(root, all_trees, notebook, emp_text, req_text, limits_text)

def on_mousewheel(event, canvas):
    canvas.yview_scroll(-1 * (event.delta // 120), "units")