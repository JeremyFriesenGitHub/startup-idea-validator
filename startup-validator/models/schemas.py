from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any



class StressTestRequest(BaseModel):
    """Idea stress test request"""
    idea: str = Field(..., min_length=10, description="The startup idea to test")
    selected_critics: Optional[List[str]] = Field(None, description="List of critics to use (vc, engineer, ethicist, user, competitor)")


class ValidationResponse(BaseModel):
    """Complete validation response"""
    thread_id: str = Field(..., description="Thread ID for this conversation")
    assistant_id: str = Field(..., description="Assistant ID used for validation")
    input_idea: str = Field(..., description="Original input idea")
    neutral_idea: str = Field(..., description="Neutralized version of the idea")
    assumptions: str = Field(..., description="Extracted assumptions")
    critics: Dict[str, str] = Field(..., description="Critiques from different personas")
    risk_signals: Dict[str, Any] = Field(..., description="Computed risk signals")
    verdict: str = Field(..., description="Final synthesized verdict")
    meta: Dict[str, Any] = Field(..., description="Metadata including models used")






class FollowUpRequest(BaseModel):
    """Follow-up question request"""
    thread_id: str = Field(..., description="Thread ID from previous validation")
    question: str = Field(..., min_length=5, description="Follow-up question")


class FollowUpResponse(BaseModel):
    """Follow-up question response"""
    thread_id: str = Field(..., description="Thread ID for this conversation")
    answer: str = Field(..., description="Answer to the follow-up question")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    backboard_connected: bool = Field(..., description="Backboard.io connection status")
