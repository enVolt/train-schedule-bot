import os
from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv
from national_rail_api import get_raw_train_services

# Load environment variables
load_dotenv()

NATIONAL_RAIL_API_TOKEN = os.getenv("NATIONAL_RAIL_API_TOKEN")
USER_AGENT = os.getenv("USER_AGENT", "train-bot-app/0.0.1")

app = FastAPI(title="Train Schedule API")

@app.get("/api/schedule")
async def get_schedule(
    origin: str = Query(..., min_length=3, max_length=3, description="3-letter CRS code for origin"),
    destination: str = Query(..., min_length=3, max_length=3, description="3-letter CRS code for destination")
):
    """
    Fetches the train schedule between two stations.
    """
    origin = origin.upper()
    destination = destination.upper()

    data = await get_raw_train_services(NATIONAL_RAIL_API_TOKEN, USER_AGENT, origin, destination)

    if "error" in data:
        status_code = data.get("status_code", 500)
        raise HTTPException(status_code=status_code, detail=data["error"])

    return data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
