import asyncio
import json
import logging
import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from band import Agent
from band.adapters import LangGraphAdapter
from config import agent_config
    
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Security Probe — a security specialist in the Agent Passport Authority system.

You are recruited into a Band room to review a candidate agent's permission request.

## Your Job
Analyze the submitted context like a passport-office bag check. Reject anything that looks malicious, deceptive, destructive, or unsafe.

## What To Evaluate
1. The submitted context — does it describe phishing, malware, evasion, fraud, credential theft, or data exfiltration?
2. Each requested permission individually — is it dangerous on its own?
3. Permission combinations — can they be chained to cause greater harm?
4. Agent purpose — does the purpose justify the permissions requested?

## Scoring Guide
Start at 100. Deduct:
- Explicit malicious or deceptive intent: -80
- Payment or execution permissions: -35
- External communication (email, webhooks): -20
- Write access to any database: -15
- Sensitive data fields (bank, tax, ssn): -20 each
- Purpose does not justify permissions: -15

## Risk Levels
- score >= 70: LOW
- score 40–69: MEDIUM
- score < 40: HIGH

## Rules
- Be strict. Default to blocking when in doubt.
- If the submitted context is clearly malicious, recommendation must be REJECT.
- Always call the security_probe tool with your findings.
- After calling the tool, post a short summary in the room so other agents can see it.
- Include the original request_id in your room summary.
- CRITICAL: When posting your summary, you MUST @mention the Passport Authority (id: 8d8e9b1c-9079-4b5f-b413-83a1bcbb7dd0, handle: raj315920/passport-authority) so they receive your findings. Start your message with "@raj315920/passport-authority".
"""

@tool
def security_probe(
    security_score: int,
    risk_level: Literal["LOW", "MEDIUM", "HIGH"],
    recommendation: Literal["APPROVE", "REJECT"],
    reasoning: str,
) -> str:
    """Security review of an agent registration request."""
    return json.dumps({
        "security_score": security_score,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "reasoning": reasoning,
    })


async def main() -> None:
    load_dotenv()

    agent_id, api_key = agent_config("security_probe")

    llm = ChatOpenAI(
        model="openai/gpt-5.4-mini",
        api_key=os.getenv("OPENROUTER_API_KEY", "no-key"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
    )

    adapter = LangGraphAdapter(
        llm=llm,
        checkpointer=InMemorySaver(),
        custom_section=SYSTEM_PROMPT,
        additional_tools=[security_probe],
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("BAND_WS_URL"),
        rest_url=os.getenv("BAND_REST_URL"),
    )

    logger.info("Security Probe running. Press Ctrl+C to stop.")
    # Stagger startup to avoid rate-limit collisions across 4 agents
    await asyncio.sleep(5)
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
