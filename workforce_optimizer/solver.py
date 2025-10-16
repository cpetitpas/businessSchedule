import pulp
import logging
import time
from datetime import datetime, timedelta
from constants import DAYS

def solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days,
                  start_date, relax_day=True, relax_shift=True, relax_weekend=True, relax_min_shifts=True, num_weeks=2):
    logging.debug("Entering solve_schedule with relax_day=%s, relax_shift=%s, relax_weekend=%s, relax_min_shifts=%s, num_weeks=%d",
                  relax_day, relax_shift, relax_weekend, relax_min_shifts, num_weeks)
    prob = pulp.LpProblem("Restaurant_Schedule", pulp.LpMaximize)
    
    # Create decision variables
    x = {}
    y = {}
    for e in employees:
        x[e] = {}
        y[e] = {}
        for w in range(num_weeks):
            x[e][w] = {}
            y[e][w] = {}
            for d in days:
                x[e][w][d] = {}
                y[e][w][d] = pulp.LpVariable(f"y_{e}_w{w}_{d}", cat="Binary")
                for s in shifts:
                    x[e][w][d][s] = {}
                    for a in work_areas[e]:
                        x[e][w][d][s][a] = pulp.LpVariable(f"assign_{e}_w{w}_{d}_{s}_{a}", cat="Binary")
    logging.debug("Created %d decision variables for %d employees, %d weeks, %d days, %d shifts",
                  len(employees) * num_weeks * len(days) * len(shifts) * max(len(work_areas[e]) for e in employees),
                  len(employees), num_weeks, len(days), len(shifts))
    
    # Set objective function
    day_penalty = -10 if relax_day else 0
    shift_penalty = -10 if relax_shift else 0
    min_shifts_penalty = -100 if relax_min_shifts else 0
    objective = pulp.lpSum(
        x[e][w][d][s][a] * ((day_prefs[e][d] if day_prefs[e][d] > 0 else day_penalty) + (shift_prefs[e][s] if shift_prefs[e][s] > 0 else shift_penalty))
        for e in employees for w in range(num_weeks) for d in days for s in shifts for a in work_areas[e]
    )
    prob += objective
    logging.debug("Objective function set with day_penalty=%d, shift_penalty=%d, min_shifts_penalty=%d",
                  day_penalty, shift_penalty, min_shifts_penalty)
    
    # Staffing requirement constraints
    staffing_count = 0
    for w in range(num_weeks):
        for d in days:
            for s in shifts:
                for a in areas:
                    prob += pulp.lpSum(x[e][w][d][s][a] for e in employees if a in work_areas[e]) == required[d][a][s]
                    staffing_count += 1
    logging.debug("Added %d staffing requirement constraints", staffing_count)
    
    # Must-off constraints
    must_off_count = 0
    for e in employees:
        for w in range(num_weeks):
            for d in days:
                date = start_date + timedelta(days=(w * 7 + DAYS.index(d)))
                date_str = date.strftime("%Y-%m-%d")
                off_dates = [off_date for _, off_date in must_off.get(e, [])]
                logging.debug("Checking must-off for %s on %s: off_dates=%s", e, date_str, off_dates)
                if date_str in off_dates:
                    for s in shifts:
                        for a in work_areas[e]:
                            prob += x[e][w][d][s][a] == 0
                            must_off_count += 1
    logging.debug("Added %d must-off constraints", must_off_count)
    
    # Max shifts per day constraints
    max_shifts_day_count = 0
    for e in employees:
        for w in range(num_weeks):
            for d in days:
                prob += pulp.lpSum(x[e][w][d][s][a] for s in shifts for a in work_areas[e]) <= constraints["max_shifts_per_day"]
                max_shifts_day_count += 1
    logging.debug("Added %d max shifts per day constraints", max_shifts_day_count)
    
    # Max shifts per week constraints
    max_shifts_week_count = 0
    for e in employees:
        for w in range(num_weeks):
            prob += pulp.lpSum(x[e][w][d][s][a] for d in days for s in shifts for a in work_areas[e]) <= max_shifts[e]
            max_shifts_week_count += 1
    logging.debug("Added %d max shifts per week constraints", max_shifts_week_count)
    
    # Min shifts per week constraints
    min_shifts_week_count = 0
    for e in employees:
        for w in range(num_weeks):
            prob += pulp.lpSum(x[e][w][d][s][a] for d in days for s in shifts for a in work_areas[e]) >= min_shifts[e] - (2 if relax_min_shifts else 0)
            min_shifts_week_count += 1
    logging.debug("Added %d min shifts per week constraints", min_shifts_week_count)
    
    # Link y to x
    link_count = 0
    for e in employees:
        for w in range(num_weeks):
            for d in days:
                prob += y[e][w][d] >= pulp.lpSum(x[e][w][d][s][a] for s in shifts for a in work_areas[e]) / (len(shifts) * len(work_areas[e]))
                link_count += 1
    logging.debug("Added %d link constraints", link_count)
    
    # Solve the problem
    start_time = time.time()
    prob.solve()
    end_time = time.time()
    solver_time = end_time - start_time
    logging.info("Solver status: %s, runtime: %.2f seconds", pulp.LpStatus[prob.status], solver_time)
    if prob.status == pulp.LpStatusOptimal:
        obj_value = pulp.value(prob.objective)
        if obj_value is not None:
            logging.info("Objective value: %.2f", obj_value)
        else:
            logging.info("Objective value: None (problem not solved to optimality)")
        assigned_shifts = []
        for e in employees:
            for w in range(num_weeks):
                for d in days:
                    for s in shifts:
                        for a in work_areas[e]:
                            if pulp.value(x[e][w][d][s][a]) == 1:
                                assigned_shifts.append(f"{e} assigned to {a}, {d}, {s}, week {w}")
        logging.debug("Assigned shifts: %s", assigned_shifts[:10])
        if len(assigned_shifts) > 10:
            logging.debug("... and %d more assigned shifts", len(assigned_shifts) - 10)
    
    logging.debug("Exiting solve_schedule")
    return prob, x

def validate_weekend_constraints(x, employees, days, shifts, work_areas, max_weekend_days, start_date, num_weeks):
    logging.debug("Entering validate_weekend_constraints")
    violations = []
    fri_sun_windows = []
    for w in range(num_weeks - 1):
        fri_sun_windows.append([(w, "Fri"), (w, "Sat"), (w + 1, "Sun")])
    if num_weeks > 0:
        fri_sun_windows.append([(num_weeks - 1, "Fri"), (num_weeks - 1, "Sat")])
    for e in employees:
        if e in work_areas:  # Check if employee is valid
            for i, window in enumerate(fri_sun_windows):
                day_counts = 0
                for w, d in window:
                    day_shift_count = sum(
                        pulp.value(x[e][w][d][s][a]) for s in shifts for a in work_areas[e]
                    )
                    if day_shift_count > 0:
                        day_counts += 1
                if day_counts > max_weekend_days[e]:
                    window_dates = " to ".join(
                        f"{d}, {(start_date + timedelta(days=(w * 7 + DAYS.index(d)))).strftime('%b %d, %y')}"
                        for w, d in window
                    )
                    violations.append(f"{e} has {int(day_counts)} days in weekend period {window_dates}")
                    logging.warning("Weekend constraint violation: %s has %d days in %s", e, int(day_counts), window_dates)
    logging.debug("Exiting validate_weekend_constraints with %d violations", len(violations))
    return violations