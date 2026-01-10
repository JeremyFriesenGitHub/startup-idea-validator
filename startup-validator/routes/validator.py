from fastapi import APIRouter, HTTPException, status
from models.schemas import (
    IdeaSubmission,
    ValidationResponse,
    FollowUpRequest,
    FollowUpResponse
)
from services.backboard_service import get_backboard_service
import re

router = APIRouter(prefix="/api", tags=["validator"])


def parse_validation_response(analysis_text: str, thread_id: str, assistant_id: str) -> ValidationResponse:
    """
    Parse the AI response into a structured ValidationResponse
    This is a simple parser - adjust based on actual response format
    """
    # Extract summary (first paragraph or up to certain length)
    lines = analysis_text.strip().split('\n')
    summary_lines = []
    for line in lines[:5]:  # Take first few lines for summary
        if line.strip():
            summary_lines.append(line.strip())
    summary = ' '.join(summary_lines[:2]) if summary_lines else analysis_text[:200]
    
    # Try to extract bullet points for strengths, concerns, next steps
    strengths = []
    concerns = []
    next_steps = []
    
    # Simple pattern matching for common sections
    current_section = None
    for line in lines:
        line_lower = line.lower().strip()
        
        # Detect section headers
        if any(word in line_lower for word in ['strength', 'advantage', 'positive']):
            current_section = 'strengths'
        elif any(word in line_lower for word in ['concern', 'risk', 'challenge', 'weakness']):
            current_section = 'concerns'
        elif any(word in line_lower for word in ['next step', 'recommendation', 'action']):
            current_section = 'next_steps'
        
        # Extract bullet points
        if line.strip().startswith(('-', '•', '*', '+')):
            clean_line = re.sub(r'^[-•*+]\s*', '', line.strip())
            if clean_line and current_section == 'strengths':
                strengths.append(clean_line)
            elif clean_line and current_section == 'concerns':
                concerns.append(clean_line)
            elif clean_line and current_section == 'next_steps':
                next_steps.append(clean_line)
    
    # Fallback: if no structured data found, provide defaults
    if not strengths and not concerns and not next_steps:
        next_steps = ["Review the detailed analysis above", "Conduct market research", "Develop MVP"]
    
    return ValidationResponse(
        thread_id=thread_id,
        assistant_id=assistant_id,
        summary=summary,
        analysis=analysis_text,
        strengths=strengths,
        concerns=concerns,
        next_steps=next_steps
    )


@router.post("/validate", response_model=ValidationResponse, status_code=status.HTTP_200_OK)
async def validate_startup_idea(idea: IdeaSubmission):
    """
    Validate a startup idea using AI analysis
    
    Args:
        idea: Startup idea details
        
    Returns:
        Comprehensive validation analysis
    """
    try:
        # Get backboard service
        backboard = get_backboard_service()
        
        # Prepare idea data
        idea_data = {
            "idea_name": idea.idea_name,
            "description": idea.description,
            "target_market": idea.target_market,
            "problem_solving": idea.problem_solving,
            "unique_value": idea.unique_value
        }
        
        # Validate the idea
        result = backboard.validate_idea(idea_data, thread_id=idea.thread_id)
        
        # Parse and structure the response
        response = parse_validation_response(
            analysis_text=result["analysis"],
            thread_id=result["thread_id"],
            assistant_id=result["assistant_id"]
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating idea: {str(e)}"
        )


@router.post("/follow-up", response_model=FollowUpResponse, status_code=status.HTTP_200_OK)
async def ask_follow_up_question(request: FollowUpRequest):
    """
    Ask a follow-up question about a previously validated idea
    
    Args:
        request: Follow-up question with thread ID
        
    Returns:
        Answer to the follow-up question
    """
    try:
        # Get backboard service
        backboard = get_backboard_service()
        
        # Ask follow-up
        result = backboard.ask_follow_up(
            thread_id=request.thread_id,
            question=request.question
        )
        
        return FollowUpResponse(
            thread_id=result["thread_id"],
            answer=result["answer"]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing follow-up: {str(e)}"
        )


@router.get("/history/{thread_id}")
async def get_validation_history(thread_id: str):
    """
    Retrieve the conversation history for a validation thread
    
    Args:
        thread_id: Thread ID from previous validation
        
    Returns:
        List of messages in the thread
    """
    try:
        backboard = get_backboard_service()
        history = backboard.get_thread_history(thread_id)
        
        return {
            "thread_id": thread_id,
            "messages": history
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving history: {str(e)}"
        )
