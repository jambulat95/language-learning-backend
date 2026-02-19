import enum

from pydantic import BaseModel


class ScenarioType(str, enum.Enum):
    airport = "airport"
    restaurant = "restaurant"
    job_interview = "job_interview"
    hotel_checkin = "hotel_checkin"
    shopping = "shopping"
    doctor_visit = "doctor_visit"
    small_talk = "small_talk"
    business_meeting = "business_meeting"
    free_conversation = "free_conversation"


class ScenarioConfig(BaseModel):
    type: ScenarioType
    title: str
    description: str
    ai_role: str
    opening_message: str
    system_context: str
    suggested_turns: int


SCENARIOS: dict[ScenarioType, ScenarioConfig] = {
    ScenarioType.airport: ScenarioConfig(
        type=ScenarioType.airport,
        title="At the Airport",
        description="Practice checking in, going through security, and boarding your flight.",
        ai_role="airport check-in agent",
        opening_message="Good morning! Welcome to the check-in counter. May I see your passport and booking confirmation, please?",
        system_context="You are an airport check-in agent. Help the passenger check in for their flight, handle baggage, and provide gate information. Stay professional and helpful.",
        suggested_turns=12,
    ),
    ScenarioType.restaurant: ScenarioConfig(
        type=ScenarioType.restaurant,
        title="At the Restaurant",
        description="Practice ordering food, asking about the menu, and paying the bill.",
        ai_role="restaurant waiter",
        opening_message="Good evening! Welcome to The Golden Plate. I'll be your server tonight. Can I start you off with something to drink?",
        system_context="You are a friendly waiter at a nice restaurant. Help the guest with the menu, take their order, and handle any special requests. Be warm and attentive.",
        suggested_turns=15,
    ),
    ScenarioType.job_interview: ScenarioConfig(
        type=ScenarioType.job_interview,
        title="Job Interview",
        description="Practice answering common interview questions and presenting yourself professionally.",
        ai_role="job interviewer",
        opening_message="Hello, thank you for coming in today. Please have a seat. Before we begin, could you tell me a little about yourself?",
        system_context="You are a professional HR interviewer conducting a job interview. Ask common interview questions, follow up on answers, and evaluate the candidate. Be professional but friendly.",
        suggested_turns=20,
    ),
    ScenarioType.hotel_checkin: ScenarioConfig(
        type=ScenarioType.hotel_checkin,
        title="Hotel Check-in",
        description="Practice checking into a hotel, asking about amenities, and handling room issues.",
        ai_role="hotel receptionist",
        opening_message="Welcome to the Grand Hotel! Do you have a reservation with us?",
        system_context="You are a hotel front desk receptionist. Help the guest check in, explain hotel amenities, and handle any requests or issues. Be professional and welcoming.",
        suggested_turns=10,
    ),
    ScenarioType.shopping: ScenarioConfig(
        type=ScenarioType.shopping,
        title="Shopping",
        description="Practice asking about products, sizes, prices, and making purchases.",
        ai_role="shop assistant",
        opening_message="Hi there! Welcome to our store. Is there anything specific you're looking for today?",
        system_context="You are a friendly shop assistant in a clothing store. Help the customer find what they need, suggest options, discuss sizes and prices. Be helpful and not pushy.",
        suggested_turns=12,
    ),
    ScenarioType.doctor_visit: ScenarioConfig(
        type=ScenarioType.doctor_visit,
        title="Doctor's Visit",
        description="Practice describing symptoms, understanding medical advice, and asking questions.",
        ai_role="general practitioner doctor",
        opening_message="Hello, please come in and take a seat. What brings you in today? How have you been feeling?",
        system_context="You are a friendly general practitioner doctor. Ask about symptoms, medical history, and provide general medical advice. Be caring and thorough. Note: this is a language practice scenario, not real medical advice.",
        suggested_turns=15,
    ),
    ScenarioType.small_talk: ScenarioConfig(
        type=ScenarioType.small_talk,
        title="Small Talk",
        description="Practice casual conversation about weather, hobbies, weekend plans, and everyday topics.",
        ai_role="friendly acquaintance",
        opening_message="Hey! I haven't seen you in a while. How have you been? What have you been up to lately?",
        system_context="You are a friendly acquaintance making casual conversation. Discuss everyday topics like weather, hobbies, movies, weekend plans, and current events. Keep the conversation light and engaging.",
        suggested_turns=15,
    ),
    ScenarioType.business_meeting: ScenarioConfig(
        type=ScenarioType.business_meeting,
        title="Business Meeting",
        description="Practice professional communication, presenting ideas, and discussing projects.",
        ai_role="business colleague",
        opening_message="Good morning, everyone. Thanks for joining the meeting. Let's start with a quick update — how is your project going?",
        system_context="You are a business colleague in a team meeting. Discuss project updates, deadlines, and proposals. Use professional language and encourage the participant to share ideas and opinions.",
        suggested_turns=20,
    ),
    ScenarioType.free_conversation: ScenarioConfig(
        type=ScenarioType.free_conversation,
        title="Free Conversation",
        description="Have an open conversation on any topic. The AI will follow your lead.",
        ai_role="conversation partner",
        opening_message="Hi there! I'm happy to chat about anything you'd like. What's on your mind today?",
        system_context="You are a friendly and curious conversation partner. Follow the user's lead on topics. Ask follow-up questions to keep the conversation flowing naturally. Be engaging and supportive.",
        suggested_turns=20,
    ),
}
