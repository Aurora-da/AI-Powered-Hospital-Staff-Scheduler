from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class SwapRequest(BaseModel):
    staff_name: str
    date: str
    shift_type: str
    target_staff: Optional[str] = None


class QueryRequest(BaseModel):
    staff_name: Optional[str] = None
    date: Optional[str] = None
    shift_type: Optional[str] = None


class EmergencySubstituteRequest(BaseModel):
    staff_name: str
    date: str
    shift_type: str
    reason: str = "临时有事"


class LearnPreferenceRequest(BaseModel):
    user_input: str


class ChatRequest(BaseModel):
    message: str
