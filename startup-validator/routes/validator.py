from fastapi import APIRouter, HTTPException, status
from models.schemas import (
    StressTestRequest,
    ValidationResponse,
    FollowUpRequest,
    FollowUpResponse
)
from services.agent_service import get_agent_service

router = APIRouter(prefix="/api", tags=["validator"])


@router.post("/validate", response_model=ValidationResponse, status_code=status.HTTP_200_OK)
async def validate_startup_idea(request: StressTestRequest):
    """
    Stress test a startup idea using the Agentic workflow.
    """
    try:
        agent = get_agent_service()
        
        # Run stress test (async)
        result = await agent.run_stress_test(request.idea)
        
        return ValidationResponse(**result)
        
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
    """
    try:
        agent = get_agent_service()
        
        # Ask follow-up
        answer = await agent.ask_follow_up(
            thread_id=request.thread_id,
            question=request.question
        )
        
        return FollowUpResponse(
            thread_id=request.thread_id,
            answer=answer
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
    Retrieve the conversation history for a validation thread.
    (Wrapped directly from SDK if possible, or implemented in service)
    """
    # Note: AgentService currently doesn't expose history listing. 
    # For now we return not implemented or basic info.
    # To strictly follow "new code", we might omit this if not requested, 
    # but to support existing frontend we can try.
    
    # Simple workaround: The new code didn't focus on history.
    # We'll just return the thread_id to not break the route, 
    # or better, implement a passthrough in agent_service if SDK supports it.
    
    # For now, let's keep it minimal as per user request to use "new code approach".
    return {"thread_id": thread_id, "messages": "History retrieval not yet implemented in Agentic mode."}
