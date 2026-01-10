import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

try:
    from backboard import BackboardClient
except ImportError:
    BackboardClient = None

load_dotenv()


class BackboardService:
    """Service for interacting with Backboard.io API"""
    
    def __init__(self):
        self.api_key = os.getenv("BACKBOARD_API_KEY")
        if not self.api_key:
            raise ValueError("BACKBOARD_API_KEY not found in environment variables")
        
        if BackboardClient is None:
            raise ImportError("backboard-sdk not installed. Run: pip install backboard-sdk")
            
        self.client = BackboardClient(api_key=self.api_key)
        self.assistant_id: Optional[str] = None
        self.system_prompt = ""
        # Note: Assistant will be created lazily on first use since it's async
    
    async def _ensure_assistant(self):
        """Ensure assistant is created (lazy initialization for async)"""
        if self.assistant_id is not None:
            return
            
        # System prompt will be included in messages
        self.system_prompt = """You are an expert startup validator and business analyst with deep experience in:
- Market analysis and competitive landscape assessment
- Business model evaluation and monetization strategies
- Product-market fit analysis
- Scalability and growth potential assessment
- Risk identification and mitigation
- Go-to-market strategy

Your role is to provide honest, constructive, and actionable feedback on startup ideas. 
Analyze each idea across multiple dimensions:
1. Market Viability - Is there a real market need?
2. Competition - Who are the competitors and what's the competitive advantage?
3. Scalability - Can this scale beyond initial launch?
4. Monetization - How will this make money?
5. Execution Risk - What are the key challenges to execution?
6. Innovation - How novel or differentiated is this idea?

Provide specific, actionable recommendations. Be encouraging but realistic. 
Identify both strengths and potential concerns. Use your memory to reference similar 
ideas you've analyzed before and provide comparative insights.

Format your response with clear sections and bullet points for easy reading."""

        # Create assistant using the correct API method
        # Note: create_assistant only takes name and description and is async
        assistant = await self.client.create_assistant(
            name="Startup Idea Validator",
            description="AI assistant for validating and analyzing startup ideas across multiple dimensions"
        )
        # Extract assistant ID from response
        if isinstance(assistant, dict):
            self.assistant_id = assistant.get('id') or assistant.get('assistant_id')
        elif hasattr(assistant, 'id'):
            self.assistant_id = assistant.id
        elif hasattr(assistant, 'assistant_id'):
            self.assistant_id = assistant.assistant_id
        else:
            self.assistant_id = str(assistant)
            
        # Ensure it's a string if it's a UUID object
        self.assistant_id = str(self.assistant_id)
        
        print(f"✓ Assistant created: {self.assistant_id}")
    
    async def validate_idea(self, idea_data: Dict[str, Any], thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate a startup idea using the AI assistant
        
        Args:
            idea_data: Dictionary containing idea details
            thread_id: Optional thread ID to continue a conversation
            
        Returns:
            Dictionary with validation results and thread info
        """
        try:
            # Ensure assistant is created (lazy async initialization)
            await self._ensure_assistant()
            
            # Create or use existing thread
            if thread_id:
                thread_obj = {"id": thread_id}
            else:
                # create_thread requires assistant_id and is async
                thread_obj = await self.client.create_thread(assistant_id=self.assistant_id)
                if isinstance(thread_obj, dict):
                    thread_id = thread_obj.get('id') or thread_obj.get('thread_id')
                elif hasattr(thread_obj, 'id'):
                    thread_id = thread_obj.id
                elif hasattr(thread_obj, 'thread_id'):
                    thread_id = thread_obj.thread_id
                else:
                    thread_id = str(thread_obj)
            
            # Ensure it's a string if it's a UUID object
            thread_id = str(thread_id)
            
            # Format the idea into a comprehensive prompt with system context
            prompt = f"""{self.system_prompt}

Now, please validate this startup idea:

**Idea Name:** {idea_data.get('idea_name', 'N/A')}

**Description:** {idea_data.get('description', 'N/A')}

**Target Market:** {idea_data.get('target_market', 'N/A')}

**Problem Being Solved:** {idea_data.get('problem_solving', 'N/A')}
"""
            
            if idea_data.get('unique_value'):
                prompt += f"\n**Unique Value Proposition:** {idea_data['unique_value']}\n"
            
            prompt += """
Please provide a comprehensive validation analysis covering:
1. Market viability and opportunity size
2. Competitive landscape analysis
3. Scalability potential
4. Monetization strategies
5. Key execution risks
6. Innovation assessment
7. Overall recommendation and next steps

Be specific and actionable in your feedback."""

            # Send message with memory enabled using the correct method
            # Note: add_message is async and doesn't need assistant_id, uses model_name instead
            response = await self.client.add_message(
                thread_id=thread_id,
                content=prompt,
                model_name="gpt-4o",  # Specify model here
                memory="Auto"  # Enable memory for this message
            )
            
            # Extract the response text from the actual SDK response structure
            analysis_text = ""
            if isinstance(response, dict):
                # Try different possible response structures
                analysis_text = (
                    response.get('content') or 
                    response.get('message') or 
                    response.get('text') or
                    str(response)
                )
            elif hasattr(response, 'content'):
                analysis_text = response.content
            elif hasattr(response, 'message'):
                analysis_text = response.message
            else:
                analysis_text = str(response)
            
            return {
                "thread_id": thread_id,
                "assistant_id": self.assistant_id,
                "analysis": analysis_text,
                "raw_response": response
            }
            
        except Exception as e:
            print(f"Error validating idea: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def ask_follow_up(self, thread_id: str, question: str) -> Dict[str, Any]:
        """
        Ask a follow-up question in an existing thread
        
        Args:
            thread_id: Thread ID from previous validation
            question: Follow-up question
            
        Returns:
            Dictionary with answer and thread info
        """
        try:
            # Ensure assistant is created
            await self._ensure_assistant()
            
            # Send follow-up message using correct method (async)
            response = await self.client.add_message(
                thread_id=thread_id,
                content=question,
                model_name="gpt-4o",
                memory="Auto"
            )
            
            # Extract response
            answer = ""
            if isinstance(response, dict):
                answer = (
                    response.get('content') or 
                    response.get('message') or 
                    response.get('text') or
                    str(response)
                )
            elif hasattr(response, 'content'):
                answer = response.content
            elif hasattr(response, 'message'):
                answer = response.message
            else:
                answer = str(response)
            
            return {
                "thread_id": thread_id,
                "answer": answer
            }
            
        except Exception as e:
            print(f"Error asking follow-up: {e}")
            raise
    
    def get_thread_history(self, thread_id: str) -> list:
        """
        Retrieve message history for a thread
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of messages in the thread
        """
        try:
            # Use get_thread to retrieve thread details
            thread = self.client.get_thread(thread_id=thread_id)
            return thread if isinstance(thread, list) else [thread]
        except Exception as e:
            print(f"Error retrieving thread history: {e}")
            raise
    
    def health_check(self) -> bool:
        """Check if the Backboard service is healthy"""
        try:
            return self.client is not None and self.assistant_id is not None
        except Exception:
            return False


# Singleton instance
_backboard_service: Optional[BackboardService] = None


def get_backboard_service() -> BackboardService:
    """Get or create the Backboard service instance"""
    global _backboard_service
    if _backboard_service is None:
        _backboard_service = BackboardService()
    return _backboard_service
