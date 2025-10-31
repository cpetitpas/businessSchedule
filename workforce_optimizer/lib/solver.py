import pulp
from pulp import PULP_CBC_CMD
import logging
from datetime import datetime, timedelta
from collections import defaultdict

def get_capacity_vs_demand(employees, work_areas, max_shifts, required, actual_days, shifts, areas):
    """
    Returns human-readable capacity vs demand + boolean if any shortage
    """
    capacity = {a: 0 for a in areas}
    demand = {a: 0 for a in areas}
    
    # Capacity: sum of max_shifts per week for employees in area
    for e in employees:
        for a in work_areas.get(e, []):
            capacity[a] += max_shifts[e]
    
    # Demand: total shifts required across all days
    for day in actual_days:
        for a in areas:
            for s in shifts:
                demand[a] += required[day][a][s]
    
    lines = ["STAFFING CAPACITY vs DEMAND:\n"]
    has_shortage = False
    for a in areas:
        cap = capacity[a]
        dem = demand[a]
        status = "OK" if cap >= dem else "SHORTAGE"
        shortage = dem - cap if dem > cap else 0
        if shortage > 0:
            has_shortage = True
        lines.append(f"{a}:")
        lines.append(f"  Available: {cap} shifts")
        lines.append(f"  Required : {dem} shifts")
        if shortage > 0:
            lines.append(f"  Shortage : {shortage} shifts  [{status}]")
        else:
            lines.append(f"  Status   : {status}")
        lines.append("")
    
    if has_shortage:
        lines.append("SOLUTION:")
        lines.append("1. Add 'Max Shifts per Week' to Violate Rules Order")
        lines.append("2. Increase Max Shifts per Week for employees in short areas")
        lines.append("3. Check 'Must have off' dates blocking availability")
    
    return "\n".join(lines), has_shortage

def setup_problem(employees, day_offsets, shifts, areas, shift_prefs, day_prefs, work_areas, 
                  min_shifts, max_shifts, max_weekend_days, num_weeks, relax_day, relax_shift, actual_days):
    prob = pulp.LpProblem("Restaurant_Schedule", pulp.LpMaximize)
    
    x = {}
    y = {}
    for e in employees:
        valid_areas = work_areas.get(e, [])
        if not valid_areas:
            logging.warning(f"Employee {e} has no work areas. Skipping.")
            continue

        x[e] = {
            w: {
                k: {
                    s: {
                        a: pulp.LpVariable(f"assign_{e}_w{w}_{k}_{s}_{a}", cat="Binary")  # ← FIXED: "Binary"
                        for a in valid_areas
                    } for s in shifts
                } for k in day_offsets
            } for w in range(num_weeks)
        }
        y[e] = {
            w: {k: pulp.LpVariable(f"y_{e}_w{w}_{k}", cat="Binary") for k in day_offsets}
            for w in range(num_weeks)
        }

    # Normalize day preferences
    non_weekend = ['Mon', 'Tue', 'Wed', 'Thu']
    normalized_day_prefs = {}
    for e in employees:
        if e not in x:
            normalized_day_prefs[e] = [0] * 7
            continue
        prefs = [day_prefs[e][actual_days[k]] for k in day_offsets if actual_days[k] in non_weekend]
        avg = sum(p for p in prefs if p > 0) / len([p for p in prefs if p > 0]) if any(prefs) else 1.0
        normalized_day_prefs[e] = [
            avg if (actual_days[k] in non_weekend and day_prefs[e][actual_days[k]] > 0) else 0
            for k in day_offsets
        ]

    # Objective
    day_penalty = -10 if relax_day else 0
    shift_penalty = -10 if relax_shift else 0
    objective = pulp.lpSum(
        x[e][w][k][s][a] * (
            (normalized_day_prefs[e][k] if normalized_day_prefs[e][k] > 0 else day_penalty) +
            (shift_prefs[e][s] if shift_prefs[e][s] > 0 else shift_penalty)
        )
        for e in x for w in range(num_weeks) for k in day_offsets for s in shifts for a in work_areas[e]
    )
    prob += objective

    return prob, x, y

def add_constraints(prob, x, y, employees, day_offsets, shifts, areas, required, work_areas, constraints, 
                    must_off, min_shifts, max_shifts, max_weekend_days, start_date, num_weeks, 
                    relax_min_shifts, relax_max_shifts, relax_weekend, actual_days):
    # === Staffing ===
    for w in range(num_weeks):
        for k in day_offsets:
            d = actual_days[k]
            for s in shifts:
                for a in areas:
                    prob += pulp.lpSum(
                        x[e][w][k][s][a] for e in x if a in work_areas[e]
                    ) == required[d][a][s]

    # === Must-off ===
    for e in x:
        for w in range(num_weeks):
            for k in day_offsets:
                date = start_date + timedelta(days=w*7 + k)
                date_str = date.strftime("%Y-%m-%d")
                off_dates = [datetime.strptime(off, "%m/%d/%Y").strftime("%Y-%m-%d") for _, off in must_off.get(e, [])]
                if date_str in off_dates:
                    for s in shifts:
                        for a in work_areas[e]:
                            prob += x[e][w][k][s][a] == 0

    # === Max shifts per day ===
    for e in x:
        for w in range(num_weeks):
            for k in day_offsets:
                prob += pulp.lpSum(x[e][w][k][s][a] for s in shifts for a in work_areas[e]) <= constraints["max_shifts_per_day"]

    # === Max shifts per week ===
    for e in x:
        for w in range(num_weeks):
            prob += pulp.lpSum(
                x[e][w][k][s][a] for k in day_offsets for s in shifts for a in work_areas[e]
            ) <= max_shifts[e] + (2 if relax_max_shifts else 0)

    # === Min shifts per week ===
    for e in x:
        for w in range(num_weeks):
            prob += pulp.lpSum(
                x[e][w][k][s][a] for k in day_offsets for s in shifts for a in work_areas[e]
            ) >= min_shifts[e] - (2 if relax_min_shifts else 0)

    # === Weekend constraint ===
    if not relax_weekend:
        end_date = start_date + timedelta(days=7*num_weeks - 1)
        current = start_date - timedelta(days=6)
        weekends = []
        while current <= end_date + timedelta(days=2):
            if current.weekday() == 4:  # Friday
                days = []
                for d in [current, current + timedelta(days=1), current + timedelta(days=2)]:
                    if start_date <= d <= end_date:
                        days_since = (d - start_date).days
                        w_idx = days_since // 7
                        k_idx = days_since % 7
                        days.append((w_idx, k_idx))
                if days:
                    weekends.append(days)
            current += timedelta(days=1)

        for e in x:
            for weekend in weekends:
                prob += pulp.lpSum(y[e][w][k] for w, k in weekend) <= max_weekend_days[e]

    # === Link y to x ===
    for e in x:
        num_options = len(shifts) * len(work_areas[e])
        if num_options == 0:
            continue
        for w in range(num_weeks):
            for k in day_offsets:
                prob += y[e][w][k] >= pulp.lpSum(
                    x[e][w][k][s][a] for s in shifts for a in work_areas[e]
                ) / num_options

def get_employee_summary(employees, work_areas, required, days, shifts, areas):
    available = defaultdict(int)
    for e in employees:
        for a in work_areas.get(e, []):
            available[a] += 1
    required_shifts = {a: sum(required[d][a][s] for d in days for s in shifts) for a in areas}
    return "Employee Summary:\n" + "\n".join(
        f"- {a}: {available[a]} employees available, {required_shifts[a]} shifts required"
        for a in areas
    )

def solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas, 
                   constraints, min_shifts, max_shifts, max_weekend_days, start_date, num_weeks=2):
    logging.debug("solve_schedule start")
    
    # === Compute actual_days ===
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    start_weekday = start_date.weekday()
    actual_days = [day_names[(start_weekday + k) % 7] for k in range(7)]
    
    # === EARLY CAPACITY CHECK ===
    capacity_msg, has_shortage = get_capacity_vs_demand(
        employees, work_areas, max_shifts, required, actual_days, shifts, areas
    )
    logging.info(capacity_msg)
    
    # === If hard shortage → fail fast ===
    if has_shortage and "Max Shifts per Week" not in constraints["violate_order"]:
        error_msg = capacity_msg
        logging.error(error_msg)
        return None, None, {"error": error_msg, "employee_summary": get_employee_summary(employees, work_areas, required, actual_days, shifts, areas)}
    
    violation_order = constraints["violate_order"]
    
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    start_weekday = start_date.weekday()
    actual_days = [day_names[(start_weekday + k) % 7] for k in range(7)]

    possible_rules = {
        "Day Weights": 'relax_day',
        "Shift Weights": 'relax_shift',
        "Max Number of Weekend Days": 'relax_weekend',
        "Max Shifts per Week": 'relax_max_shifts',
        "Min Shifts per Week": 'relax_min_shifts'
    }
    rule_to_flag = {r: f for r, f in possible_rules.items() if r in violation_order}
    relax_params = {f: False for f in rule_to_flag.values()}
    configs = [tuple(relax_params.values())]
    for rule in violation_order:
        if rule in rule_to_flag:
            relax_params[rule_to_flag[rule]] = True
        configs.append(tuple(relax_params.values()))
    configs = list(dict.fromkeys(configs))

    employee_summary = get_employee_summary(employees, work_areas, required, actual_days, shifts, areas)
    logging.info(employee_summary)

    day_offsets = range(7)
    for i, config in enumerate(configs):
        relax_flags = dict(zip(rule_to_flag.values(), config))
        logging.info("Attempt %d: %s", i + 1, ", ".join(f"{k}={v}" for k, v in relax_flags.items()))

        prob, x, y = setup_problem(
            employees, day_offsets, shifts, areas, shift_prefs, day_prefs, work_areas,
            min_shifts, max_shifts, max_weekend_days, num_weeks,
            relax_flags.get('relax_day', False),
            relax_flags.get('relax_shift', False),
            actual_days
        )
        add_constraints(
            prob, x, y, employees, day_offsets, shifts, areas, required, work_areas, constraints,
            must_off, min_shifts, max_shifts, max_weekend_days, start_date, num_weeks,
            relax_flags.get('relax_min_shifts', False),
            relax_flags.get('relax_max_shifts', False),
            relax_flags.get('relax_weekend', False),
            actual_days
        )

        solver = PULP_CBC_CMD(msg=False, timeLimit=300)
        status = prob.solve(solver)
        if status != 1:
            logging.info("No solution in attempt %d", i + 1)
            continue

        if prob.status == pulp.LpStatusOptimal:
            logging.info("Solution found!")
            result_dict = {f"{a.lower()}_schedule": [] for a in areas}
            result_dict["violations"] = []
            result_dict["employee_summary"] = employee_summary

            for w in range(num_weeks):
                for k in day_offsets:
                    for e in x:
                        for s in shifts:
                            for a in work_areas[e]:
                                if pulp.value(x[e][w][k][s][a]) >= 0.5:
                                    date = start_date + timedelta(days=w*7 + k)
                                    entry = [e, date.strftime("%Y-%m-%d"), actual_days[k], s, a]
                                    result_dict[f"{a.lower()}_schedule"].append(entry)

            return prob, x, result_dict

    error_msg = "Failed to find a feasible schedule due to staffing shortages:\n" + employee_summary
    logging.error(error_msg)
    return None, None, {"error": error_msg, "employee_summary": employee_summary}