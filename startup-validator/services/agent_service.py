import os
import re
import asyncio
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Use backboard module
try:
    from backboard import BackboardClient
except ImportError:
    BackboardClient = None

load_dotenv()

class AgentService:
    """
    Service for orchestrating the Agentic/Multi-Persona stress test workflow.
    """

    def __init__(self):
        self.api_key = os.getenv("BACKBOARD_API_KEY")
        if not self.api_key:
            raise ValueError("BACKBOARD_API_KEY not found in environment variables")
        
        if BackboardClient is None:
             raise ImportError("backboard-sdk not installed. Please install it.")

        self.client = BackboardClient(api_key=self.api_key)
        self.assistant_id: Optional[str] = None
        
        # Load Model Configurations
        # Refactored to use OpenAI GPT-4o for all personas
        default_provider = "openai"
        default_model = "gpt-4o"

        self.MODELS = {
            "main": {
                "llm_provider": os.getenv("LLM_PROVIDER_MAIN", default_provider),
                "model_name": os.getenv("MODEL_MAIN", default_model),
            },
            "vc": {
                "llm_provider": os.getenv("LLM_PROVIDER_VC", default_provider),
                "model_name": os.getenv("MODEL_VC", default_model),
            },
            "engineer": {
                "llm_provider": os.getenv("LLM_PROVIDER_ENGINEER", default_provider),
                "model_name": os.getenv("MODEL_ENGINEER", default_model),
            },
            "ethicist": {
                "llm_provider": os.getenv("LLM_PROVIDER_ETHICIST", default_provider),
                "model_name": os.getenv("MODEL_ETHICIST", default_model),
            },
            "user": {
                "llm_provider": os.getenv("LLM_PROVIDER_USER", default_provider),
                "model_name": os.getenv("MODEL_USER", default_model),
            },
            "competitor": {
                "llm_provider": os.getenv("LLM_PROVIDER_COMPETITOR", default_provider), 
                "model_name": os.getenv("MODEL_COMPETITOR", default_model),
            },
        }

    async def ensure_assistant(self) -> str:
        """Ensure the Backboard assistant exists (singleton-ish pattern per instance)."""
        if self.assistant_id:
            return str(self.assistant_id)

        # Create assistant once
        # SDK uses snake_case and is async
        assistant = await self.client.create_assistant(
            name="Idea Stress Tester",
            description=(
                "Forced adversarial reasoning system: neutralizes optimism bias, "
                "extracts assumptions, runs 5 persona critics, synthesizes a decisive verdict."
            )
        )

        # Handle SDK variations
        _id = getattr(assistant, "id", None) or getattr(assistant, "assistant_id", None)
        if not _id:
             # Fallback if it returns dict
             if isinstance(assistant, dict):
                 _id = assistant.get("id") or assistant.get("assistant_id")
        
        if not _id:
            raise RuntimeError("Could not read assistantId from Backboard create_assistant response.")
        
        self.assistant_id = str(_id)
        return self.assistant_id

    async def run_block_async(self, thread_id: str, content: str, llm_provider: str, model_name: str) -> str:
        """Async wrapper for the add_message call."""
        # SDK add_message is likely async. If not, we wrap it.
        # Based on previous file, it seemed to be async.
        # Arguments: thread_id, content, model_name, etc.
        
        try:
            resp = await self.client.add_message(
                thread_id=thread_id,
                content=content,
                model_name=model_name
            )
        except TypeError:
            # Fallback if arguments differ slightly
            resp = await self.client.add_message(thread_id, content, model_name=model_name)

        # Extract content
        text = getattr(resp, "content", None) or (resp.get("content") if isinstance(resp, dict) else None)
        if not text:
             # Try other fields
             text = getattr(resp, "message", None) or (resp.get("message") if isinstance(resp, dict) else None)
             
        if not text:
            return "" 
        return str(text).strip()

    # --- Logic Helpers ---

    def normalize_text(self, s: str) -> str:
        s = (s or "").lower()
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def text_hits_theme(self, text: str, patterns: List[Any]) -> bool:
        t = self.normalize_text(text)
        for p in patterns:
            if isinstance(p, str):
                if p in t:
                    return True
            else:
                if p.search(t):
                    return True
        return False

    def compute_risk_signals(self, critics: Dict[str, str], threshold: int = 3) -> Dict[str, Any]:
        themes = [
            {
                "key": "distribution_adoption",
                "label": "Distribution / adoption friction",
                "patterns": ["distribution", "acquisition", "marketing", "onboarding", "adoption", "retention", "growth", re.compile(r"go to market")],
            },
            {
                "key": "trust_credibility",
                "label": "Trust / credibility",
                "patterns": ["trust", "credible", "accuracy", "hallucination", "reliability", "confidence", "wrong", "false", "misleading"],
            },
            {
                "key": "privacy_compliance",
                "label": "Privacy / compliance risk",
                "patterns": ["privacy", "pii", "gdpr", "hipaa", "consent", "compliance", "data leak", "breach", "sensitive"],
            },
            {
                "key": "security_abuse",
                "label": "Security / misuse / abuse",
                "patterns": ["security", "abuse", "misuse", "fraud", "spam", "scam", "attack", "prompt injection", "jailbreak"],
            },
            {
                "key": "moat_competition",
                "label": "Weak moat / competition will copy",
                "patterns": ["moat", "defensible", "differentiation", "commodity", "copy", "clone", "competition", "incumbent"],
            },
            {
                "key": "scalability_cost",
                "label": "Scalability / cost",
                "patterns": ["scale", "scalability", "latency", "cost", "token", "inference", "throughput", "rate limit"],
            },
            {
                "key": "product_scope",
                "label": "Too broad / unclear scope",
                "patterns": ["scope", "too broad", "vague", "unclear", "who is this for", "not specific", "undefined"],
            },
        ]

        theme_counts = {t["key"]: 0 for t in themes}
        mentions = {t["key"]: [] for t in themes}

        for persona, txt in critics.items():
            for th in themes:
                if self.text_hits_theme(txt, th["patterns"]):
                    theme_counts[th["key"]] += 1
                    mentions[th["key"]].append(persona)

        ranked = sorted(
            [{"key": th["key"], "label": th["label"], "count": theme_counts[th["key"]], "personas": mentions[th["key"]]} for th in themes],
            key=lambda x: x["count"],
            reverse=True,
        )

        high_conf = [x for x in ranked if x["count"] >= threshold]
        confidence_note = (
            f"High confidence risk: {high_conf[0]['label']} (mentioned by {high_conf[0]['count']}/5 personas)."
            if high_conf else
            f"No high-confidence convergence (no theme mentioned by ≥{threshold} personas)."
        )

        return {
            "topThemes": ranked[:3],
            "highConfidenceRisks": high_conf,
            "themeCounts": theme_counts,
            "threshold": threshold,
            "confidenceNote": confidence_note,
        }

    # --- Prompts ---

    def _build_prompts(self, idea: str) -> Dict[str, Any]:
        """Generate prompt templates injected with the idea."""
        # Note: In a real app, these might be loaded from files or a DB.
        
        return {
            "bias_remover": f"""Rewrite the idea below in neutral, factual language.\nRules:\n- Remove adjectives, hype, and assumptions of success.\n- Convert vague claims into testable statements.\n- Keep it to 3–6 sentences.\nReturn ONLY the rewritten idea.\n\nIdea:\n{idea}""",
            "assumptions": lambda neutral: f"""Extract the hidden assumptions that must be true for this idea to succeed.\nRules:\n- Only necessary assumptions (not nice-to-have).\n- Phrase each as falsifiable.\n- 8–12 max.\n\nReturn as a numbered list.\n\nIdea:\n{neutral}""",
            "vc": lambda neutral: f"""Persona: Skeptical VC\nAttack: market size, moat, monetization\n\nDeliver exactly:\n- MARKET RISKS: (2 bullets)\n- MOAT & DEFENSE: (2 bullets)\n- KILL SIGNAL: (1 metric that proves this is dead)\n- ONE RECOMMENDATION: (1 specific action)\n\nBe blunt and specific.\n\nIdea:\n{neutral}""",
            "engineer": lambda neutral: f"""Persona: Senior Engineer\nAttack: scalability, edge cases, reliability\n\nDeliver exactly:\n- SYSTEM RISKS: (2 bullets)\n- EDGE CASES: (2 bullets)\n- SCALING BOTTLENECK: (1 specific bottleneck)\n- MINIMUM BUILD: (1 critical feature to build first)\n\nBe concrete. No generic advice.\n\nIdea:\n{neutral}""",
            "ethicist": lambda neutral: f"""Persona: Ethicist / Safety Reviewer\nAttack: harm, bias, misuse, privacy\n\nDeliver exactly:\n- HARMS & BIAS: (2 bullets)\n- MISUSE SCENARIOS: (2 bullets)\n- DATA PRIVACY: (1 specific risk)\n- REQUIRED SAFEGUARD: (1 mandatory control)\n\nDon’t moralize. Be practical.\n\nIdea:\n{neutral}""",
            "user": lambda neutral: f"""Persona: Real User (impatient, skeptical)\nAttack: adoption friction, trust, workflow fit\n\nDeliver exactly:\n- ADOPTION FRICTION: (2 bullets)\n- TRUST ISSUES: (2 bullets)\n- DEALBREAKER: (1 reason I won't sign up)\n- WHAT WOULD CONVINCE ME: (1 feature/change)\n\nIdea:\n{neutral}""",
            "competitor": lambda neutral: f"""Persona: Competitor Strategy Lead\nAttack: why we’ll crush you\n\nDeliver exactly:\n- COMPETITIVE ADVANTAGE: (2 bullets on why we win)\n- COPYCAT STRATEGY: (2 bullets on how we copy you)\n- YOUR WEAKNESS: (1 critical flaw)\n- DEFENSIVE MOVE: (1 thing you must do)\n\nBe ruthless.\n\nIdea:\n{neutral}""",
            "final_judge": lambda neutral, assume, critics: f"""You are an independent hackathon judge.\nSynthesize the critics below into a decisive verdict.\n\nReturn in this exact format:\n\nPRIMARY FAILURE MODE:\n- (one sentence)\n\nTOP 3 ASSUMPTIONS TO TEST:\n1) ...\n2) ...\n3) ...\n\nKILL QUESTION:\n- (one question)\n\nWINNING DEMO ANGLE:\n- (one sentence: how to demo this in 30 seconds)\n\n48-HOUR VALIDATION EXPERIMENT:\n- (one experiment + success metric)\n\nONE PIVOT TO MAKE THIS A WINNER:\n- (one sentence)\n\nINPUTS\nNeutral Idea:\n{neutral}\n\nAssumptions:\n{assume}\n\n""" + "\n\n".join([f"{k.title()}:\n{v}" for k, v in critics.items()])
        }

    # --- Main Workflow ---

    async def run_stress_test(self, idea_text: str, thread_id: Optional[str] = None, selected_critics: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute the full agentic stress test workflow.
        """
        assistant_id = await self.ensure_assistant()
        
        # Default to all critics if none selected
        available_critics = ["vc", "engineer", "ethicist", "user", "competitor"]
        if not selected_critics:
            selected_critics = available_critics
        
        # Filter selected critics to ensure they are valid
        selected_critics = [c for c in selected_critics if c in available_critics]
        if not selected_critics:
             selected_critics = available_critics

        if not thread_id:
            # SDK create_thread is async
            thread = await self.client.create_thread(assistant_id=assistant_id)
            
            thread_id = getattr(thread, "id", None) or getattr(thread, "thread_id", None)
            if not thread_id:
                if isinstance(thread, dict):
                    thread_id = thread.get("id") or thread.get("thread_id")
            
            if not thread_id:
                # String fallback
                if isinstance(thread, str):
                    thread_id = thread
                else:
                    raise RuntimeError("Could not create threadId via create_thread.")
        
        thread_id = str(thread_id)

        P = self._build_prompts(idea_text)
        
        # 1. Neutralize Hype
        neutral_idea = await self.run_block_async(
            thread_id, 
            P["bias_remover"], 
            self.MODELS["main"]["llm_provider"], 
            self.MODELS["main"]["model_name"]
        )

        # 2. Extract Assumptions
        assumptions_txt = await self.run_block_async(
            thread_id,
            P["assumptions"](neutral_idea),
            self.MODELS["main"]["llm_provider"],
            self.MODELS["main"]["model_name"]
        )

        # 3. Parallel Critics
        # We must run each critic in a Separate Thread to avoid "Assistant is processing" locking issues
        # on the main thread.
        async def _run_isolated_critic(prompt: str, model_conf: Dict[str, str]) -> str:
            # Create a localized thread for this critic
            t = await self.client.create_thread(assistant_id=assistant_id)
            t_id = getattr(t, "id", None) or getattr(t, "thread_id", None)
            if isinstance(t, dict): t_id = t.get("id") or t.get("thread_id")
            
            t_id_str = str(t_id)
            
            try:
                return await self.run_block_async(
                    t_id_str,
                    prompt,
                    model_conf["llm_provider"],
                    model_conf["model_name"]
                )
            finally:
                # Cleanup: Delete the temporary thread
                try:
                    await self.client.delete_thread(thread_id=t_id_str)
                except Exception as e:
                    print(f"Warning: Failed to delete temporary thread {t_id_str}: {e}")

        critic_tasks = []
        critic_names = []
        
        for critic_name in selected_critics:
            critic_prompt = P[critic_name](neutral_idea)
            model_conf = self.MODELS[critic_name]
            critic_tasks.append(_run_isolated_critic(critic_prompt, model_conf))
            critic_names.append(critic_name)
        
        # Run critics in parallel
        results = await asyncio.gather(*critic_tasks)
        critics = {name: result for name, result in zip(critic_names, results)}

        # 4. Compute Risk Signals (Local Python)
        risk_signals = self.compute_risk_signals(critics)

        # 5. Final Verdict
        verdict = await self.run_block_async(
            thread_id,
            P["final_judge"](neutral_idea, assumptions_txt, critics),
            self.MODELS["main"]["llm_provider"],
            self.MODELS["main"]["model_name"]
        )

        return {
            "thread_id": thread_id,
            "assistant_id": assistant_id,
            "input_idea": idea_text,
            "neutral_idea": neutral_idea,
            "assumptions": assumptions_txt,
            "critics": critics,
            "risk_signals": risk_signals,
            "verdict": verdict,
            "meta": {
                "models": self.MODELS
            }
        }

    async def ask_follow_up(self, thread_id: str, question: str) -> str:
        """
        Ask a follow-up question in the existing thread context.
        Uses the 'main' model for general interaction.
        """
        return await self.run_block_async(
            thread_id,
            question,
            self.MODELS["main"]["llm_provider"],
            self.MODELS["main"]["model_name"]
        )

    def health_check(self) -> bool:
        """Check if client and config are valid."""
        return self.client is not None and self.api_key is not None


# Singleton
_agent_service = None

def get_agent_service() -> AgentService:
    global _agent_service
    if not _agent_service:
        _agent_service = AgentService()
    return _agent_service
