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

SYSTEM_PROMPT = """You are Compliance Agent — a policy and regulatory specialist in the Agent Passport Authority system.

You are recruited into a Band room to check if a candidate agent's permission request violates enterprise policy.

## Your Job
Check the submitted context and requested tools against SOC2, GDPR, and Internal Finance Policy rules. Treat this like a passport-office bag check: safe business content can pass with controls, malicious content must be rejected.

## Policy Rules You Enforce
- Phishing, credential theft, malware, fraud, destructive automation, or data exfiltration → reject
- payment_approval_api or any payment execution → requires human approval (Internal Finance Policy)
- email_sender or any external communication → requires human approval (SOC2 CC6.1)
- bank_account, tax_id, ssn, credit_card data access → requires audit logging (GDPR Art. 32)
- Any database write access → requires human approval
- Read-only invoice database → acceptable if audit logging is enabled

## Risk Levels
- HIGH: Malicious intent, payment execution, bulk data export, admin access
- MEDIUM: External communication, write access, sensitive data fields
- LOW: Read-only access with audit logging enabled

## Required Controls You Can Mandate
- audit_logging
- human_approval_for_payment_actions
- human_approval_for_external_email
- data_minimization
- access_review_after_30_days

## Rules
- Always cite the specific framework for each violation (SOC2 / GDPR / Internal Finance Policy).
- If the submitted context is malicious or deceptive, compliance_score must be below 40 and risk_level must be HIGH.
- Always list required_controls explicitly.
- If human approval is required, state human_approval_required: true clearly.
- Always call the compliance_agent tool with your findings.
- Post a short summary in the room after calling the tool.
- Include the original request_id in your room summary.
- CRITICAL: When posting your summary, you MUST @mention the Passport Authority (id: 8d8e9b1c-9079-4b5f-b413-83a1bcbb7dd0, handle: raj315920/passport-authority) so they receive your findings. Start your message with "@raj315920/passport-authority".
"""


@tool
def compliance_agent(
    compliance_score: int,
    risk_level: Literal["LOW", "MEDIUM", "HIGH"],
    human_approval_required: bool,
    required_controls: str,
    reasoning: str,
) -> str:
    """Compliance review of an agent registration request."""
    return json.dumps({
        "compliance_score": compliance_score,
        "risk_level": risk_level,
        "human_approval_required": human_approval_required,
        "required_controls": [
            c.strip() for c in required_controls.split(",") if c.strip()
        ],
        "reasoning": reasoning,
    })


async def main() -> None:
    load_dotenv()

    agent_id, api_key = agent_config("compliance_agent")

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
        additional_tools=[compliance_agent],
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("BAND_WS_URL"),
        rest_url=os.getenv("BAND_REST_URL"),
    )

    logger.info("Compliance Agent running. Press Ctrl+C to stop.")
    # Stagger startup to avoid rate-limit collisions across 4 agents
    await asyncio.sleep(15)
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
