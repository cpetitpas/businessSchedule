# solver.py
import pulp
from pulp import PULP_CBC_CMD
import logging
from datetime import datetime, timedelta
from collections import defaultdict


def get_capacity_report(employees, work_areas, required, actual_days, shifts, areas, max_shifts):
    """
    Build a capacity report that is always shown in the Summary Report and in the
    message-box when the solver succeeds or fails.

    Returns
    -------
    report : str
        Multi-line string with:
        1. Total shifts required per work area
        2. Total max-shifts-per-week available per work area
        3. List of areas that are under-capacity (required > available)
    """
    # Required shifts (sum over all days & all shifts)
    required_shifts = {
        a: sum(required[d][a][s] for d in actual_days for s in shifts)
        for a in areas
    }

    # Available capacity = Σ max_shifts per employee that can work the area
    available_capacity = defaultdict(int)
    for emp in employees:
        area = work_areas[emp][0]                     # one area per employee
        available_capacity[area] += max_shifts[emp]

    # Identify short-falls
    shortfalls = {
        a: required_shifts[a] - available_capacity[a]
        for a in areas if required_shifts[a] > available_capacity[a]
    }

    lines = ["Capacity Report:"]
    for a in areas:
        lines.append(
            f"- {a}: {required_shifts[a]} shifts required, "
            f"{available_capacity[a]} max shifts available"
        )
    if shortfalls:
        lines.append("\nUnder-capacity areas:")
        for a, diff in shortfalls.items():
            lines.append(f"  • {a}: short by {diff} shift(s)")

    return "\n".join(lines)


def setup_problem(employees, day_offsets, shifts, areas, shift_prefs, day_prefs, work_areas,
                  min_shifts, max_shifts, max_weekend_days, num_weeks, relax_day, relax_shift, required, actual_days):
    prob = pulp.LpProblem("Restaurant_Schedule", pulp.LpMaximize)

    x = {}
    y = {}
    for e in employees:
        valid_areas = work_areas.get(e, [])
        if not valid_areas:
            logging.warning(f"Employee {e} has no work areas. Skipping.")
            continue

        x[e] = {}
        y[e] = {
            w: {k: pulp.LpVariable(f"y_{e}_w{w}_{k}", cat="Binary") for k in day_offsets}
            for w in range(num_weeks)
        }

        for w in range(num_weeks):
            x[e][w] = {}
            for k in day_offsets:
                day_name = actual_days[k]
                x[e][w][k] = {}
                for s in shifts:
                    x[e][w][k][s] = {}
                    for a in valid_areas:
                        if required[day_name][a][s] > 0:
                            x[e][w][k][s][a] = pulp.LpVariable(f"assign_{e}_w{w}_{k}_{s}_{a}", cat="Binary")
                        else:
                            x[e][w][k][s][a] = 0  # constant 0 - key exists, no assignment possible

    # Normalise day preferences
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
    objective = pulp.lpSum(
        x[e][w][k][s][a] * (
            normalized_day_prefs[e][k] +
            (10 if shift_prefs[e][s] > 0 else (0 if relax_shift else -50)) +
            1   # <<< THIS +1 IS THE KEY - encourages scheduling when neutral
        )
        for e in x
        for w in range(num_weeks)
        for k in day_offsets
        for s in shifts
        for a in work_areas[e]
    )
    prob += objective
    return prob, x, y


def add_constraints(
    prob, x, y, employees, day_offsets, shifts, areas, required, work_areas, constraints,
    must_off, min_shifts, max_shifts, max_weekend_days, start_date, num_weeks,
    relax_min_shifts=False, relax_max_shifts=False, relax_weekend=False,
    relax_shift=False, actual_days=None
):
    if actual_days is None:
        raise ValueError("actual_days must be provided")
    # Staffing
    for w in range(num_weeks):
        for k in day_offsets:
            day_name = actual_days[k]
            for s in shifts:
                for a in areas:
                    req = required[day_name][a][s]
                    if req == 0:
                        continue  # No variables created → nothing to constrain
                    lhs = pulp.lpSum(
                        x[e][w][k][s][a]
                        for e in employees
                        if e in x and w in x[e] and k in x[e][w] and s in x[e][w][k] and a in x[e][w][k][s] and isinstance(x[e][w][k][s][a], pulp.LpVariable)
                    )
                    prob += lhs == req, f"Staff_{w}_{day_name}_{s}_{a}"

    # Must-off
    for e in x:
        for w in range(num_weeks):
            for k in day_offsets:
                date = start_date + timedelta(days=w*7 + k)
                date_str = date.strftime("%Y-%m-%d")
                off_dates = [datetime.strptime(off, "%m/%d/%Y").strftime("%Y-%m-%d") for _, off in must_off.get(e, [])]
                if date_str in off_dates:
                    for s in shifts:
                        for a in work_areas[e]:
                            if isinstance(x[e][w][k][s][a], pulp.LpVariable):
                                prob += x[e][w][k][s][a] == 0

    # Max shifts per day
    for e in x:
        for w in range(num_weeks):
            for k in day_offsets:
                prob += pulp.lpSum(x[e][w][k][s][a]
                    for s in shifts
                    for a in work_areas[e]
                    if isinstance(x[e][w][k][s][a], pulp.LpVariable)) <= constraints["max_shifts_per_day"]

    # Max shifts per week
    for e in x:
        for w in range(num_weeks):
            prob += pulp.lpSum(
               x[e][w][k][s][a]
                for k in day_offsets
                for s in shifts
                for a in work_areas[e]
                if isinstance(x[e][w][k][s][a], pulp.LpVariable)
            ) <= max_shifts[e] + (2 if relax_max_shifts else 0)

    # Min shifts per week
    for e in x:
        for w in range(num_weeks):
            prob += pulp.lpSum(
                x[e][w][k][s][a]
                for k in day_offsets
                for s in shifts
                for a in work_areas[e]
                if isinstance(x[e][w][k][s][a], pulp.LpVariable)
            ) >= min_shifts[e] - (2 if relax_min_shifts else 0)

    # Weekend constraint
    if not relax_weekend:
        end_date = start_date + timedelta(days=7*num_weeks - 1)
        current = start_date - timedelta(days=6)
        weekends = []
        while current <= end_date + timedelta(days=2):
            if current.weekday() == 4:               # Friday
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

    # Link y to x
    for e in x:
        num_options = len(shifts) * len(work_areas[e])
        if num_options == 0:
            continue
        for w in range(num_weeks):
            for k in day_offsets:
                prob += y[e][w][k] >= pulp.lpSum(
                    x[e][w][k][s][a]
                    for s in shifts
                    for a in work_areas[e]
                    if isinstance(x[e][w][k][s][a], pulp.LpVariable)
                ) / num_options


def solve_schedule(employees, days, shifts, areas, shift_prefs, day_prefs, must_off, required, work_areas,
                   constraints, min_shifts, max_shifts, max_weekend_days, start_date, num_weeks=2):
    logging.debug("solve_schedule start")
    violation_order = constraints["violate_order"]

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    start_weekday = start_date.weekday()
    actual_days = [day_names[(start_weekday + k) % 7] for k in range(7)]

    # ----- NEW: capacity report (always returned) -----
    capacity_report = get_capacity_report(
        employees, work_areas, required, actual_days, shifts, areas, max_shifts
    )
    # --------------------------------------------------

    possible_rules = {
        "Preferred Days": 'relax_day',
        "Preferred Shift": 'relax_shift',
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

    day_offsets = range(7)

    for i, config in enumerate(configs):
        relax_flags = dict(zip(rule_to_flag.values(), config))
        logging.info("Attempt %d: %s", i + 1, ", ".join(f"{k}={v}" for k, v in relax_flags.items()))

        prob, x, y = setup_problem(
            employees, day_offsets, shifts, areas, shift_prefs, day_prefs, work_areas,
            min_shifts, max_shifts, max_weekend_days, num_weeks,
            relax_flags.get('relax_day', False),
            relax_flags.get('relax_shift', False),
            required,          # ← NEW: pass required
            actual_days        # ← already passed, keep it
        )
        add_constraints(
            prob, x, y, employees, day_offsets, shifts, areas, required, work_areas, constraints,
            must_off, min_shifts, max_shifts, max_weekend_days, start_date, num_weeks,
            relax_min_shifts=relax_flags.get('relax_min_shifts', False),
            relax_max_shifts=relax_flags.get('relax_max_shifts', False),
            relax_weekend=relax_flags.get('relax_weekend', False),
            relax_shift=relax_flags.get('relax_shift', False),
            actual_days=actual_days
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
            result_dict["capacity_report"] = capacity_report   # <-- always included
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

    # ----- FAILURE PATH -----
    hints = (
        "\n\nPossible fixes:\n"
        "1. Add \"Max Shifts per Week\" to the Violate Rules Order in Hard_Limits.csv.\n"
        "2. Increase Max Shifts per Week for employees in the under-capacity area(s).\n"
        "3. Remove or adjust \"Must have off\" dates for employees in the under-capacity area(s).\n"
        "3. If you have many employees in a given work area, add Min Shifts per Week to the Violate Rules Order (min shifts > total shifts/week)."
    )
    error_msg = (
        "Failed to find a feasible schedule due to insufficient weekly capacity.\n\n"
        f"{capacity_report}{hints}"
    )
    logging.error(error_msg)
    return None, None, {"error": error_msg, "capacity_report": capacity_report}