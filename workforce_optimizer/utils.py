import math
from datetime import datetime, timedelta
import logging
import tkinter as tk
from tkinter import ttk

def calculate_min_employees(required, work_areas, employees, must_off, max_shifts, max_weekend_days, start_date, num_weeks):
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
    
    # Minimum employees needed (using area-specific averages)
    needed = {"Bar": 0, "Kitchen": 0}
    for area in areas:
        area_employees = [e for e in employees if area in work_areas[e]]
        num_area_employees = len(area_employees)
        if num_area_employees == 0:
            needed[area] = float('inf')  # Impossible if no employees
            continue
        
        avg_max_shifts = sum(max_shifts[e] for e in area_employees) / num_area_employees
        avg_max_weekend = sum(max_weekend_days[e] for e in area_employees) / num_area_employees
        
        shifts_needed = total_shifts[area] + unavailable_shifts[area]
        employees_by_total = math.ceil(shifts_needed / (avg_max_shifts * num_weeks)) if avg_max_shifts > 0 else float('inf')
        employees_by_weekend = math.ceil(weekend_shifts[area] / (avg_max_weekend * num_weeks)) if avg_max_weekend > 0 else float('inf')
        needed[area] = max(employees_by_total, employees_by_weekend)
        if area == "Bar" and num_weeks == 2:
            needed[area] = max(needed[area], 6)
    logging.info("Minimum employees needed: Bar=%d, Kitchen=%d", needed["Bar"], needed["Kitchen"])
    
    logging.debug("Exiting calculate_min_employees")
    return current, needed

def adjust_column_widths(root, all_listboxes, notebook, emp_text, req_text, limits_text, summary_text):
    width = root.winfo_width()
    for lb in all_listboxes:
        lb.config(width=max(10, (width // 70)))  # Approximate, 7 days + shift label ~70 per col
    # Adjust input data tabs
    notebook.update_idletasks()
    for tab in [emp_text, req_text, limits_text, summary_text]:
        tab.configure(width=max(50, width // 10))  # Adjust text widget width

def on_resize(event, root, all_listboxes, notebook, emp_text, req_text, limits_text, summary_text):
    if event.widget == root:
        adjust_column_widths(root, all_listboxes, notebook, emp_text, req_text, limits_text, summary_text)

def on_mousewheel(event, canvas):
    canvas.yview_scroll(-1 * (event.delta // 120), "units")