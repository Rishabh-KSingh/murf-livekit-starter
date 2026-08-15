import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
import requests
from livekit.agents import llm

from agent import FarmerTools, get_system_prompt, init_db


@pytest.mark.asyncio
async def test_weather_forecast_success():
    tools = FarmerTools()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "+28°C Sunny"

    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = await tools.get_weather_forecast("Pune")
        mock_get.assert_called_once_with("https://wttr.in/Pune?format=%t+%C", timeout=5)
        assert result == "SUCCESS: Aaj ka data: +28°C and Sunny in Pune."


@pytest.mark.asyncio
async def test_weather_forecast_failure_path_exception():
    tools = FarmerTools()

    with patch(
        "requests.get", side_effect=requests.RequestException("Connection timed out")
    ):
        result = await tools.get_weather_forecast("Nagpur")
        assert result == "ERROR: Weather API is currently down."


@pytest.mark.asyncio
async def test_weather_forecast_failure_path_status_error():
    tools = FarmerTools()
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"

    with patch("requests.get", return_value=mock_resp):
        result = await tools.get_weather_forecast("Nagpur")
        assert result == "ERROR: Weather API is currently down."


def test_farmer_tools_has_weather_tool():
    tools = FarmerTools()
    discovered = llm.find_function_tools(tools)
    tool_names = [
        getattr(t, "__name__", getattr(t.info, "name", str(t))) for t in discovered
    ]
    assert "get_weather_forecast" in tool_names
    assert "get_user_profile" in tool_names
    assert "save_user_profile" in tool_names


def test_system_prompt_requirements():
    prompt = get_system_prompt(
        user_id="user_123",
        existing_profile={
            "name": "Ramesh",
            "facts": {"district": "Nashik", "crop": "Onion"},
        },
    )

    # 1. Chaining instructions
    assert "get_weather_forecast" in prompt
    assert "WITHOUT asking them where they live again" in prompt
    assert "FIRST check if you already know their district" in prompt

    # 2. Recency instructions
    assert "आज का मौसम" in prompt

    # 3. Graceful failure instructions
    assert (
        "माफ़ कीजिएगा, अभी मौसम सर्वर से संपर्क नहीं हो पा रहा है। कृपया थोड़ी देर बाद पूछें।"
        in prompt
    )
    assert "Do not read out JSON or raw system logs" in prompt


@pytest.mark.asyncio
async def test_weather_tool_chaining_with_profile(tmp_path):
    test_db = str(tmp_path / "test_kisan.db")
    init_db(test_db)

    # Pre-populate user profile in SQLite with known district
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (user_id, name, language_preference, facts, last_interaction)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "user_999",
            "Suresh Patel",
            "Hindi",
            json.dumps({"district": "Indore", "crop": "Soybean"}),
            "2026-08-10 10:00:00",
        ),
    )
    conn.commit()
    conn.close()

    farmer_tools = FarmerTools(db_path=test_db, current_user_id="user_999")
    profile = await farmer_tools.get_user_profile("user_999")
    assert profile is not None
    assert profile["name"] == "Suresh Patel"
    district = profile["facts"]["district"]
    assert district == "Indore"

    # Now get weather forecast for that district
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "+25°C Moderate Rain"

    with patch("requests.get", return_value=mock_resp):
        weather = await farmer_tools.get_weather_forecast(district)
        assert weather == "SUCCESS: Aaj ka data: +25°C and Moderate Rain in Indore."
