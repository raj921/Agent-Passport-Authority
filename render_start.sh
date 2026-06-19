#!/usr/bin/env bash
set -euo pipefail

echo "Starting Agent Passport Authority on port ${PORT:-8000}"

uv run python my_agent.py &
uv run python security_probe.py &
uv run python capability_verifier.py &
uv run python compliance_agent.py &
uv run python listener.py &

exec uv run uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}"
