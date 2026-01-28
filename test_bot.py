import pytest
from unittest.mock import AsyncMock, patch
import json
import requests
from bot import fetch_train_schedule

# Mock the os.getenv call for the API token
@pytest.fixture(autouse=True)
def mock_env_vars():
    with patch('os.getenv', return_value='test_api_token'):
        yield

# Helper to create a mock response object
def create_mock_response(json_data, status_code=200):
    mock_response = AsyncMock(spec=requests.Response)
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data
    mock_response.raise_for_status.return_value = None
    # For HTTPError, we need to make sure the response is accessible
    mock_response.response = mock_response
    return mock_response

@pytest.mark.asyncio
async def test_fetch_train_schedule_on_time():
    mock_api_response = {
        "trainServices": [
            {
                "std": "10:00",
                "etd": "On time",
                "platform": "1",
                "operator": "Northern",
                "isCancelled": False
            }
        ]
    }
    with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = create_mock_response(mock_api_response)
        result = await fetch_train_schedule("MAN", "LDS")
        assert "Trains from MAN to LDS:" in result
        assert "- 10:00 -> On time, Plat: 1, Op: Northern" in result
        assert "DELAYED" not in result

@pytest.mark.asyncio
async def test_fetch_train_schedule_small_delay():
    mock_api_response = {
        "trainServices": [
            {
                "std": "10:00",
                "etd": "10:05",
                "platform": "2",
                "operator": "TransPennine Express",
                "isCancelled": False
            }
        ]
    }
    with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = create_mock_response(mock_api_response)
        result = await fetch_train_schedule("MAN", "LDS")
        assert "Trains from MAN to LDS:" in result
        assert "- 10:00 (exp. 10:05), Plat: 2, Op: TransPennine Express" in result
        assert "DELAYED" not in result

@pytest.mark.asyncio
async def test_fetch_train_schedule_cancelled():
    mock_api_response = {
        "trainServices": [
            {
                "std": "11:00",
                "etd": "Cancelled",
                "platform": "4",
                "operator": "CrossCountry",
                "isCancelled": True
            }
        ]
    }
    with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = create_mock_response(mock_api_response)
        result = await fetch_train_schedule("MAN", "LDS")
        assert "Trains from MAN to LDS:" in result
        assert "- 11:00 - CANCELLED, Plat: 4, Op: CrossCountry" in result
        assert "DELAYED" not in result # Should not show delayed if cancelled

@pytest.mark.asyncio
async def test_fetch_train_schedule_no_services():
    mock_api_response = {
        "trainServices": []
    }
    with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = create_mock_response(mock_api_response)
        result = await fetch_train_schedule("MAN", "LDS")
        assert "No direct services found from MAN to LDS at this time." in result

@pytest.mark.asyncio
async def test_fetch_train_schedule_api_error():
    with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.side_effect = requests.exceptions.RequestException("Connection error")
        result = await fetch_train_schedule("MAN", "LDS")
        assert "Sorry, I couldn't connect to the train schedule service." in result

@pytest.mark.asyncio
async def test_fetch_train_schedule_http_error():
    mock_response = create_mock_response({}, status_code=403)
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
    with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = mock_response
        result = await fetch_train_schedule("MAN", "LDS")
        assert "Sorry, there was a problem reaching the schedule service (HTTP 403)." in result
