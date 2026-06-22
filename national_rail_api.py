import asyncio
import requests
from typing import Dict, Any, List, Union

async def get_raw_train_services(api_token: str, user_agent_str: str, origin: str, destination: str) -> Dict[str, Any]:
    """Fetches raw train services from the National Rail API."""
    if not api_token:
        return {"error": "National Rail API token is missing."}

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
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return {"error": "Authentication failed. Please check your API token.", "status_code": 401}
        return {"error": f"Problem reaching the schedule service (HTTP {e.response.status_code}).", "status_code": e.response.status_code}
    except requests.exceptions.RequestException:
        return {"error": "Could not connect to the train schedule service."}
    except Exception:
        return {"error": "An unexpected error occurred while fetching the schedule."}

async def fetch_train_schedule(api_token: str, user_agent_str: str, origin: str, destination: str) -> str:
    """Fetches the schedule (trains & replacement buses) and returns a formatted string for the Telegram bot."""
    import re
    data = await get_raw_train_services(api_token, user_agent_str, origin, destination)

    if "error" in data:
        return f"Sorry, {data['error']}"

    raw_trains = data.get("trainServices") or []
    raw_buses = data.get("busServices") or []

    trains = [{**s, "service_type": "train"} for s in raw_trains]
    buses = [{**s, "service_type": "bus"} for s in raw_buses]
    all_services = trains + buses

    if not all_services:
        return f"No direct services found from {origin} to {destination} at this time."

    # Sort chronologically by std
    all_services.sort(key=lambda s: s.get("std", ""))

    has_trains = len(trains) > 0
    has_buses = len(buses) > 0

    if has_trains and has_buses:
        title = f"Services from {origin} to {destination}:\n"
    elif has_buses:
        title = f"🚌 Replacement Buses from {origin} to {destination}:\n"
    else:
        title = f"🚆 Trains from {origin} to {destination}:\n"

    schedule_lines = [title]
    for service in all_services[:10]:
        std = service.get("std")
        etd = service.get("etd")
        platform = service.get("platform", "TBA")
        operator = service.get("operator")
        is_cancelled = service.get("isCancelled", False)
        service_type = service.get("service_type")

        emoji = "🚌" if service_type == "bus" else "🚆"

        status = f"{std} -> {etd}"
        if etd and etd.lower() != 'on time':
            status = f"{std} (exp. {etd})"
        if is_cancelled:
            status = f"{std} - CANCELLED"

        schedule_lines.append(
            f"{emoji} {status}, Plat: {platform}, Op: {operator}"
        )

    # Format NRCC notices/engineering work details
    nrcc_messages = data.get("nrccMessages") or []
    notices = []
    for msg in nrcc_messages:
        html = msg.get("Value") or ""
        if html:
            text = re.sub(r'<[^>]*>', '', html)
            text = re.sub(r'\s+', ' ', text).strip()
            text = re.sub(r'More details are available.*', '', text, flags=re.IGNORECASE).strip()
            if text:
                notices.append(text)

    if notices:
        schedule_lines.append("\n⚠️ Service Notices:")
        for notice in notices:
            schedule_lines.append(f"• {notice}")

    return "\n".join(schedule_lines)
