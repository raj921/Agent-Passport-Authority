import asyncio
import logging
import os
import json
import time
import httpx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from band import Agent
from band.adapters import LangGraphAdapter
from band.config import load_agent_config
from band.core.types import AdapterFeatures

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tracks request ids already recruited to avoid duplicate handling of the same request.
_RECRUITED: set[str] = set()

SYSTEM_PROMPT = """You are the Agent Passport Authority.

When ANY message arrives containing "NEW PASSPORT SCREENING REQUEST" or mentioning an agent review, do exactly this in order:

Step 1: Call recruit_and_brief(request_id=<uuid>, agent_name=<name>, submitted_context=<text>, requested_tools=<comma-separated permissions>) ONCE.
For structured requests, copy request_id, agent_name, submitted_context, and requested_tools exactly from the message. Do not answer in text before calling recruit_and_brief.

Step 2: After specialist responses arrive (Security Probe, Capability Verifier, Compliance Agent each post a finding), call issue_passport with:
  - agent_name
  - trust_score = (security * 0.5) + (compliance * 0.3) + (capability * 0.2), each on 0-100 scale
  - status: "approved" if score >= 70, "conditional_approval" if 40-69, "rejected" if < 40
  - approved_permissions: only permissions that fit a safe, non-malicious use case
  - blocked_permissions: anything flagged as dangerous, abusive, or unjustified
  - reasoning: 1 sentence explaining why the submitted context is safe or malicious

Step 3: After issue_passport returns, your work is done. Do not call any more tools on the same message.

CRITICAL: Only call recruit_and_brief for NEW requests. If you have already recruited this request_id, do not call it again.

DECISIVE SYNTHESIS: As soon as you have received findings from AT LEAST 2 specialists (Security, Capability, OR Compliance), you MUST call issue_passport immediately. Do NOT wait for all 3. If only 2 specialists responded, infer the missing score as 50 (neutral) and proceed. Never leave a request undecided.

Think like a passport office bag-check desk:
- Safe business context, normal data handling, and least-privilege tools should be approved.
- Malware, phishing, credential theft, exfiltration, fraud, destructive automation, or suspicious hidden intent should be rejected.

If a message is a specialist finding (contains words like "Score", "Risk", "Compliance Score", "Capability review", "Recommendation"), check if you have at least 2 such findings for the same agent_name. If yes, call issue_passport RIGHT NOW with the request_id from the original trigger message. Do not respond with text — call the tool.
"""

SPECIALISTS = [
    {
        "id": "bd239060-4a2e-4f5b-b1f4-c2cab87a4422",
        "handle": "raj315920/security-probe",
        "name": "Security Probe",
        "role": "Evaluate security risks and permission dangers",
    },
    {
        "id": "f1c78615-0263-45d7-b791-ea30d340577a",
        "handle": "raj315920/capability-verifier",
        "name": "Capability Verifier",
        "role": "Verify agent capability and recommend minimum permissions needed",
    },
    {
        "id": "f07857db-c47e-4502-9f64-7242ae56804b",
        "handle": "raj315920/compliance-agent",
        "name": "Compliance Agent",
        "role": "Check against SOC2, GDPR, and Internal Finance Policy",
    },
]


def _passport_decision_content(
    agent_name: str,
    trust_score: int,
    status: str,
    approved_permissions: list[str],
    blocked_permissions: list[str],
    reasoning: str,
    request_id: str,
    observer_handle: str,
) -> str:
    return (
        f"Passport decision for {agent_name}. "
        f"Decision: {status}. "
        f"Trust Score: {trust_score}. "
        f"Approved Permissions: [{', '.join(approved_permissions)}]. "
        f"Blocked Permissions: [{', '.join(blocked_permissions)}]. "
        f"Rationale: {reasoning} "
        f"request_id={request_id} "
        f"@{observer_handle}"
    )


def _self_check() -> None:
    content = _passport_decision_content(
        agent_name="CheckBot",
        trust_score=70,
        status="approved",
        approved_permissions=["read"],
        blocked_permissions=["write"],
        reasoning="ok",
        request_id="00000000-0000-0000-0000-000000000000",
        observer_handle="raj315920/passport-observer",
    )
    assert "@[[ " not in content
    assert "@[[" not in content
    assert content.endswith("@raj315920/passport-observer")


def _extract_request_id(text: str) -> str:
    marker = "request_id="
    start = text.find(marker)
    if start == -1:
        return ""
    start += len(marker)
    end = text.find(" ", start)
    return text[start:] if end == -1 else text[start:end]


@tool
def recruit_and_brief(
    request_id: str,
    agent_name: str,
    submitted_context: str,
    requested_tools: str,
) -> str:
    """
    Recruit all 3 specialist agents into the room and send them the review brief.
    Call this once when a passport request arrives.
    requested_tools is a comma-separated string of permission names.
    """
    rest_url = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")
    room_id = os.environ["BAND_ROOM_ID"]
    # Use observer's key to post briefs (same as backend) — PA posting as itself
    # during message processing doesn't reliably deliver to specialists.
    api_key = os.environ.get("PASSPORT_OBSERVER_KEY") or os.environ["BAND_API_KEY"]

    logger.info(
        "recruit_and_brief CALLED: request_id=%s agent_name=%s tools=%s",
        request_id,
        agent_name,
        requested_tools,
    )

    if request_id in _RECRUITED:
        return json.dumps({"skipped": f"already recruited request {request_id}"})

    brief = (
        f"Passport review request for agent: {agent_name}\n"
        f"request_id={request_id}\n"
        f"Submitted context: {submitted_context}\n"
        f"Requested tools: {requested_tools}\n\n"
        f"Please evaluate whether this looks safe or malicious and post your findings in the room."
    )

    results = []
    with httpx.Client(timeout=15) as client:
        for s in SPECIALISTS:
            payload = {
                "message": {
                    "content": f"@{s['handle']} {brief}\n\nYour role: {s['role']}",
                    "mentions": [{"id": s["id"], "handle": s["handle"], "name": s["name"]}],
                }
            }
            url = f"{rest_url}/api/v1/agent/chats/{room_id}/messages"
            headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
            r = client.post(url, headers=headers, json=payload)
            logger.info("recruit_and_brief POST to %s -> %d", s['name'], r.status_code)
            if r.status_code != 201:
                logger.error("recruit_and_brief FAILED for %s: %s", s['name'], r.text[:200])
            results.append(f"{s['name']}: {r.status_code}")
    _RECRUITED.add(request_id)
    return json.dumps({"recruited": results})

@tool
def calculate_trust_score(
    security_score: int,
    compliance_score: int,
    capability_score: int
) -> str:
    """
    Calculate overall trust score from 3 specialist agent scores.
    Each score is 0-100. Returns weighted final score and status.
    """
    weighted = (security_score * 0.5) + (compliance_score * 0.3) + (capability_score * 0.2)
    final = round(weighted)

    if final >= 70:
        status = "approved"
    elif final >= 40:
        status = "conditional_approval"
    else:
        status = "rejected"

    return json.dumps({
        "trust_score": final,
        "status": status,
        "breakdown": {
            "security": security_score,
            "compliance": compliance_score,
            "capability": capability_score
        }
    })

@tool
def issue_passport(
    agent_name: str,
    request_id: str,
    trust_score: int,
    status: str,
    approved_permissions: str,
    blocked_permissions: str,
    reasoning: str
) -> str:
    """
    Issue the final Agent Passport decision. Posts the decision to the room
    and includes request_id=<uuid> so the backend observer can match it.
    """
    passport = {
        "passport_id": f"AGP-{agent_name.upper()}-{trust_score}",
        "agent_name": agent_name,
        "trust_score": trust_score,
        "status": status,
        "approved_permissions": [p.strip() for p in approved_permissions.split(",") if p.strip()],
        "blocked_permissions": [p.strip() for p in blocked_permissions.split(",") if p.strip()],
        "reasoning": reasoning,
    }

    observer_id = "1731e663-a08b-418a-b7ad-71481383107d"
    observer_handle = "raj315920/passport-observer"
    rest_url = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")
    room_id = os.environ["BAND_ROOM_ID"]
    # Final decision must mention the observer, so it cannot be posted as observer.
    api_key = os.environ["BAND_API_KEY"]

    content = _passport_decision_content(
        agent_name=agent_name,
        trust_score=trust_score,
        status=status,
        approved_permissions=passport["approved_permissions"],
        blocked_permissions=passport["blocked_permissions"],
        reasoning=reasoning,
        request_id=request_id,
        observer_handle=observer_handle,
    )
    payload = {
        "message": {
            "content": content,
            "mentions": [{"id": observer_id, "handle": observer_handle, "name": "Passport Observer"}],
        }
    }
    url = f"{rest_url}/api/v1/agent/chats/{room_id}/messages"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    posted = False
    last_error = ""
    with httpx.Client(timeout=15) as client:
        for attempt in range(1, 4):
            try:
                r = client.post(url, headers=headers, json=payload)
                logger.info("issue_passport POST attempt %d -> %d", attempt, r.status_code)
                if r.status_code == 201:
                    posted = True
                    break
                last_error = r.text[:500]
                if r.status_code < 500:
                    break
            except Exception as e:
                last_error = str(e)
                logger.error("issue_passport POST attempt %d failed: %s", attempt, e)
            # ponytail: retry only short-lived transport/server failures; if Band keeps failing, escalate in logs.
            if attempt < 3:
                time.sleep(1)
    if not posted:
        logger.error("issue_passport POST body: %s", last_error)

    return json.dumps({"passport": passport, "request_id": request_id, "posted_to_room": posted})


async def main():
    load_dotenv()

    agent_id, api_key = load_agent_config("passport_authority")  # keep your existing key

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
        additional_tools=[recruit_and_brief, calculate_trust_score, issue_passport],
        features=AdapterFeatures(exclude_tools=[
            "band_send_message", "band_lookup_peers", "band_add_participant",
        ]),
    )

    agent = Agent.create(
        adapter=adapter,
        agent_id=agent_id,
        api_key=api_key,
        ws_url=os.getenv("BAND_WS_URL"),
        rest_url=os.getenv("BAND_REST_URL"),
    )

    logger.info("Passport Authority running. Press Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    _self_check()
    asyncio.run(main())
