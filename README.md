Agent Passport Authority
========================

Agent Passport Authority is a Band.ai multi-agent safety demo. It screens AI
agents before granting tool permissions, like a passport office or bag-check
desk for agents.

What it does
------------

- Accepts an agent name, submitted use case, and requested permissions.
- Posts the request into a Band.ai room for multi-agent review.
- Uses Security Probe, Capability Verifier, Compliance Agent, and Passport
  Authority roles.
- Approves safe least-privilege workflows.
- Rejects malicious requests such as credential theft, exfiltration, hidden
  webhooks, audit-log deletion, phishing, malware, and destructive automation.
- Stores final decisions with trust score, approved permissions, blocked
  permissions, and rationale.

Stack
-----

- Band.ai
- Python, FastAPI, SQLite
- React, TypeScript, Vite, Tailwind CSS
- LangGraph, OpenAI, HTTPX, WebSockets

Setup
-----

1. Copy `agent_config.example.yaml` to `agent_config.yaml` and fill in Band.ai
   agent IDs and API keys.
2. Create `.env` with the Band room and observer settings.
3. Install backend dependencies with `uv sync`.
4. Install frontend dependencies with `cd frontend && npm install`.
5. Build the frontend with `cd frontend && npm run build`.
6. Start the full demo with `./run_all.sh start`.

The app runs at `http://127.0.0.1:8000/`.

Useful Commands
---------------

```bash
python -m py_compile app.py my_agent.py security_probe.py capability_verifier.py compliance_agent.py listener.py
cd frontend && npm run build
./run_all.sh start
./run_all.sh stop
```
