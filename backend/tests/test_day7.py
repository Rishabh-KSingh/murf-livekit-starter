import re
from unittest.mock import MagicMock, patch

import pytest

from agent import (
    ESCALATION_DENIED_RESPONSE,
    ESCALATION_PERMISSION_GATE,
    SYSTEM_PROMPT,
    FarmerTools,
    RobustKisanLLM,
)


def test_system_prompt_day7_human_escalation_rules():
    """Verify Day 7 Human Escalation persona, self-resolve rule, triggers, permission gate, and dialogues."""
    # 1. Persona
    assert "KisanMitra AI" in SYSTEM_PROMPT
    assert "किसान मित्र AI" in SYSTEM_PROMPT

    # 2. Self-Resolve First Rule
    assert "SELF-RESOLVE FIRST RULE" in SYSTEM_PROMPT

    # 3. Escalation Triggers
    assert "HUMAN ESCALATION & PERMISSION GATE (Day 7)" in SYSTEM_PROMPT
    assert "severe crop disease" in SYSTEM_PROMPT
    assert "mandi prices that are missing" in SYSTEM_PROMPT

    # 4. Exact Permission Gate Dialogue
    expected_gate = (
        "किसान भाई, आपकी फसल की यह समस्या थोड़ी गंभीर लग रही है। अगर आप कहें, तो क्या मैं आपकी यह परेशानी "
        "हमारे सीनियर कृषि विशेषज्ञ (Agriculture Expert) तक पहुँचा दूँ? वो आपको इसका एकदम पक्का इलाज बता पाएंगे।"
    )
    assert expected_gate == ESCALATION_PERMISSION_GATE
    assert expected_gate in SYSTEM_PROMPT

    # 5. Exact Post-Escalation Success Dialogue
    assert "जी धन्यवाद! मैंने आपकी परेशानी हमारी एक्सपर्ट टीम को भेज दी है" in SYSTEM_PROMPT
    assert "आपका शिकायत नंबर (Reference ID)" in SYSTEM_PROMPT

    # 6. Permission Denied Dialogue
    expected_denied = "कोई बात नहीं जी। मैं अपनी तरफ से आपको कुछ सामान्य सुझाव दे देता हूँ..."
    assert expected_denied == ESCALATION_DENIED_RESPONSE
    assert expected_denied in SYSTEM_PROMPT


def test_smart_fallback_self_resolve_vs_escalation():
    """Verify AI directly resolves routine queries and ONLY triggers permission gate for emergencies."""
    mock_llm = MagicMock()
    mock_llm.model = "mock"
    mock_llm.provider = "mock"
    robust = RobustKisanLLM(mock_llm)

    # Path A: Normal everyday farming queries — AI solves directly without escalation
    routine_crop_resp = robust._get_smart_fallback(
        "Tamatar me patte pile ho rahe hain kya karun"
    )
    assert ESCALATION_PERMISSION_GATE not in routine_crop_resp
    assert "NPK" in routine_crop_resp or "छिड़काव" in routine_crop_resp

    routine_fertilizer_resp = robust._get_smart_fallback(
        "Dhan me khad kab dalni chahiye"
    )
    assert ESCALATION_PERMISSION_GATE not in routine_fertilizer_resp
    assert "डीएपी" in routine_fertilizer_resp or "यूरिया" in routine_fertilizer_resp

    # Path B: Emergency catastrophic issue — Triggers Permission Gate
    severe_resp = robust._get_smart_fallback(
        "Kisan bhai meri puri fasal barbad ho gayi hai bhayankar kida lag gaya"
    )
    assert severe_resp == ESCALATION_PERMISSION_GATE

    # Path B (Cont): Permission Denied
    denied_resp = robust._get_smart_fallback("Nahi mat bhejo expert ko")
    assert "कोई बात नहीं जी। मैं अपनी तरफ से आपको कुछ सामान्य सुझाव दे देता हूँ" in denied_resp

    # Path B (Cont): Permission Agreed
    agreed_resp = robust._get_smart_fallback("Haan expert ko bhej do")
    assert "जी धन्यवाद! मैंने आपकी परेशानी हमारी एक्सपर्ट टीम को भेज दी है" in agreed_resp
    assert "शिकायत नंबर (Reference ID)" in agreed_resp


@pytest.mark.asyncio
async def test_create_escalation_tool_success():
    """Test create_escalation tool generating KISAN-XXX ID and posting payload to Discord."""
    tools = FarmerTools()
    tools.current_user_id = "sip_rishabh_kisan1"

    with patch("agent.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        with patch.dict(
            "os.environ",
            {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test/123"},
        ):
            result = await tools.create_escalation(
                summary="Severe blight destroying tomato crops in Sheikhpura",
                urgency="High",
                language="Hindi",
            )

            assert result["status"] == "success"
            assert "reference_id" in result
            ref_id = result["reference_id"]
            assert re.match(r"^KISAN-\d{3}$", ref_id)

            # Verify Discord POST call and payload structure
            mock_post.assert_called_once()
            call_args, call_kwargs = mock_post.call_args
            assert call_args[0] == "https://discord.com/api/webhooks/test/123"

            payload = call_kwargs["json"]
            assert "embeds" in payload
            embed = payload["embeds"][0]
            field_names = [f["name"] for f in embed["fields"]]
            assert "👤 Who needs help" in field_names
            assert "⚡ Urgency" in field_names
            assert "🗣️ Language" in field_names
            assert "🌾 What was checked" in field_names
            assert "📝 What happened" in field_names
            assert "🎫 Reference ID" in field_names


@pytest.mark.asyncio
async def test_create_escalation_sanitizes_sensitive_data():
    """Verify that private data (passwords, bank accounts, OTPs) is redacted from summary."""
    tools = FarmerTools()
    tools.current_user_id = "user_123"

    with patch("agent.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with patch.dict(
            "os.environ",
            {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test/123"},
        ):
            raw_summary = (
                "Fasal kharab hai, account 1234567890123456 and password:"
                " secretPass123 OTP is 987654"
            )
            result = await tools.create_escalation(
                summary=raw_summary,
                urgency="Critical",
                language="Hindi",
            )

            clean_happened = result["what_happened"]
            assert "1234567890123456" not in clean_happened
            assert "secretPass123" not in clean_happened
            assert "[REDACTED_NUMBER]" in clean_happened
            assert "[REDACTED_SENSITIVE]" in clean_happened
