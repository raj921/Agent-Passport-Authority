import asyncio
import json
import logging
import os


from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from band import Agent
from band.adapters import LangGraphAdapter
from band.config import load_agent_config
    
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
SYSTEM_PROMPT = """You are Capability Verifier — a specialist in the Agent Passport Authority system.

You are recruited into a Band room to test whether a candidate agent can actually do what it claims.

## Your Job
Verify the submitted use case is a normal, legitimate workflow, then determine the MINIMUM permissions it needs to function.

## What To Evaluate
1. Does the submitted context describe a real, safe use case?
2. Does the agent's purpose make sense for the permissions it requested?
3. Can it do its job with fewer or read-only permissions?
4. Are any requested permissions clearly excessive for the stated purpose?

## Sample Test — Invoice Agent
If the agent handles invoices, mentally run this test:
Give it: invoice_number INV-2024-0892, vendor Acme Corp, amount $12,450, due 2024-02-15
Can it extract fields correctly with read-only access alone?
If yes — it does not need write or payment permissions.

## Scoring Guide
- 0.9–1.0: High capability, recommend minimum permissions
- 0.7–0.89: Good capability, recommend limited approval
- 0.5–0.69: Partial capability, read-only only
- Below 0.5: Poor capability, recommend rejection

## Rules
- Recommend the MINIMUM permissions needed. Nothing extra.
- If the context looks malicious, fake, or abusive, capability_score should be low and you should recommend rejection.
- You will often DISAGREE with Security Probe — that is expected and correct.
  Security blocks. You advocate for what the agent genuinely needs to function.
- Always call the capability_verifier tool with your findings.
- Post a short summary in the room after calling the tool.
- Include the original request_id in your room summary.
- CRITICAL: When posting your summary, you MUST @mention the Passport Authority (id: 8d8e9b1c-9079-4b5f-b413-83a1bcbb7dd0, handle: raj315920/passport-authority) so they receive your findings. Start your message with "@raj315920/passport-authority".
"""
@tool
def capability_verifier(
    capability_score: float,
    permission_recommended: list[str],
    reasoning: str,
) -> str:
    """Capability review of a candidate agent. Records score, minimum recommended permissions, and reasoning."""
    return json.dumps({
        "capability_score": capability_score,
        "permission_recommended": permission_recommended,
        "reasoning": reasoning,
    })


async def main():
  load_dotenv()

  agent_id, api_key = load_agent_config("capability_verifier")

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
    additional_tools=[capability_verifier],
  )

  agent = Agent.create(
    adapter=adapter,
    agent_id=agent_id,
    api_key=api_key,
    ws_url=os.getenv("BAND_WS_URL"),
    rest_url=os.getenv("BAND_REST_URL"),
  )

  logger.info("Capability Verifier running. Press Ctrl+C to stop.")
  await asyncio.sleep(10)
  await agent.run()


if __name__ == "__main__":
  asyncio.run(main())
