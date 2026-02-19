import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gamification import Achievement, AchievementCondition

logger = logging.getLogger(__name__)

ACHIEVEMENTS = [
    # cards_learned
    {"condition_type": AchievementCondition.cards_learned, "condition_value": 10, "title": "First Steps", "description": "Learn your first 10 cards", "xp_reward": 50},
    {"condition_type": AchievementCondition.cards_learned, "condition_value": 50, "title": "Getting Serious", "description": "Learn 50 cards", "xp_reward": 100},
    {"condition_type": AchievementCondition.cards_learned, "condition_value": 100, "title": "Centurion", "description": "Learn 100 cards", "xp_reward": 200},
    {"condition_type": AchievementCondition.cards_learned, "condition_value": 500, "title": "Word Collector", "description": "Learn 500 cards", "xp_reward": 500},
    {"condition_type": AchievementCondition.cards_learned, "condition_value": 1000, "title": "Lexicon Master", "description": "Learn 1000 cards", "xp_reward": 1000},
    # streak_days
    {"condition_type": AchievementCondition.streak_days, "condition_value": 3, "title": "Three in a Row", "description": "Maintain a 3-day streak", "xp_reward": 30},
    {"condition_type": AchievementCondition.streak_days, "condition_value": 7, "title": "Week Warrior", "description": "Maintain a 7-day streak", "xp_reward": 75},
    {"condition_type": AchievementCondition.streak_days, "condition_value": 14, "title": "Two Weeks Strong", "description": "Maintain a 14-day streak", "xp_reward": 150},
    {"condition_type": AchievementCondition.streak_days, "condition_value": 30, "title": "Monthly Dedication", "description": "Maintain a 30-day streak", "xp_reward": 300},
    {"condition_type": AchievementCondition.streak_days, "condition_value": 100, "title": "Unstoppable", "description": "Maintain a 100-day streak", "xp_reward": 1000},
    # xp_earned
    {"condition_type": AchievementCondition.xp_earned, "condition_value": 100, "title": "First Hundred", "description": "Earn 100 XP", "xp_reward": 25},
    {"condition_type": AchievementCondition.xp_earned, "condition_value": 500, "title": "Rising Star", "description": "Earn 500 XP", "xp_reward": 50},
    {"condition_type": AchievementCondition.xp_earned, "condition_value": 1000, "title": "XP Hunter", "description": "Earn 1000 XP", "xp_reward": 100},
    {"condition_type": AchievementCondition.xp_earned, "condition_value": 5000, "title": "XP Veteran", "description": "Earn 5000 XP", "xp_reward": 250},
    {"condition_type": AchievementCondition.xp_earned, "condition_value": 10000, "title": "XP Legend", "description": "Earn 10000 XP", "xp_reward": 500},
    # sets_created
    {"condition_type": AchievementCondition.sets_created, "condition_value": 1, "title": "Set Builder", "description": "Create your first card set", "xp_reward": 25},
    {"condition_type": AchievementCondition.sets_created, "condition_value": 5, "title": "Collection Starter", "description": "Create 5 card sets", "xp_reward": 75},
    {"condition_type": AchievementCondition.sets_created, "condition_value": 10, "title": "Curator", "description": "Create 10 card sets", "xp_reward": 150},
    {"condition_type": AchievementCondition.sets_created, "condition_value": 25, "title": "Library Architect", "description": "Create 25 card sets", "xp_reward": 300},
    # perfect_reviews
    {"condition_type": AchievementCondition.perfect_reviews, "condition_value": 10, "title": "Sharp Mind", "description": "Get 10 correct reviews", "xp_reward": 50},
    {"condition_type": AchievementCondition.perfect_reviews, "condition_value": 50, "title": "Perfectionist", "description": "Get 50 correct reviews", "xp_reward": 150},
    {"condition_type": AchievementCondition.perfect_reviews, "condition_value": 100, "title": "Flawless", "description": "Get 100 correct reviews", "xp_reward": 300},
    # conversations
    {"condition_type": AchievementCondition.conversations, "condition_value": 1, "title": "First Chat", "description": "Complete your first AI conversation", "xp_reward": 50},
    {"condition_type": AchievementCondition.conversations, "condition_value": 5, "title": "Chatty", "description": "Complete 5 AI conversations", "xp_reward": 100},
    {"condition_type": AchievementCondition.conversations, "condition_value": 25, "title": "Conversation Pro", "description": "Complete 25 AI conversations", "xp_reward": 250},
    {"condition_type": AchievementCondition.conversations, "condition_value": 100, "title": "Social Butterfly", "description": "Complete 100 AI conversations", "xp_reward": 500},
    # friends_count
    {"condition_type": AchievementCondition.friends_count, "condition_value": 1, "title": "First Friend", "description": "Add your first friend", "xp_reward": 25},
    {"condition_type": AchievementCondition.friends_count, "condition_value": 5, "title": "Social Network", "description": "Add 5 friends", "xp_reward": 75},
    {"condition_type": AchievementCondition.friends_count, "condition_value": 10, "title": "Popular", "description": "Add 10 friends", "xp_reward": 150},
]


async def seed_achievements(db: AsyncSession) -> None:
    """Insert predefined achievements if they don't exist (idempotent)."""
    result = await db.execute(select(Achievement))
    existing = result.scalars().all()

    # Index by (condition_type, condition_value) for dedup
    existing_keys = {
        (a.condition_type, a.condition_value) for a in existing
    }

    added = 0
    for data in ACHIEVEMENTS:
        key = (data["condition_type"], data["condition_value"])
        if key not in existing_keys:
            achievement = Achievement(**data)
            db.add(achievement)
            added += 1

    if added > 0:
        await db.commit()
        logger.info("Seeded %d new achievements", added)
    else:
        logger.info("All achievements already seeded")
