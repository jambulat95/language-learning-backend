import json
import logging

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI

from app.config import settings
from app.schemas.ai import GeneratedCardItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert language teacher creating flashcards for English learners.

Generate exactly {count} flashcards on the topic "{topic}" for a student at CEFR level {level}.

Level guidelines:
- A1: Basic everyday words and simple phrases
- A2: Common expressions, simple sentences, routine topics
- B1: Intermediate vocabulary, opinions, experiences
- B2: Abstract topics, idiomatic expressions, nuanced vocabulary
- C1: Advanced idioms, academic/professional language, subtle distinctions
- C2: Rare words, literary expressions, native-level nuance

{interests_section}

Each card must have:
- "front_text": the English word or phrase (max 500 chars)
- "back_text": the translation/explanation in {native_language} (max 500 chars)
- "example_sentence": a natural example sentence using the word/phrase (optional but recommended)

Return ONLY a JSON array of objects, no extra text. Example:
[
  {{"front_text": "to commute", "back_text": "ездить на работу/учёбу", "example_sentence": "I commute to work by train every day."}}
]
"""


def _build_llm() -> ChatMistralAI:
    return ChatMistralAI(
        model=settings.MISTRAL_MODEL,
        api_key=settings.MISTRAL_API_KEY,
        temperature=settings.AI_GENERATION_TEMPERATURE,
    )


def _build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Generate {count} flashcards about \"{topic}\" for level {level}."),
    ])


async def generate_cards(
    topic: str,
    level: str,
    count: int,
    interests: list[str],
    native_language: str = "Russian",
) -> list[GeneratedCardItem]:
    interests_section = ""
    if interests:
        interests_section = (
            "The student is interested in: "
            + ", ".join(interests)
            + ". Try to relate cards to these interests when relevant."
        )

    llm = _build_llm()
    prompt = _build_prompt()
    parser = JsonOutputParser()

    chain = prompt | llm | parser

    logger.info("Generating %d cards for topic=%s, level=%s", count, topic, level)

    result = await chain.ainvoke({
        "topic": topic,
        "level": level,
        "count": count,
        "interests_section": interests_section,
        "native_language": native_language,
    })

    cards = [GeneratedCardItem(**item) for item in result]

    # Trim to requested count in case LLM returns more
    return cards[:count]
