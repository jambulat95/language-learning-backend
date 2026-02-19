from app.models.gamification import League

# XP rewards per action
XP_REVIEW_BASE: int = 10
XP_REVIEW_BONUS: dict[str, int] = {
    "again": 0,
    "hard": 5,
    "good": 10,
    "easy": 15,
}
XP_SET_CREATED: int = 20
XP_AI_GENERATION: int = 30
XP_CONVERSATION: int = 25
XP_FRIEND_ADDED: int = 10

# Level thresholds — index is the level number (0-indexed, level 1 = index 0)
LEVEL_THRESHOLDS: list[int] = [
    0,      # Level 1
    100,    # Level 2
    250,    # Level 3
    500,    # Level 4
    1000,   # Level 5
    1750,   # Level 6
    2750,   # Level 7
    4000,   # Level 8
    5500,   # Level 9
    7500,   # Level 10
]
LEVEL_INCREMENT_AFTER_10: int = 2500

# League XP thresholds
LEAGUE_THRESHOLDS: list[tuple[int, League]] = [
    (50000, League.Diamond),
    (15000, League.Platinum),
    (5000, League.Gold),
    (1000, League.Silver),
    (0, League.Bronze),
]
