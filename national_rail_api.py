import asyncio
import requests

async def fetch_train_schedule(api_token: str, user_agent_str: str, origin: str, destination: str) -> str:
    """Fetches the train schedule from the National Rail API using the official REST endpoint."""
    if not api_token:
        return "National Rail API token is missing."

    url = f"https://api1.raildata.org.uk/1010-live-departure-board-dep1_2/LDBWS/api/20220120/GetDepBoardWithDetails/{origin}"
    params = {
        "filterCrs": destination,
        "filterType": "to",
        "numRows": 10,
        "timeWindow": 120,
    }
    headers = {
        "x-apikey": api_token,
        'user-agent': user_agent_str
    }

    try:
        response = await asyncio.to_thread(requests.get, url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data or not data.get("trainServices"):
            return f"No direct services found from {origin} to {destination} at this time."

        schedule_lines = [f"Trains from {origin} to {destination}:\n"]
        for service in data["trainServices"]:
            std = service.get("std")
            etd = service.get("etd")
            platform = service.get("platform", "TBA")
            operator = service.get("operator")
            is_cancelled = service.get("isCancelled", False)

            status = f"{std} -> {etd}"
            if etd and etd.lower() != 'on time':
                status = f"{std} (exp. {etd})"
            if is_cancelled:
                status = f"{std} - CANCELLED"

            schedule_lines.append(
                f"- {status}, Plat: {platform}, Op: {operator}"
            )
        
        return "\n".join(schedule_lines)

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return "Authentication failed. Please check your API token."
        return f"Sorry, there was a problem reaching the schedule service (HTTP {e.response.status_code})."
    except requests.exceptions.RequestException as e:
        return "Sorry, I couldn't connect to the train schedule service."
    except Exception as e:
        return "An unexpected error occurred while fetching the schedule."
