import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from prophet import Prophet
from sklearn.linear_model import LinearRegression
import pandas as pd
from spos_service.utils.supabase_client import delete_data, fetch_data, insert_data
import json

def forecast_daily_visits(appointments, open_hours, profitability_data):
    """
    Forecast daily visits using Prophet.

    Args:
        appointments (list): List of appointment records.
        open_hours (dict): Dictionary containing open hours for each day.

    Returns:
        dict: Forecasted hourly visitor counts with avg and std dev.
    """
    df = pd.DataFrame(appointments)
    df["ds"] = pd.to_datetime(df["start_time"]).dt.date
    df["y"] = 1  # Each appointment counts as one visit
    df = df.groupby("ds").sum().reset_index()

    model = Prophet()
    model.fit(df)

    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)

    
    forecast["weekday"] = forecast["ds"].dt.day_name()

    def calculate_visitors_per_hour(row):
        day_name = row["weekday"].lower()
        profitability_score = profitability_data[day_name]["profitability_score"]
        should_be_closed = profitability_data[day_name]["is_closed"]
        if day_name in open_hours and (not open_hours[day_name]["closed"] or not should_be_closed):
            if not should_be_closed and open_hours[day_name]["closed"]:
                # Find a similar day based on profitability_score
                similar_day = min(
                    (d for d, data in profitability_data.items() if d != day_name and not data.get("is_closed", True)),
                    key=lambda d: abs(profitability_data[d]["profitability_score"] - profitability_score),
                    default=None
                )
                if similar_day:
                    # Use the forecast values of the similar day
                    similar_forecast = forecast[forecast["weekday"].str.lower() == similar_day.lower()]
                    if not similar_forecast.empty:
                        avg_yhat = similar_forecast["yhat"].mean()
                        similar_hours_open = open_hours[similar_day]["to"] - open_hours[similar_day]["from"]
                        adjusted_visitors = avg_yhat * (1 + profitability_data[day_name]["profitability_score"] / 20)
                        return adjusted_visitors / similar_hours_open
                return 0
            else:
                hours_open = open_hours[day_name]["to"] - open_hours[day_name]["from"]
                adjusted_visitors = row["yhat"] * (1 + profitability_score / 20)  # Apply profitability score (-5% to +10%)
                return adjusted_visitors / hours_open
        return 0

    forecast["visitors_per_hour"] = forecast.apply(calculate_visitors_per_hour, axis=1)

    grouped = forecast.groupby(forecast["weekday"].str.lower()).agg(
        avg_visitors=("visitors_per_hour", "mean"),
        std_dev_visitors=("visitors_per_hour", "std")
    ).to_dict("index")

    return grouped

def calculate_service_capacity(hours_open, employees, avg_service_duration):
    """
    Calculate the maximum number of services that can be completed.

    Args:
        hours_open (int): Number of hours the business is open.
        employees (int): Number of employees available.
        avg_service_duration (float): Average duration of a service in hours.

    Returns:
        int: Maximum services that can be completed.
    """
    return int(hours_open / avg_service_duration)

def evaluate_schedule(hours_open, visits_simulated, avg_service_duration, employee_capacity_per_hour, services, employees, profitability_factor):
    """
    Evaluate a schedule and calculate profitability.

    Args:
        hours_open (int): Hours the business operates.
        visits_simulated (int): Simulated visitor count.
        avg_service_duration (float): Average service duration in hours.
        employee_capacity_per_hour (int): Capacity per employee per hour.
        services (list): List of services with prices.
        employees (list): List of employees with hourly costs.
        profitability_factor (float): Profitability adjustment factor (-1 to 2).

    Returns:
        dict: Evaluation results for the schedule.
    """

    # Calculate max service capacity
    max_services_capacity_per_employee = calculate_service_capacity(hours_open, len(employees), avg_service_duration)

    # Calculate employees needed
    employees_needed = int(round(visits_simulated / max_services_capacity_per_employee))
    if employees_needed > len(employees):
        employees_needed = len(employees)

    # Calculate revenue, costs, and profit
    avg_service_price = np.mean([service["price"] for service in services])
    avg_employee_cost = np.mean([employee["cost_per_hour"] for employee in employees])

    revenue_simulated = visits_simulated * avg_service_price
    cost_simulated = employees_needed * hours_open * avg_employee_cost
    profit_simulated = revenue_simulated - cost_simulated

    return {
        "hours_open": hours_open,
        "visits_simulated": int(round(visits_simulated, 0)),
        "employees_needed": employees_needed,
        "revenue_simulated": round(revenue_simulated, 2),
        "cost_simulated": round(cost_simulated, 2),
        "profit_simulated": round(profit_simulated, 2),
    }

def monte_carlo_simulation(runs=1000, min_visits_for_open=15, employee_capacity_per_hour=4, max_weekly_hours=180, min_weekly_hours=140, open_days=None):
    """
    Perform Monte Carlo simulation for optimal business planning.

    Args:
        runs (int): Number of simulation iterations.
        min_visits_for_open (int): Minimum visitors per hour required to keep the business open.
        employee_capacity_per_hour (int): Number of visitors an employee can handle per hour.
        max_weekly_hours (int): Maximum hours an employee can work per week.

    Returns:
        list: Best simulation results for the week.
    """
    profitability_data = {row["day_of_week"]: row for row in fetch_data("day_profitability")}
    services = fetch_data("services")
    employees = fetch_data("employees")
    appointments = fetch_data("appointments")
    open_hours_data = fetch_data("open_hours")
    for week_day, day_data in profitability_data.items():
        delete_data("monte_carlo_results", {"week_day": week_day})

    avg_service_duration = np.mean([service["time"] for service in services]) / 60  # Convert minutes to hours
    open_hours = open_hours_data[0]["open_hours"]  # Assuming single row for open_hours

    visit_forecasts = forecast_daily_visits(appointments, open_hours, profitability_data)  # Pass open_hours to forecast function
    results = defaultdict(list)
    total_hours_used = defaultdict(int)
    day_results = []
    for week_day, day_data in profitability_data.items():
        possible_hours = generate_schedules()
        day_results.append({
            "week_day": week_day,
            "is_open": False,
            "hours_open": 0,
            "employees_needed": 0,
            "profit_simulated": 0.0,
        })
        if week_day == 'sunday':
            continue
        for schedule in possible_hours:
            for _ in range(runs):
                scheduled_hours = int((datetime.strptime(schedule["end_time"], "%H:%M:%S") - datetime.strptime(schedule["start_time"], "%H:%M:%S")).seconds / 3600)
                visits_simulated = max(0, int(np.random.normal(
                    loc=visit_forecasts[week_day]["avg_visitors"],
                    scale=max(visit_forecasts[week_day]["std_dev_visitors"], 0.1)  # Avoid zero std deviation
                ) * scheduled_hours))  # Convert hourly visitors to daily visitors
                result = evaluate_schedule(scheduled_hours, visits_simulated, avg_service_duration, employee_capacity_per_hour, services, employees, day_data["profitability_score"])
                result.update(schedule)
                result["week_day"] = week_day
                result["is_open"] = True
                if visits_simulated < min_visits_for_open or result["profit_simulated"] < 500:  # Adjusted to hourly threshold
                    continue
                else:
                    day_results.append(result)

    weekly_results = simulate_best_schedule(day_results, max_weekly_hours, min_weekly_hours, open_days)

    for result in weekly_results:
        insert_data("monte_carlo_results", result)

    return weekly_results


def generate_schedules():
    """
    Generate possible schedules for the business.

    Returns:
        list: List of dictionaries containing start and end times.
    """
    return [
        {"start_time": "08:00:00", "end_time": "14:00:00"},
        {"start_time": "09:00:00", "end_time": "15:00:00"},
        {"start_time": "09:00:00", "end_time": "17:00:00"},
        {"start_time": "09:00:00", "end_time": "19:00:00"},
        {"start_time": "10:00:00", "end_time": "14:00:00"},
        {"start_time": "10:00:00", "end_time": "16:00:00"},
        {"start_time": "10:00:00", "end_time": "18:00:00"},
        {"start_time": "10:00:00", "end_time": "20:00:00"},
        {"start_time": "11:00:00", "end_time": "15:00:00"},
        {"start_time": "11:00:00", "end_time": "17:00:00"},
        {"start_time": "12:00:00", "end_time": "16:00:00"},
        {"start_time": "12:00:00", "end_time": "18:00:00"},
        {"start_time": "12:00:00", "end_time": "20:00:00"},
        {"start_time": "13:00:00", "end_time": "17:00:00"},
        {"start_time": "13:00:00", "end_time": "19:00:00"},
        {"start_time": "14:00:00", "end_time": "18:00:00"},
        {"start_time": "14:00:00", "end_time": "20:00:00"},
        {"start_time": "15:00:00", "end_time": "19:00:00"},
        {"start_time": "16:00:00", "end_time": "20:00:00"},
    ]


from itertools import product
import numpy as np
from collections import defaultdict

def simulate_best_schedule(day_results, max_weekly_hours=180, min_weekly_hours=140, open_days=None ):
    """
    Optimize the weekly schedule to maximize profit under constraints.

    Args:
        day_results (list): List of daily results.
        max_weekly_hours (int): Maximum weekly hours allowed.

    Returns:
        dict: The best weekly schedule and corresponding stats.
    """
    # Step 1: Group day_results by weekday
    days_grouped = defaultdict(list)
    for entry in day_results:
        days_grouped[entry["week_day"].lower()].append(entry)
    
    # Ensure all days of the week are present in the dataset
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for day in weekdays:
        if day not in days_grouped:
            raise ValueError(f"Missing data for {day} in day_results.")
    
    # Step 2: Generate combinations, one entry per weekday
    best_combination = None
    best_profit = -np.inf
    ignore_days = False
    if open_days == None:
        ignore_days = True
        open_days = 0

    for combination in (
        combination for combination in product(
            *[days_grouped[day] for day in weekdays]
        )
        if sum(day["hours_open"] * day["employees_needed"] for day in combination) <= max_weekly_hours
        and sum(day["hours_open"] * day["employees_needed"] for day in combination) >= min_weekly_hours
        and (ignore_days or sum(day["is_open"] for day in combination) == open_days)
    ):
        total_profit = sum(day["profit_simulated"] for day in combination)
        if total_profit > best_profit:
            best_combination = combination
            best_profit = total_profit

    return best_combination
