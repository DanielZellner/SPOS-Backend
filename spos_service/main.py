from fastapi import FastAPI
from spos_service.routers import simulation
app = FastAPI()

# Router registrieren
app.include_router(simulation.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the SPOS API"}

