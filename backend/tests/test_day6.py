from unittest.mock import AsyncMock, MagicMock, patch

import livekit.api as api
import pytest

from agent import (
    MANDATORY_OUTBOUND_OPENING,
    SYSTEM_PROMPT,
    RobustKisanLLM,
    get_system_prompt,
)
from trigger_outbound import normalize_sip_call_to, trigger_outbound_call


def test_normalize_sip_call_to():
    """Test normalization of SIP URIs and usernames for LiveKit SIP API."""
    assert (
        normalize_sip_call_to("sip:rishabh_kisan1@sip.linphone.org") == "rishabh_kisan1"
    )
    assert normalize_sip_call_to("rishabh_kisan1@sip.linphone.org") == "rishabh_kisan1"
    assert normalize_sip_call_to("rishabh_kisan1") == "rishabh_kisan1"
    assert normalize_sip_call_to("+919876543210") == "+919876543210"


def test_system_prompt_outbound_compliance():
    """Verify Day 6 Outbound Compliance rules and exact Hindi opening string."""
    assert "OUTBOUND CALL COMPLIANCE" in SYSTEM_PROMPT
    assert "CRITICAL RULE (Day 6 Step 4)" in SYSTEM_PROMPT
    assert MANDATORY_OUTBOUND_OPENING in SYSTEM_PROMPT
    assert (
        "Wait for the user to say 'Hello' or pick up, and then immediately deliver this exact opening line"
        in SYSTEM_PROMPT
    )
    assert (
        "If the user says 'Stop', politely confirm that their number has been removed from the list and end the conversation"
        in SYSTEM_PROMPT
    )

    # Exact expected opening Hindi string test
    expected_hindi_opening = (
        "नमस्ते, मैं आपका किसान मित्र AI बोल रहा हूँ। आपके इलाके में अगले 24 घंटों में भारी बारिश की चेतावनी है, "
        "इसलिए मैंने आपको यह अलर्ट देने के लिए कॉल किया है। अगर आप आगे से ऐसे कॉल नहीं चाहते हैं, "
        "तो कृपया 'स्टॉप' (Stop) कह दें।"
    )
    assert expected_hindi_opening == MANDATORY_OUTBOUND_OPENING
    assert expected_hindi_opening in SYSTEM_PROMPT

    # Check prompt generator with profile
    prompt_with_profile = get_system_prompt(
        user_id="user_test",
        existing_profile={
            "name": "Harish",
            "facts": {"district": "Nashik", "crop": "Grapes"},
        },
    )
    assert expected_hindi_opening in prompt_with_profile
    assert "Harish" in prompt_with_profile


def test_smart_fallback_outbound_greetings_and_opt_out():
    """Verify fallback responses for greetings and opt-out stop commands."""
    mock_llm = MagicMock()
    mock_llm.model = "mock"
    mock_llm.provider = "mock"
    robust = RobustKisanLLM(mock_llm)

    # Greeting fallback returns conversational response
    greeting_resp = robust._get_smart_fallback("Hello")
    assert "नमस्ते" in greeting_resp
    assert "ऋषभ" in greeting_resp

    namaste_resp = robust._get_smart_fallback("नमस्ते")
    assert "नमस्ते" in namaste_resp
    assert "ऋषभ" in namaste_resp

    # Stop fallback confirms opt-out and removal
    stop_resp = robust._get_smart_fallback("Stop")
    assert "हटा दिया गया है" in stop_resp

    stop_hindi_resp = robust._get_smart_fallback("स्टॉप")
    assert "हटा दिया गया है" in stop_hindi_resp


@pytest.mark.asyncio
async def test_trigger_outbound_call_sip_uri_success():
    """Test successful dispatch of an outbound SIP call using a SIP URI (Linphone) via LiveKitAPI."""
    sip_uri = "sip:farmer123@sip.linphone.org"
    mock_participant = api.SIPParticipantInfo(
        participant_id="PA_12345",
        participant_identity="sip_farmer123",
        room_name="kisan-outbound-alert",
    )

    mock_sip = MagicMock()
    mock_sip.create_sip_participant = AsyncMock(return_value=mock_participant)

    mock_lkapi_instance = MagicMock()
    mock_lkapi_instance.sip = mock_sip
    mock_lkapi_instance.__aenter__ = AsyncMock(return_value=mock_lkapi_instance)
    mock_lkapi_instance.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("livekit.api.LiveKitAPI", return_value=mock_lkapi_instance),
        patch.dict(
            "os.environ",
            {
                "LIVEKIT_URL": "wss://test.livekit.cloud",
                "LIVEKIT_API_KEY": "test_key",
                "LIVEKIT_API_SECRET": "test_secret",
            },
        ),
    ):
        result = await trigger_outbound_call(
            sip_trunk_id="ST_LINPHONE_TRUNK",
            destination_number=sip_uri,
            room_name="kisan-outbound-alert",
        )

        assert result is not None
        assert result.participant_id == "PA_12345"
        assert result.participant_identity == "sip_farmer123"
        mock_sip.create_sip_participant.assert_called_once()
        call_req = mock_sip.create_sip_participant.call_args[0][0]
        assert call_req.sip_trunk_id == "ST_LINPHONE_TRUNK"
        assert call_req.sip_call_to == "farmer123"
        assert call_req.room_name == "kisan-outbound-alert"


@pytest.mark.asyncio
async def test_trigger_outbound_call_missing_env():
    """Test trigger outbound call handles missing credentials gracefully."""
    with patch.dict("os.environ", {}, clear=True):
        result = await trigger_outbound_call(
            sip_trunk_id="ST_TEST",
            destination_number="sip:user@sip.linphone.org",
        )
        assert result is None


@pytest.mark.asyncio
async def test_trigger_outbound_call_api_error():
    """Test trigger outbound call handles LiveKit API error gracefully."""
    mock_sip = MagicMock()
    mock_sip.create_sip_participant = AsyncMock(
        side_effect=RuntimeError("SIP Trunk connection error")
    )

    mock_lkapi_instance = MagicMock()
    mock_lkapi_instance.sip = mock_sip
    mock_lkapi_instance.__aenter__ = AsyncMock(return_value=mock_lkapi_instance)
    mock_lkapi_instance.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("livekit.api.LiveKitAPI", return_value=mock_lkapi_instance),
        patch.dict(
            "os.environ",
            {
                "LIVEKIT_URL": "wss://test.livekit.cloud",
                "LIVEKIT_API_KEY": "test_key",
                "LIVEKIT_API_SECRET": "test_secret",
            },
        ),
    ):
        result = await trigger_outbound_call(
            sip_trunk_id="ST_FAIL_TRUNK",
            destination_number="sip:user@sip.linphone.org",
        )
        assert result is None
