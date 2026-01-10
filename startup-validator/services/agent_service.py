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
        self.MODELS = {
            "main": {
                "llm_provider": os.getenv("LLM_PROVIDER_MAIN", "openai"),
                "model_name": os.getenv("MODEL_MAIN", "gpt-4o"),
            },
            "vc": {
                "llm_provider": os.getenv("LLM_PROVIDER_VC", "anthropic"),
                "model_name": os.getenv("MODEL_VC", "claude-3-5-sonnet-latest"),
            },
            "engineer": {
                "llm_provider": os.getenv("LLM_PROVIDER_ENGINEER", "openai"),
                "model_name": os.getenv("MODEL_ENGINEER", "gpt-4o"), # Fallback from grok
            },
            "ethicist": {
                "llm_provider": os.getenv("LLM_PROVIDER_ETHICIST", "google"),
                "model_name": os.getenv("MODEL_ETHICIST", "gemini-1.5-pro"),
            },
            "user": {
                "llm_provider": os.getenv("LLM_PROVIDER_USER", "openai"),
                "model_name": os.getenv("MODEL_USER", "gpt-4o-mini"),
            },
            "competitor": {
                "llm_provider": os.getenv("LLM_PROVIDER_COMPETITOR", "openai"), 
                "model_name": os.getenv("MODEL_COMPETITOR", "gpt-4o"), # Fallback from cohere
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
            "vc": lambda neutral: f"""Persona: Skeptical VC\nAttack: market size, moat, monetization\n\nDeliver exactly:\n- MARKET: (1–2 bullets)\n- MONEY: (1–2 bullets)\n- MOAT: (1–2 bullets)\n- KILL SIGNAL: (one metric that would prove this is dead)\n\nBe blunt and specific.\n\nIdea:\n{neutral}""",
            "engineer": lambda neutral: f"""Persona: Senior Engineer\nAttack: scalability, edge cases, reliability\n\nDeliver exactly:\n- WHAT BREAKS FIRST: (1 bullet)\n- EDGE CASES: (3 bullets)\n- SCALING BOTTLENECK: (1 bullet)\n- MINIMUM BUILD (48 HOURS): (3 bullets)\n\nBe concrete. No generic advice.\n\nIdea:\n{neutral}""",
            "ethicist": lambda neutral: f"""Persona: Ethicist / Safety Reviewer\nAttack: harm, bias, misuse, privacy\n\nDeliver exactly:\n- LIKELY HARMS: (3 bullets)\n- MISUSE SCENARIO: (1 short scenario)\n- DATA RISK: (1 bullet)\n- REQUIRED SAFEGUARD TO SHIP: (2 bullets)\n\nDon’t moralize. Be practical.\n\nIdea:\n{neutral}""",
            "user": lambda neutral: f"""Persona: Real User (impatient, skeptical)\nAttack: adoption friction, trust, workflow fit\n\nDeliver exactly:\n- WHY I WON’T TRY IT: (3 bullets)\n- WHAT WOULD MAKE ME TRY IT TODAY: (2 bullets)\n- ONBOARDING FRICTION: (1 bullet)\n- ONE “AHA” MOMENT: (describe in 1 sentence)\n\nIdea:\n{neutral}""",
            "competitor": lambda neutral: f"""Persona: Competitor Strategy Lead\nAttack: why we’ll crush you\n\nDeliver exactly:\n- HOW WE COPY THIS FAST: (2 bullets)\n- WHY USERS CHOOSE US: (2 bullets)\n- YOUR WEAK SPOT: (1 bullet)\n- DEFENSE YOU COULD BUILD: (2 bullets)\n\nBe ruthless.\n\nIdea:\n{neutral}""",
            "final_judge": lambda neutral, assume, critics: f"""You are an independent hackathon judge.\nSynthesize the critics below into a decisive verdict.\n\nReturn in this exact format:\n\nPRIMARY FAILURE MODE:\n- (one sentence)\n\nTOP 3 ASSUMPTIONS TO TEST:\n1) ...\n2) ...\n3) ...\n\nKILL QUESTION:\n- (one question)\n\nWINNING DEMO ANGLE:\n- (one sentence: how to demo this in 30 seconds)\n\n48-HOUR VALIDATION EXPERIMENT:\n- (one experiment + success metric)\n\nONE PIVOT TO MAKE THIS A WINNER:\n- (one sentence)\n\nINPUTS\nNeutral Idea:\n{neutral}\n\nAssumptions:\n{assume}\n\nVC:\n{critics["vc"]}\n\nEngineer:\n{critics["engineer"]}\n\nEthicist:\n{critics["ethicist"]}\n\nUser:\n{critics["user"]}\n\nCompetitor:\n{critics["competitor"]}""",
        }

    # --- Main Workflow ---

    async def run_stress_test(self, idea_text: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the full agentic stress test workflow.
        """
        assistant_id = await self.ensure_assistant()
        
        # Create thread if new
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
            # Note: We don't need to persist this thread ID as the interaction is one-off.
            t = await self.client.create_thread(assistant_id=assistant_id)
            t_id = getattr(t, "id", None) or getattr(t, "thread_id", None)
            if isinstance(t, dict): t_id = t.get("id") or t.get("thread_id")
            
            return await self.run_block_async(
                str(t_id),
                prompt,
                model_conf["llm_provider"],
                model_conf["model_name"]
            )

        critic_tasks = [
            _run_isolated_critic(P["vc"](neutral_idea), self.MODELS["vc"]),
            _run_isolated_critic(P["engineer"](neutral_idea), self.MODELS["engineer"]),
            _run_isolated_critic(P["ethicist"](neutral_idea), self.MODELS["ethicist"]),
            _run_isolated_critic(P["user"](neutral_idea), self.MODELS["user"]),
            _run_isolated_critic(P["competitor"](neutral_idea), self.MODELS["competitor"]),
        ]
        
        # Run critics in parallel
        results = await asyncio.gather(*critic_tasks)
        critics = {
            "vc": results[0],
            "engineer": results[1],
            "ethicist": results[2],
            "user": results[3],
            "competitor": results[4],
        }

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
