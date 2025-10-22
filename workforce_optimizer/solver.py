import pulp
import logging
from datetime import datetime, timedelta
from collections import defaultdict

def setup_problem(employees, day_offsets, shifts, areas, shift_prefs, day_prefs, work_areas, constraints, min_shifts, max_shifts, max_weekend_days, num_weeks, relax_day, relax_shift, relax_weekend, relax_max_shifts, actual_days):
    prob = pulp.LpProblem("Restaurant_Schedule", pulp.LpMaximize)
    
    # Decision variables
    x = {}  # x[e][w][k][s][a]: Binary variable for employee e assigned to week w, day offset k, shift s, area a
    y = {}  # y[e][w][k]: Binary variable indicating if employee e works on day offset k in week w
    for e in employees:
        x[e] = {w: {k: {s: {a: pulp.LpVariable(f"assign_{e}_w{w}_{k}_{s}_{a}", cat="Binary") for a in work_areas[e]} for s in shifts} for k in day_offsets} for w in range(num_weeks)}
        y[e] = {w: {k: pulp.LpVariable(f"y_{e}_w{w}_{k}", cat="Binary") for k in day_offsets} for w in range(num_weeks)}
    
    # Objective function: Maximize preference satisfaction, penalize violations if relaxed
    day_penalty = -10 if relax_day else 0
    shift_penalty = -10 if relax_shift else 0
    objective = pulp.lpSum(
        x[e][w][k][s][a] * (
            (day_prefs[e][actual_days[k]] if day_prefs[e][actual_days[k]] > 0 else day_penalty) +
            (shift_prefs[e][s] if shift_prefs[e][s] > 0 else shift_penalty)
        )
        for e in employees for w in range(num_weeks) for k in day_offsets for s in shifts for a in work_areas[e]
    )
    prob += objective
    logging.debug("Objective function set with day_penalty=%d, shift_penalty=%d", day_penalty, shift_penalty)
    
    return prob, x, y

def add_constraints(prob, x, y, employees, day_offsets, shifts, areas, required, work_areas, constraints, must_off, min_shifts, max_shifts, max_weekend_days, start_date, num_weeks, relax_min_shifts, relax_max_shifts, relax_weekend, actual_days):
    # Staffing requirements
    for w in range(num_weeks):
        for k in day_offsets:
            model_d = actual_days[k]
            for s in shifts:
                for a in areas:
                    prob += pulp.lpSum(x[e][w][k][s][a] for e in employees if a in work_areas[e]) == required[model_d][a][s]
    
    # Must-off constraints (hard)
    for e in employees:
        for w in range(num_weeks):
            for k in day_offsets:
                date = start_date + timedelta(days=(w * 7 + k))
                date_str = date.strftime("%Y-%m-%d")
                off_dates = [datetime.strptime(off_date, "%m/%d/%Y").strftime("%Y-%m-%d") for _, off_date in must_off.get(e, [])]
                if date_str in off_dates:
                    for s in shifts:
                        for a in work_areas[e]:
                            prob += x[e][w][k][s][a] == 0
    
    # Max shifts per day (hard)
    for e in employees:
        for w in range(num_weeks):
            for k in day_offsets:
                prob += pulp.lpSum(x[e][w][k][s][a] for s in shifts for a in work_areas[e]) <= constraints["max_shifts_per_day"]
    
    # Max shifts per week
    for e in employees:
        for w in range(num_weeks):
            prob += pulp.lpSum(x[e][w][k][s][a] for k in day_offsets for s in shifts for a in work_areas[e]) <= max_shifts[e] + (2 if relax_max_shifts else 0)
    
    # Min shifts per week
    for e in employees:
        for w in range(num_weeks):
            prob += pulp.lpSum(x[e][w][k][s][a] for k in day_offsets for s in shifts for a in work_areas[e]) >= min_shifts[e] - (2 if relax_min_shifts else 0)
    
    # Max weekend days (Fri-Sun)
    if not relax_weekend:
        for e in employees:
            for w in range(num_weeks):
                fri_sun_days = ["Fri", "Sat"] if w == num_weeks - 1 else ["Fri", "Sat", "Sun"]
                fri_sun = [k for k in day_offsets if actual_days[k] in fri_sun_days]
                prob += pulp.lpSum(y[e][w][k] for k in fri_sun) <= max_weekend_days[e]
    
    # Link y to x
    for e in employees:
        for w in range(num_weeks):
            for k in day_offsets:
                prob += y[e][w][k] >= pulp.lpSum(x[e][w][k][s][a] for s in shifts for a in work_areas[e]) / (len(shifts) * len(work_areas[e]))

def validate_weekend_constraints(x, employees, day_offsets, shifts, work_areas, max_weekend_days, start_date, num_weeks, actual_days):
    violations = []
    fri_sun_windows = [[(w, k) for k in day_offsets if actual_days[k] in (["Fri", "Sat", "Sun"] if w < num_weeks - 1 else ["Fri", "Sat"])] for w in range(num_weeks)]
    for e in employees:
        for i, window in enumerate(fri_sun_windows):
            day_counts = sum(
                1 if sum(pulp.value(x[e][w][k][s][a]) or 0 for s in shifts for a in work_areas[e]) >= 0.5 else 0
                for w, k in window
            )
            if day_counts > max_weekend_days[e]:
                window_dates = " to ".join(
                    f"{actual_days[k]}, {(start_date + timedelta(days=(w * 7 + k))).strftime('%b %d, %Y')}"
                    for w, k in window
                )
                violations.append(f"{e} has {day_counts} weekend days in period {window_dates}, exceeding limit of {max_weekend_days[e]}")
    return violations

def get_employee_summary(employees, work_areas, required, days, shifts, areas):
    available = defaultdict(int)
    for e in employees:
        for a in work_areas[e]:
            available[a] += 1
    required_shifts = {a: sum(required[d][a][s] for d in days for s in shifts) for a in areas}
    summary = "Employee Summary:\n"
    for a in areas:
        summary += f"- {a}: {available[a]} employees available, {required_shifts[a]} shifts required\n"
    return summary

def solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, constraints, min_shifts, max_shifts, max_weekend_days, start_date, num_weeks=2):
    logging.debug("Starting solve_schedule with %d employees, %d days, %d shifts, %d areas", len(employees), len(days), len(shifts), len(areas))
    violation_order = constraints["violate_order"]
    logging.debug("Violation order: %s", violation_order)
    
    # Compute actual_days based on start_date
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    start_weekday = start_date.weekday()  # 0=Mon, 1=Tue, ..., 5=Sat, 6=Sun
    actual_days = []
    for k in range(7):
        weekday = (start_weekday + k) % 7
        actual_days.append(day_names[weekday])
    logging.debug("Actual days for schedule: %s", actual_days)
    
    # Dynamic relaxation based on violation_order
    rule_to_flag = {
        "Day Weights": 'relax_day',
        "Shift Weights": 'relax_shift',
        "Max Number of Weekend Days": 'relax_weekend',
        "Max Shifts per Week": 'relax_max_shifts'
    }
    relax_params = {
        'relax_day': False,
        'relax_shift': False,
        'relax_weekend': False,
        'relax_max_shifts': False,
        'relax_min_shifts': False
    }
    configs = []
    configs.append((relax_params['relax_day'], relax_params['relax_shift'], relax_params['relax_weekend'], relax_params['relax_max_shifts']))
    for rule in violation_order:
        if rule in rule_to_flag:
            relax_params[rule_to_flag[rule]] = True
        configs.append((relax_params['relax_day'], relax_params['relax_shift'], relax_params['relax_weekend'], relax_params['relax_max_shifts']))
    
    # Remove duplicates
    configs = list(dict.fromkeys(configs))
    
    employee_summary = get_employee_summary(employees, work_areas, required, actual_days, shifts, areas)
    logging.info(employee_summary)
    
    day_offsets = range(7)
    for i, (relax_day, relax_shift, relax_weekend, relax_max_shifts) in enumerate(configs):
        logging.info("Attempt %d: relax_day=%s, relax_shift=%s, relax_weekend=%s, relax_max_shifts=%s", i + 1, relax_day, relax_shift, relax_weekend, relax_max_shifts)
        prob, x, y = setup_problem(employees, day_offsets, shifts, areas, shift_prefs, day_prefs, work_areas, constraints, min_shifts, max_shifts, max_weekend_days, num_weeks, relax_day, relax_shift, relax_weekend, relax_max_shifts, actual_days)
        add_constraints(prob, x, y, employees, day_offsets, shifts, areas, required, work_areas, constraints, must_off, min_shifts, max_shifts, max_weekend_days, start_date, num_weeks, relax_min_shifts=relax_max_shifts, relax_max_shifts=relax_max_shifts, relax_weekend=relax_weekend, actual_days=actual_days)
        
        prob.solve()
        if prob.status == pulp.LpStatusOptimal:
            logging.info("Solution found with objective value: %.2f", pulp.value(prob.objective))
            violations = validate_weekend_constraints(x, employees, day_offsets, shifts, work_areas, max_weekend_days, start_date, num_weeks, actual_days)
            if violations:
                logging.warning("Weekend constraint violations: %s", violations)
            # Prepare output schedules
            bar_schedule = []
            kitchen_schedule = []
            summary = []
            for w in range(num_weeks):
                for k in day_offsets:
                    for e in employees:
                        for s in shifts:
                            for a in work_areas[e]:
                                if pulp.value(x[e][w][k][s][a]) >= 0.5:
                                    date = start_date + timedelta(days=(w * 7 + k))
                                    d = actual_days[k]
                                    entry = [e, date.strftime("%Y-%m-%d"), d, s, a]
                                    if a == "Bar":
                                        bar_schedule.append(entry)
                                    else:
                                        kitchen_schedule.append(entry)
                                    summary.append(entry)
            return prob, x, {
                "bar_schedule": bar_schedule,
                "kitchen_schedule": kitchen_schedule,
                "summary": summary,
                "violations": violations,
                "employee_summary": employee_summary
            }
        
        logging.info("No feasible solution found for attempt %d", i + 1)
    
    # If no solution is found, return staffing shortage message with employee summary
    shortage_message = "Failed to find a feasible schedule due to staffing shortages:\n" + employee_summary
    logging.error(shortage_message)
    return None, None, {
        "error": shortage_message,
        "employee_summary": employee_summary
    }