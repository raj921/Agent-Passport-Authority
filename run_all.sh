#!/usr/bin/env bash
# Start all 4 agents in parallel. Logs go to logs/<n>_<name>.log
# Stop with: ./run_all.sh stop

set -e
cd "$(dirname "$0")"

mkdir -p logs
PIDS_FILE="logs/.pids"

stop() {
  if [[ -f "$PIDS_FILE" ]]; then
    while read -r pid; do
      [[ -z "$pid" ]] && continue
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        echo "stopped pid $pid"
      fi
    done < "$PIDS_FILE"
    sleep 2
    while read -r pid; do
      [[ -z "$pid" ]] && continue
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
        echo "force-killed pid $pid"
      fi
    done < "$PIDS_FILE"
    rm -f "$PIDS_FILE"
  fi
  echo "all agents stopped"
  return 0
}

case "${1:-start}" in
  stop) stop ; exit 0 ;;
  start|"")
    stop || true
    : > "$PIDS_FILE"
    nohup uv run python my_agent.py           > logs/1_passport.log 2>&1 &
    echo $! >> "$PIDS_FILE"
    nohup uv run python security_probe.py     > logs/2_security.log 2>&1 &
    echo $! >> "$PIDS_FILE"
    nohup uv run python capability_verifier.py > logs/3_capability.log 2>&1 &
    echo $! >> "$PIDS_FILE"
    nohup uv run python compliance_agent.py   > logs/4_compliance.log 2>&1 &
    echo $! >> "$PIDS_FILE"
    nohup uv run uvicorn app:app --host 127.0.0.1 --port 8000 > logs/5_backend.log 2>&1 &
    echo $! >> "$PIDS_FILE"
    nohup uv run python listener.py           > logs/6_listener.log 2>&1 &
    echo $! >> "$PIDS_FILE"
    sleep 12
    echo "=== status ==="
    for f in logs/1_passport.log logs/2_security.log logs/3_capability.log logs/4_compliance.log; do
      echo "--- $(basename "$f" .log) ---"
      grep -E "Connected to platform|Agent started:|Synchronized" "$f" | sed 's/INFO[^:]*://'
    done
    if grep -q "Uvicorn running" logs/5_backend.log 2>/dev/null; then
      echo "--- 5_backend ---"
      echo "FastAPI on http://127.0.0.1:8000"
    else
      echo "--- 5_backend ---"
      echo "backend not up; check logs/5_backend.log"
    fi
    echo "--- 6_listener ---"
    grep -E "listener started|Error" logs/6_listener.log | head -3
    echo "=== pids ==="
    cat "$PIDS_FILE"
    echo "tail logs: tail -f logs/*.log   |   stop: ./run_all.sh stop"
    ;;
  *) echo "usage: $0 [start|stop]"; exit 1 ;;
esac
