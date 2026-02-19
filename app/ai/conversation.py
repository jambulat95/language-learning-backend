import json
import logging
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI

from app.ai.scenarios import ScenarioConfig
from app.config import settings

logger = logging.getLogger(__name__)

LEVEL_GUIDELINES = {
    "A1": "Use very simple words and short sentences. Avoid idioms. Speak slowly and clearly.",
    "A2": "Use common everyday expressions and simple sentences. Keep vocabulary basic.",
    "B1": "Use intermediate vocabulary. You can use some common idioms. Explain complex words if needed.",
    "B2": "Use natural language with some idiomatic expressions. Don't oversimplify.",
    "C1": "Use advanced vocabulary, idioms, and complex sentences naturally.",
    "C2": "Use sophisticated, native-level language including rare expressions and nuance.",
}

MAX_CONTEXT_MESSAGES = 20


def _build_conversation_llm() -> ChatMistralAI:
    return ChatMistralAI(
        model=settings.MISTRAL_MODEL,
        api_key=settings.MISTRAL_API_KEY,
        temperature=settings.AI_CONVERSATION_TEMPERATURE,
        max_tokens=settings.AI_CONVERSATION_MAX_TOKENS,
    )


def _build_grammar_llm() -> ChatMistralAI:
    return ChatMistralAI(
        model=settings.MISTRAL_MODEL,
        api_key=settings.MISTRAL_API_KEY,
        temperature=settings.AI_GRAMMAR_CHECK_TEMPERATURE,
    )


def _build_system_message(scenario: ScenarioConfig, level: str) -> str:
    level_guide = LEVEL_GUIDELINES.get(level, LEVEL_GUIDELINES["B1"])
    return (
        f"{scenario.system_context}\n\n"
        f"Your role: {scenario.ai_role}\n\n"
        f"Language guidelines for the student (CEFR level {level}):\n"
        f"{level_guide}\n\n"
        "Stay in character throughout the conversation. "
        "Keep your replies concise (2-4 sentences typically). "
        "Ask follow-up questions to keep the conversation going. "
        "Do NOT correct the user's grammar — a separate system handles that."
    )


def _build_langchain_messages(
    system_prompt: str,
    messages: list[dict],
) -> list[SystemMessage | HumanMessage | AIMessage]:
    lc_messages: list[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=system_prompt),
    ]

    # Truncate to last N messages for context window management
    recent = messages[-MAX_CONTEXT_MESSAGES:] if len(messages) > MAX_CONTEXT_MESSAGES else messages

    for msg in recent:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))

    return lc_messages


async def generate_conversation_reply_stream(
    scenario: ScenarioConfig,
    messages: list[dict],
    level: str,
) -> AsyncIterator[str]:
    """Stream AI conversation reply as text chunks."""
    llm = _build_conversation_llm()
    system_prompt = _build_system_message(scenario, level)
    lc_messages = _build_langchain_messages(system_prompt, messages)

    async for chunk in llm.astream(lc_messages):
        if chunk.content:
            yield chunk.content


GRAMMAR_CHECK_PROMPT = """\
You are a grammar checker for English language learners at CEFR level {level}.
Their native language is {native_language}.

Analyze the following message the student sent during a conversation:

Student's message: "{user_message}"
Context (AI's previous message): "{last_ai_message}"

Find grammar, spelling, and word choice errors. For each error provide:
- "original": the incorrect text
- "corrected": the corrected version
- "explanation": brief explanation in {native_language}

Also provide 1-3 short suggestions for alternative phrasings or vocabulary the student could have used, in English.

Return ONLY valid JSON in this exact format:
{{"corrections": [{{"original": "...", "corrected": "...", "explanation": "..."}}], "suggestions": ["..."]}}

If there are no errors, return: {{"corrections": [], "suggestions": []}}
"""


async def check_grammar(
    user_message: str,
    last_ai_message: str,
    level: str,
    native_language: str,
) -> tuple[list[dict], list[str]]:
    """Check grammar and return (corrections, suggestions). Gracefully returns empty on error."""
    try:
        llm = _build_grammar_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", GRAMMAR_CHECK_PROMPT),
        ])
        parser = JsonOutputParser()
        chain = prompt | llm | parser

        result = await chain.ainvoke({
            "level": level,
            "native_language": native_language,
            "user_message": user_message,
            "last_ai_message": last_ai_message or "",
        })

        corrections = result.get("corrections", [])
        suggestions = result.get("suggestions", [])
        return corrections, suggestions
    except Exception:
        logger.exception("Grammar check failed, returning empty corrections")
        return [], []


FEEDBACK_PROMPT = """\
You are an English language teacher evaluating a conversation practice session.
The student is at CEFR level {level} and their native language is {native_language}.

Here is the full conversation:
{conversation_text}

Grammar errors found during the conversation:
{errors_summary}

Provide a comprehensive feedback summary in JSON format:
{{
    "total_errors": <number>,
    "common_error_types": ["list of recurring error categories, e.g. article usage, verb tense"],
    "strengths": ["what the student did well, in {native_language}"],
    "areas_to_improve": ["what the student should work on, in {native_language}"],
    "overall_assessment": "A brief overall assessment paragraph in {native_language}"
}}

Return ONLY valid JSON, no extra text.
"""


async def generate_conversation_feedback(
    messages: list[dict],
    level: str,
    native_language: str,
) -> dict:
    """Generate end-of-conversation feedback."""
    try:
        # Build conversation text
        conversation_lines = []
        errors_summary_parts = []
        total_errors = 0

        for msg in messages:
            role_label = "Student" if msg["role"] == "user" else "AI"
            conversation_lines.append(f"{role_label}: {msg['content']}")

            corrections = msg.get("corrections")
            if corrections:
                total_errors += len(corrections)
                for c in corrections:
                    errors_summary_parts.append(
                        f"- \"{c['original']}\" → \"{c['corrected']}\" ({c.get('explanation', '')})"
                    )

        conversation_text = "\n".join(conversation_lines)
        errors_summary = "\n".join(errors_summary_parts) if errors_summary_parts else "No errors found."

        llm = _build_grammar_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", FEEDBACK_PROMPT),
        ])
        parser = JsonOutputParser()
        chain = prompt | llm | parser

        result = await chain.ainvoke({
            "level": level,
            "native_language": native_language,
            "conversation_text": conversation_text,
            "errors_summary": errors_summary,
        })

        result["total_errors"] = total_errors
        return result
    except Exception:
        logger.exception("Feedback generation failed, returning basic feedback")
        return {
            "total_errors": 0,
            "common_error_types": [],
            "strengths": [],
            "areas_to_improve": [],
            "overall_assessment": "Feedback generation failed. Please try again.",
        }
