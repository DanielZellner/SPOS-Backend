from fastapi import APIRouter, Query
from spos_service.services.monte_carlo import monte_carlo_simulation
from spos_service.services.pricing import calculate_dynamic_pricing_with_forecast
from spos_service.services.validate import dynamic_pricing_validate, monte_carlo_simulation_validate

router = APIRouter(
    prefix="/simulate",
    tags=["Simulation"]
)

@router.get("/monte-carlo")
async def calc_monte_carlo_simulation(simulation_runs: int = Query(1, description="Number of simulation runs to perform: 1 equals 140 runs"), max_weekly_hours: int = 180, min_weekly_hours: int = 140, open_days: int=None):
    result = monte_carlo_simulation(simulation_runs, max_weekly_hours=max_weekly_hours, min_weekly_hours=min_weekly_hours,open_days=open_days)
    return {"result": result}

@router.get("/dynamic-pricing")
async def dynamic_pricing():
    result = calculate_dynamic_pricing_with_forecast(forecast_days=7)
    return {"result": result}

@router.get("/monte-carlo-validate")
async def calc_monte_carlo_simulation_validate():
    result = monte_carlo_simulation_validate()
    return {"result": result}

@router.get("/dynamic-pricing-validate")
async def calc_dynamic_pricing_validate():
    result = dynamic_pricing_validate()
    return {"result": result}