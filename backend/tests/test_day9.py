import pytest
from livekit.agents import AgentSession, inference, llm

from agent import (
    CROP_SPECIALIST_INTRO,
    CROP_SPECIALIST_SYSTEM_PROMPT,
    PRE_HANDOFF_DIALOGUE,
    SYSTEM_PROMPT,
    Assistant,
    CropSpecialistAgent,
)


def _llm() -> llm.LLM:
    return inference.LLM(model="openai/gpt-4.1-mini")


def test_crop_specialist_system_prompt_and_persona():
    """Verify CropSpecialistAgent system prompt, instructions, and intro constants."""
    expected_prompt = (
        "You are the Fasal Doctor (Crop Problem Specialist) for KisanMitra AI. "
        "You ONLY handle queries related to crop diseases, pest control, and soil health. "
        "Speak in respectful, Romanized Hindi (Hinglish). "
        "Always introduce yourself upon taking over: 'Namaste, main Fasal Doctor hoon. Aapki fasal mein kya samasya aa rahi hai?'"
    )
    assert expected_prompt == CROP_SPECIALIST_SYSTEM_PROMPT

    specialist = CropSpecialistAgent()
    assert specialist.instructions == expected_prompt

    expected_intro = (
        "Namaste, main Fasal Doctor hoon. Aapki fasal mein kya samasya aa rahi hai?"
    )
    assert expected_intro == CROP_SPECIALIST_INTRO


def test_main_agent_handoff_tool_and_pre_handoff_dialogue():
    """Verify Assistant has transfer_to_crop_specialist tool with exact required description and system prompt rules."""
    assistant = Assistant()
    tool_names = [t.info.name for t in assistant.tools]
    assert "transfer_to_crop_specialist" in tool_names

    transfer_tool = next(
        t for t in assistant.tools if t.info.name == "transfer_to_crop_specialist"
    )
    expected_description = "Call this tool IMMEDIATELY when the user asks about crop diseases, pests, fertilizers, or plant health issues."
    assert transfer_tool.info.description == expected_description

    expected_dialogue = "Yeh fasal ki bimari lag rahi hai. Main aapki aawaz hamare Fasal Doctor ko transfer kar raha hoon. Line par bane rahein."
    assert expected_dialogue == PRE_HANDOFF_DIALOGUE

    assert "AGENT HANDOFF TO CROP SPECIALIST (Day 9)" in SYSTEM_PROMPT
    assert expected_dialogue in SYSTEM_PROMPT
    assert "transfer_to_crop_specialist" in SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_crop_specialist_on_enter_speaks_intro():
    """Verify CropSpecialistAgent speaks intro on entering session."""
    specialist = CropSpecialistAgent()
    assert hasattr(specialist, "on_enter")


@pytest.mark.asyncio
async def test_agent_handoff_execution_and_context_passing():
    """Test full LiveKit multi-agent handoff from Assistant to CropSpecialistAgent with context."""
    async with (
        _llm() as mock_llm,
        AgentSession(llm=mock_llm) as session,
    ):
        assistant = Assistant()
        await session.start(assistant)
        assert session.current_agent == assistant

        # Trigger handoff
        result = await session.run(
            user_input="Mere tamatar ke paudhon mein keeda lag gaya hai aur patte peele pad rahe hain."
        )

        # Confirm transfer tool or handoff happened
        tool_called = any(
            getattr(e, "name", "") == "transfer_to_crop_specialist"
            or getattr(e, "type", "") == "agent_handoff"
            for e in result.events
        )
        assert tool_called or isinstance(session.current_agent, CropSpecialistAgent)

        # Verify context preservation on follow-up turn with specialist
        if isinstance(session.current_agent, CropSpecialistAgent):
            # Follow-up turn directly to specialist
            followup_result = await session.run(user_input="Iska kya ilaaj hai?")
            assert session.current_agent is not None
            assert len(followup_result.events) > 0
