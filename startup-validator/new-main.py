import os
import re
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# Backboard SDK (Python)
# NOTE: Import path may differ slightly depending on the SDK version.
# If your quickstart shows a different import, update it here.
from backboard_sdk import BackboardClient  # type: ignore

load_dotenv()

PORT = int(os.getenv("PORT", "8080"))
BACKBOARD_API_KEY = os.getenv("BACKBOARD_API_KEY")

if not BACKBOARD_API_KEY:
    raise RuntimeError("Missing BACKBOARD_API_KEY in .env")

app = FastAPI(title="Idea Stress Tester (Backboard)")

client = BackboardClient(api_key=BACKBOARD_API_KEY)

MODELS = {
    "main": {
        "llm_provider": os.getenv("LLM_PROVIDER_MAIN", "openai"),
        "model_name": os.getenv("MODEL_MAIN", "gpt-5-chat-latest"),
    },
    "vc": {
        "llm_provider": os.getenv("LLM_PROVIDER_VC", "anthropic"),
        "model_name": os.getenv("MODEL_VC", "claude-3-7-sonnet-20250219"),
    },
    "engineer": {
        "llm_provider": os.getenv("LLM_PROVIDER_ENGINEER", "xai"),
        "model_name": os.getenv("MODEL_ENGINEER", "grok-code-fast-1"),
    },
    "ethicist": {
        "llm_provider": os.getenv("LLM_PROVIDER_ETHICIST", "google"),
        "model_name": os.getenv("MODEL_ETHICIST", "gemini-2.5-pro"),
    },
    "user": {
        "llm_provider": os.getenv("LLM_PROVIDER_USER", "openai"),
        "model_name": os.getenv("MODEL_USER", "gpt-4.1-mini"),
    },
    "competitor": {
        "llm_provider": os.getenv("LLM_PROVIDER_COMPETITOR", "cohere"),
        "model_name": os.getenv("MODEL_COMPETITOR", "command-a-03-2025"),
    },
}

# Cache assistant id (created once)
ASSISTANT_ID: Optional[str] = None


class StressTestRequest(BaseModel):
    idea: str


def normalize_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def text_hits_theme(text: str, patterns: List[Any]) -> bool:
    t = normalize_text(text)
    for p in patterns:
        if isinstance(p, str):
            if p in t:
                return True
        else:
            # regex
            if p.search(t):
                return True
    return False


def compute_risk_signals(critics: Dict[str, str], threshold: int = 3) -> Dict[str, Any]:
    themes = [
        {
            "key": "distribution_adoption",
            "label": "Distribution / adoption friction",
            "patterns": [
                "distribution", "acquisition", "marketing", "onboarding",
                "adoption", "retention", "growth", re.compile(r"go to market")
            ],
        },
        {
            "key": "trust_credibility",
            "label": "Trust / credibility",
            "patterns": [
                "trust", "credible", "accuracy", "hallucination",
                "reliability", "confidence", "wrong", "false", "misleading"
            ],
        },
        {
            "key": "privacy_compliance",
            "label": "Privacy / compliance risk",
            "patterns": [
                "privacy", "pii", "gdpr", "hipaa", "consent",
                "compliance", "data leak", "breach", "sensitive"
            ],
        },
        {
            "key": "security_abuse",
            "label": "Security / misuse / abuse",
            "patterns": [
                "security", "abuse", "misuse", "fraud", "spam", "scam",
                "attack", "prompt injection", "jailbreak"
            ],
        },
        {
            "key": "moat_competition",
            "label": "Weak moat / competition will copy",
            "patterns": [
                "moat", "defensible", "differentiation", "commodity",
                "copy", "clone", "competition", "incumbent"
            ],
        },
        {
            "key": "scalability_cost",
            "label": "Scalability / cost",
            "patterns": [
                "scale", "scalability", "latency", "cost",
                "token", "inference", "throughput", "rate limit"
            ],
        },
        {
            "key": "product_scope",
            "label": "Too broad / unclear scope",
            "patterns": [
                "scope", "too broad", "vague", "unclear",
                "who is this for", "not specific", "undefined"
            ],
        },
    ]

    theme_counts = {t["key"]: 0 for t in themes}
    mentions = {t["key"]: [] for t in themes}

    for persona, txt in critics.items():
        for th in themes:
            if text_hits_theme(txt, th["patterns"]):
                theme_counts[th["key"]] += 1
                mentions[th["key"]].append(persona)

    ranked = sorted(
        [
            {
                "key": th["key"],
                "label": th["label"],
                "count": theme_counts[th["key"]],
                "personas": mentions[th["key"]],
            }
            for th in themes
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    high_conf = [x for x in ranked if x["count"] >= threshold]

    confidence_note = (
        f"High confidence risk: {high_conf[0]['label']} "
        f"(mentioned by {high_conf[0]['count']}/5 personas)."
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


def build_prompts(idea: str) -> Dict[str, Any]:
    bias_remover = f"""
Rewrite the idea below in neutral, factual language.
Rules:
- Remove adjectives, hype, and assumptions of success.
- Convert vague claims into testable statements.
- Keep it to 3–6 sentences.
Return ONLY the rewritten idea.

Idea:
{idea}
""".strip()

    def assumptions(neutral_idea: str) -> str:
        return f"""
Extract the hidden assumptions that must be true for this idea to succeed.
Rules:
- Only necessary assumptions (not nice-to-have).
- Phrase each as falsifiable.
- 8–12 max.

Return as a numbered list.

Idea:
{neutral_idea}
""".strip()

    def vc(neutral_idea: str) -> str:
        return f"""
Persona: Skeptical VC
Attack: market size, moat, monetization

Deliver exactly:
- MARKET: (1–2 bullets)
- MONEY: (1–2 bullets)
- MOAT: (1–2 bullets)
- KILL SIGNAL: (one metric that would prove this is dead)

Be blunt and specific.

Idea:
{neutral_idea}
""".strip()

    def engineer(neutral_idea: str) -> str:
        return f"""
Persona: Senior Engineer
Attack: scalability, edge cases, reliability

Deliver exactly:
- WHAT BREAKS FIRST: (1 bullet)
- EDGE CASES: (3 bullets)
- SCALING BOTTLENECK: (1 bullet)
- MINIMUM BUILD (48 HOURS): (3 bullets)

Be concrete. No generic advice.

Idea:
{neutral_idea}
""".strip()

    def ethicist(neutral_idea: str) -> str:
        return f"""
Persona: Ethicist / Safety Reviewer
Attack: harm, bias, misuse, privacy

Deliver exactly:
- LIKELY HARMS: (3 bullets)
- MISUSE SCENARIO: (1 short scenario)
- DATA RISK: (1 bullet)
- REQUIRED SAFEGUARD TO SHIP: (2 bullets)

Don’t moralize. Be practical.

Idea:
{neutral_idea}
""".strip()

    def user(neutral_idea: str) -> str:
        return f"""
Persona: Real User (impatient, skeptical)
Attack: adoption friction, trust, workflow fit

Deliver exactly:
- WHY I WON’T TRY IT: (3 bullets)
- WHAT WOULD MAKE ME TRY IT TODAY: (2 bullets)
- ONBOARDING FRICTION: (1 bullet)
- ONE “AHA” MOMENT: (describe in 1 sentence)

Idea:
{neutral_idea}
""".strip()

    def competitor(neutral_idea: str) -> str:
        return f"""
Persona: Competitor Strategy Lead
Attack: why we’ll crush you

Deliver exactly:
- HOW WE COPY THIS FAST: (2 bullets)
- WHY USERS CHOOSE US: (2 bullets)
- YOUR WEAK SPOT: (1 bullet)
- DEFENSE YOU COULD BUILD: (2 bullets)

Be ruthless.

Idea:
{neutral_idea}
""".strip()

    def final_judge(neutral_idea: str, assumptions_txt: str, critics: Dict[str, str]) -> str:
        return f"""
You are an independent hackathon judge.
Synthesize the critics below into a decisive verdict.

Return in this exact format:

PRIMARY FAILURE MODE:
- (one sentence)

TOP 3 ASSUMPTIONS TO TEST:
1) ...
2) ...
3) ...

KILL QUESTION:
- (one question)

WINNING DEMO ANGLE:
- (one sentence: how to demo this in 30 seconds)

48-HOUR VALIDATION EXPERIMENT:
- (one experiment + success metric)

ONE PIVOT TO MAKE THIS A WINNER:
- (one sentence)

INPUTS
Neutral Idea:
{neutral_idea}

Assumptions:
{assumptions_txt}

VC:
{critics["vc"]}

Engineer:
{critics["engineer"]}

Ethicist:
{critics["ethicist"]}

User:
{critics["user"]}

Competitor:
{critics["competitor"]}
""".strip()

    return {
        "bias_remover": bias_remover,
        "assumptions": assumptions,
        "vc": vc,
        "engineer": engineer,
        "ethicist": ethicist,
        "user": user,
        "competitor": competitor,
        "final_judge": final_judge,
    }


async def ensure_assistant_id() -> str:
    global ASSISTANT_ID
    if ASSISTANT_ID:
        return ASSISTANT_ID

    # Backboard Quickstart concept: create an assistant once
    assistant = client.createAssistant({
        "name": "Idea Stress Tester",
        "description": (
            "Forced adversarial reasoning system: neutralizes optimism bias, "
            "extracts assumptions, runs 5 persona critics, synthesizes a decisive verdict."
        ),
    })

    # SDK might return assistantId or assistant_id depending on version
    ASSISTANT_ID = getattr(assistant, "assistantId", None) or getattr(assistant, "assistant_id", None)
    if not ASSISTANT_ID:
        raise RuntimeError("Could not read assistantId from Backboard createAssistant response.")
    return ASSISTANT_ID


def run_block(thread_id: str, content: str, llm_provider: str, model_name: str) -> str:
    # Backboard Quickstart concept: addMessage(threadId, {content, llm_provider, model_name, stream:false})
    resp = client.addMessage(thread_id, {
        "content": content,
        "llm_provider": llm_provider,
        "model_name": model_name,
        "stream": False,
    })

    text = getattr(resp, "content", None) or (resp.get("content") if isinstance(resp, dict) else None)
    if not text:
        raise RuntimeError("Backboard returned no content for this block.")
    return str(text).strip()


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "assistantId": ASSISTANT_ID}


@app.post("/stress-test")
async def stress_test(req: StressTestRequest) -> Dict[str, Any]:
    idea = (req.idea or "").strip()
    if not idea:
        raise HTTPException(status_code=400, detail="Missing 'idea' in request body.")

    try:
        assistant_id = await ensure_assistant_id()

        # Backboard: create a thread per request
        thread = client.createThread(assistant_id)
        thread_id = getattr(thread, "threadId", None) or getattr(thread, "thread_id", None)
        if not thread_id:
            raise RuntimeError("Could not read threadId from Backboard createThread response.")

        P = build_prompts(idea)

        # 0) Neutralize
        neutral_idea = run_block(
            thread_id,
            P["bias_remover"],
            MODELS["main"]["llm_provider"],
            MODELS["main"]["model_name"],
        )

        # 1) Assumptions
        assumptions_txt = run_block(
            thread_id,
            P["assumptions"](neutral_idea),
            MODELS["main"]["llm_provider"],
            MODELS["main"]["model_name"],
        )

        # 2–6) Persona critics
        critics = {
            "vc": run_block(thread_id, P["vc"](neutral_idea), MODELS["vc"]["llm_provider"], MODELS["vc"]["model_name"]),
            "engineer": run_block(thread_id, P["engineer"](neutral_idea), MODELS["engineer"]["llm_provider"], MODELS["engineer"]["model_name"]),
            "ethicist": run_block(thread_id, P["ethicist"](neutral_idea), MODELS["ethicist"]["llm_provider"], MODELS["ethicist"]["model_name"]),
            "user": run_block(thread_id, P["user"](neutral_idea), MODELS["user"]["llm_provider"], MODELS["user"]["model_name"]),
            "competitor": run_block(thread_id, P["competitor"](neutral_idea), MODELS["competitor"]["llm_provider"], MODELS["competitor"]["model_name"]),
        }

        # Risk convergence (no extra AI calls)
        risk_signals = compute_risk_signals(critics, threshold=3)

        # 7) Final judge synthesis
        verdict = run_block(
            thread_id,
            P["final_judge"](neutral_idea, assumptions_txt, critics),
            MODELS["main"]["llm_provider"],
            MODELS["main"]["model_name"],
        )

        return {
            "inputIdea": idea,
            "neutralIdea": neutral_idea,
            "assumptions": assumptions_txt,
            "critics": critics,
            "riskSignals": risk_signals,
            "verdict": verdict,
            "meta": {
                "assistantId": assistant_id,
                "threadId": thread_id,
                "modelsUsed": MODELS,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
