import numpy as np
from spos_service.utils.supabase_client import fetch_data, insert_data, fetch_with_date_range, delete_data
from datetime import datetime
from prophet import Prophet
import pandas as pd

def calculate_dynamic_pricing_with_forecast(forecast_days=1):
    """
    Calculate dynamic pricing using Prophet for forecasting and save results.

    Args:
        adjustment_factor (float): Maximum adjustment factor (default ±10%).
        forecast_days (int): Number of days to forecast.

    Returns:
        list: List of inserted dynamic pricing records.
    """
    # Fetch services
    services = fetch_data("services")
    for service in services:
        delete_data("dynamic_pricing", {"service_id": service["id"]})

    # Fetch appointments for the current month using the updated function
    current_date = datetime.now()
    start_of_month = current_date.replace(day=1).strftime("%Y-%m-%d")
    end_of_month = current_date.replace(day=31).strftime("%Y-%m-%d")

    appointments = fetch_with_date_range(
        "appointments", start_date=start_of_month, end_date=end_of_month
    )

    # Prepare data for Prophet
    booking_data = []
    for appointment in appointments:
        service_ids = appointment["service_ids"]
        date = appointment["start_time"][:10]
        for service_id in service_ids:
            booking_data.append({"service_id": service_id, "date": date})

    df_bookings = pd.DataFrame(booking_data)
    results = []

    for service in services:
        service_id = service["id"]
        service_name = service["name"]
        base_price = service["price"]
        business_id = service["business_id"]

        service_bookings = df_bookings[df_bookings["service_id"] == service_id]
        if service_bookings.empty:
            continue

        service_counts = service_bookings.groupby("date").size().reset_index(name="y")
        service_counts.rename(columns={"date": "ds"}, inplace=True)

        if len(service_counts) < 3:  # Ensure sufficient data for Prophet
            continue

        service_counts["ds"] = pd.to_datetime(service_counts["ds"])
        service_counts = service_counts.set_index("ds").resample("W").sum().reset_index()

        model = Prophet(interval_width=0.8)
        model.fit(service_counts)

        future = model.make_future_dataframe(periods=forecast_days)
        forecast = model.predict(future)

        forecasted_demand = forecast.iloc[-forecast_days:]["yhat"].mean()
        average_demand = service_counts["y"].mean()

        #if average_demand == 0:
        #    popularity_score = 0  # No demand results in a minimum score
        #else:
        #    # Scale popularity score between 0 and 100
        #    popularity_score = 50 + 50 * (forecasted_demand - average_demand) / average_demand
        #    popularity_score = min(max(popularity_score, 0), 100)  # Clamp between 0 and 100
        popularity_score = calculate_score(forecasted_demand, average_demand)

        # Calculate dynamic price based on the popularity score
        if popularity_score < 40:
            dynamic_price = base_price * 0.9  # Decrease price by 10%
        elif 33 <= popularity_score <= 66:
            dynamic_price = base_price  # Keep price the same
        else:
            dynamic_price = base_price * 1.1  # Increase price by 10%

        dynamic_price = round(dynamic_price, 2)
        price_change = round(dynamic_price - base_price, 2)

        print(f"Service: {service_name}, Base: {base_price}, Forecast: {forecasted_demand}, Avg: {average_demand}, Score: {popularity_score}, Dynamic: {dynamic_price}")

        # Save the results, including forecasted_demand and popularity_score
        result = {
            "service_id": service_id,
            "service_name": service_name,
            "base_price": base_price,
            "dynamic_price": dynamic_price,
            "popularity_score": round(popularity_score, 0),
            "price_change": price_change,
            "business_id": business_id,
            "forecasted_demand": round(forecasted_demand, 0),
        }
        insert_data("dynamic_pricing", result)
        results.append(result)

    return results

def calculate_score(forecasted_demand, average_demand):
    # Verhältnis berechnen
    ratio = forecasted_demand / average_demand if average_demand != 0 else 1
    
    # Logarithmische Transformation, um asymptotische Grenzen zu gewährleisten
    score = 50 + 50 * np.tanh((ratio - 1) * 2)
    
    # Gewährleisten, dass der Score zwischen 0 und 100 liegt
    return max(0, min(100, score))