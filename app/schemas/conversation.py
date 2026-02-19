import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.ai.scenarios import ScenarioType


# --- Subdocument schemas (for JSONB) ---

class GrammarCorrection(BaseModel):
    original: str
    corrected: str
    explanation: str


class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime
    corrections: list[GrammarCorrection] | None = None
    suggestions: list[str] | None = None


# --- Request schemas ---

class StartConversationRequest(BaseModel):
    scenario: ScenarioType


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


# --- Response schemas ---

class ConversationStartResponse(BaseModel):
    conversation_id: uuid.UUID
    scenario: ScenarioType
    scenario_title: str
    ai_message: str
    suggestions: list[str]


class ConversationFeedback(BaseModel):
    total_turns: int
    total_errors: int
    common_error_types: list[str]
    strengths: list[str]
    areas_to_improve: list[str]
    overall_assessment: str
    xp_earned: int


class ConversationEndResponse(BaseModel):
    conversation_id: uuid.UUID
    feedback: ConversationFeedback


class ConversationSummary(BaseModel):
    id: uuid.UUID
    scenario: str
    scenario_title: str
    started_at: datetime
    ended_at: datetime | None
    total_turns: int
    is_active: bool


class ConversationDetailResponse(BaseModel):
    id: uuid.UUID
    scenario: str
    scenario_title: str
    started_at: datetime
    ended_at: datetime | None
    total_turns: int
    messages: list[ConversationMessage]
    feedback: ConversationFeedback | None


class ScenarioListItem(BaseModel):
    type: ScenarioType
    title: str
    description: str
    suggested_turns: int


class WeeklyDialogueStatus(BaseModel):
    used: int
    limit: int
    is_premium: bool
