from pydantic import BaseModel, Field
from typing import Optional, List


class IdeaSubmission(BaseModel):
    """Startup idea submission request"""
    idea_name: str = Field(..., min_length=1, max_length=200, description="Name of the startup idea")
    description: str = Field(..., min_length=10, description="Detailed description of the idea")
    target_market: str = Field(..., min_length=5, description="Target market or customer segment")
    problem_solving: str = Field(..., min_length=10, description="What problem does this solve?")
    unique_value: Optional[str] = Field(None, description="Unique value proposition or differentiator")
    thread_id: Optional[str] = Field(None, description="Thread ID for continuing a conversation")


class ValidationResult(BaseModel):
    """Validation analysis result"""
    category: str = Field(..., description="Analysis category (e.g., Market Viability, Competition)")
    score: Optional[int] = Field(None, ge=0, le=100, description="Score out of 100")
    analysis: str = Field(..., description="Detailed analysis text")
    recommendations: List[str] = Field(default_factory=list, description="Specific recommendations")


class ValidationResponse(BaseModel):
    """Complete validation response"""
    thread_id: str = Field(..., description="Thread ID for this conversation")
    assistant_id: str = Field(..., description="Assistant ID used for validation")
    summary: str = Field(..., description="Overall validation summary")
    analysis: str = Field(..., description="Complete analysis from the AI")
    strengths: List[str] = Field(default_factory=list, description="Key strengths identified")
    concerns: List[str] = Field(default_factory=list, description="Key concerns or risks")
    next_steps: List[str] = Field(default_factory=list, description="Recommended next steps")


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
