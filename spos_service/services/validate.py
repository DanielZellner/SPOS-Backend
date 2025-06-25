import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from prophet import Prophet
from sklearn.linear_model import LinearRegression
import pandas as pd
from spos_service.services.monte_carlo import forecast_daily_visits
from spos_service.utils.supabase_client import delete_data, fetch_data, fetch_with_date_range, insert_data


def monte_carlo_simulation_validate(evaluation_month=None):
    """
    Validate Monte Carlo simulation by comparing actual weekly revenues from Supabase historical data
    with simulated weekly revenues under new opening times.

    Args:
        evaluation_month (str): Month to validate in "YYYY-MM" format (default: previous month).

    Returns:
        dict: Validation metrics comparing one regular week to one Monte Carlo simulation week.
    """
    import numpy as np

    if evaluation_month is None:
        today = datetime.now()
        first_of_current_month = today.replace(day=1)
        last_month = first_of_current_month - timedelta(days=1)
        evaluation_month = last_month.strftime("%Y-%m")

    # Fetch a single week's historical appointments and simulation results
    appointments = fetch_with_date_range(
        "appointments", start_date=f"{evaluation_month}-06", end_date=f"{evaluation_month}-12"
    )
    simulation_results = fetch_data("monte_carlo_results")

    if not appointments:
        raise ValueError("No appointment data found for the evaluation period.")
    if not simulation_results:
        raise ValueError("No simulation results available for validation.")

    # Sum up total prices for the historical week
    df_appointments = pd.DataFrame(appointments)
    actual_revenue = df_appointments["total_price"].sum()

    # Sum up total simulated revenues for the Monte Carlo week
    simulated_revenue = sum(
        float(res["revenue_simulated"]) for res in simulation_results if res["is_open"]
    )

    # Compare the two weeks
    revenue_difference = simulated_revenue - actual_revenue
    percentage_change = (revenue_difference / actual_revenue * 100) if actual_revenue != 0 else 0

    return {
        "historical_week_revenue": round(float(actual_revenue), 2),
        "monte_carlo_week_revenue": round(float(simulated_revenue), 2),
        "revenue_difference": round(float(revenue_difference), 2),
        "percentage_change": round(float(percentage_change), 2),
    }










    

def  dynamic_pricing_validate(evaluation_period=30):
    """
    Validate the dynamic pricing model by comparing actual and forecasted results.

    Args:
        evaluation_period (int): Number of days to evaluate the model (default: 30).

    Returns:
        dict: Validation metrics such as revenue improvement and demand prediction accuracy.
    """
    # Fetch data from Supabase
    services = fetch_data("services")
    appointments = fetch_data("appointments")
    dynamic_pricing_results = fetch_data("dynamic_pricing")  # Fetch saved pricing results

    # Prepare historical data
    df = pd.DataFrame(appointments)
    df["ds"] = pd.to_datetime(df["start_time"]).dt.date
    df["y"] = 1  # Each appointment counts as one visit
    df = df.groupby("ds").size().reset_index(name="total_bookings")

    # Check if there are enough data points for the evaluation period
    if len(df) < evaluation_period:
        raise ValueError(f"Not enough data points for the evaluation period: {evaluation_period} days.")

    # Validation period
    validation_data = df.iloc[-evaluation_period:]  # Use the last `evaluation_period` days

    validation_results = []
    for _, row in validation_data.iterrows():
        date = row["ds"]
        actual_demand = row["total_bookings"]

        # Calculate total revenue for the date using dynamic pricing
        daily_revenue_dynamic = 0
        daily_revenue_static = 0

        for service in services:
            service_id = service["id"]
            base_price = service["price"]

            # Get the dynamic price for this service
            dynamic_price_entry = next(
                (res for res in dynamic_pricing_results if res["service_id"] == service_id),
                None
            )
            if not dynamic_price_entry:
                continue

            dynamic_price = dynamic_price_entry["dynamic_price"]

            # Estimate demand change due to dynamic pricing
            demand_change_factor = (
                1.1 if dynamic_price > base_price else
                0.9 if dynamic_price < base_price else
                1.0
            )
            predicted_demand = actual_demand * demand_change_factor

            # Calculate revenue
            daily_revenue_dynamic += float(predicted_demand * dynamic_price)
            daily_revenue_static += float(actual_demand * base_price)

        validation_results.append({
            "date": date.isoformat(),
            "actual_demand": int(actual_demand),
            "daily_revenue_static": round(daily_revenue_static, 2),
            "daily_revenue_dynamic": round(daily_revenue_dynamic, 2),
        })

    # Convert to DataFrame for analysis
    validation_df = pd.DataFrame(validation_results)

    # Calculate metrics
    static_revenue = validation_df["daily_revenue_static"].sum()
    dynamic_revenue = validation_df["daily_revenue_dynamic"].sum()
    revenue_improvement = ((dynamic_revenue - static_revenue) / static_revenue) * 100

    # Ensure JSON-serializable output
    return {
        "static_revenue": round(static_revenue, 2),
        "dynamic_revenue": round(dynamic_revenue, 2),
        "revenue_improvement (%)": round(revenue_improvement, 2)
    }