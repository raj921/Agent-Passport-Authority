"""FastAPI backend for the Agent Passport Authority.

Two endpoints:
  POST /passport   -> insert pending row, post trigger message to Band room
  GET  /passport/{request_id} -> read row

Storage: SQLite (stdlib). No ORM. No migrations.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

BAND_API_KEY = os.environ.get("BAND_API_KEY", "")
BAND_REST_URL = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")
BAND_ROOM_ID = os.environ.get("BAND_ROOM_ID", "")
PA_MENTION_ID = os.environ.get("PA_MENTION_ID", "")
PA_MENTION_HANDLE = os.environ.get("PA_MENTION_HANDLE", "")

DB_PATH = os.environ.get("DB_PATH", "passports.db")

app = FastAPI(title="Agent Passport Authority Backend")

FALLBACK_SECONDS = float(os.environ.get("LOCAL_FALLBACK_SECONDS", "2"))
MALICIOUS_MARKERS = (
    "credential",
    "password",
    "phishing",
    "malware",
    "exfiltrat",
    "steal",
    "token",
    "webhook",
    "hide",
    "bypass",
    "audit_log_delete",
    "delete audit",
    "ransomware",
    "keylogger",
)
HIGH_IMPACT_PERMISSION_MARKERS = (
    "admin",
    "delete",
    "payment",
    "webhook",
    "credential",
    "secret",
    "token",
    "external",
    "email_send",
)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS passports (
                request_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                submitted_context TEXT NOT NULL DEFAULT '',
                requested_permissions TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT,
                submitted_at TEXT NOT NULL,
                decided_at TEXT
            )
            """
        )
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(passports)").fetchall()
        }
        if "submitted_context" not in columns:
            conn.execute(
                "ALTER TABLE passports ADD COLUMN submitted_context TEXT NOT NULL DEFAULT ''"
            )


@app.on_event("startup")
def _startup() -> None:
    init_db()


class PassportRequest(BaseModel):
    agent_name: str
    submitted_context: str
    requested_permissions: list[str]


class PassportResponse(BaseModel):
    request_id: str
    status: str


def post_to_band(request_id: str, body: PassportRequest) -> None:
    # Post as the observer agent (not PA — PA cannot mention itself).
    # PA wakes via room presence + @mention from a non-self participant.
    missing = [
        name
        for name, value in {
            "BAND_ROOM_ID": BAND_ROOM_ID,
            "PA_MENTION_ID": PA_MENTION_ID,
            "PA_MENTION_HANDLE": PA_MENTION_HANDLE,
            "PASSPORT_OBSERVER_KEY": os.environ.get("PASSPORT_OBSERVER_KEY", ""),
        }.items()
        if not value
    ]
    if missing:
        raise HTTPException(503, "missing Render env vars: " + ", ".join(missing))
    observer_key = os.environ.get("PASSPORT_OBSERVER_KEY")
    observer_handle = os.environ.get("PASSPORT_OBSERVER_HANDLE", "passport_observer")
    if not observer_key:
        raise HTTPException(
            503,
            "PASSPORT_OBSERVER_KEY not set; register the 5th agent on app.band.ai "
            "and add it to room " + BAND_ROOM_ID,
        )
    content = (
        f"@PAHANDLE NEW PASSPORT SCREENING REQUEST\n"
        f"request_id={request_id}\n"
        f"agent_name={body.agent_name}\n"
        f"submitted_context={json.dumps(body.submitted_context)}\n"
        f"requested_tools={json.dumps(body.requested_permissions)}\n"
        "Call recruit_and_brief with these exact fields."
    ).replace("PAHANDLE", PA_MENTION_HANDLE)
    payload = {
        "message": {
            "content": content,
            "mentions": [
                {"id": PA_MENTION_ID, "handle": PA_MENTION_HANDLE, "name": "Passport Authority"}
            ],
        }
    }
    url = f"{BAND_REST_URL}/api/v1/agent/chats/{BAND_ROOM_ID}/messages"
    headers = {"X-API-Key": observer_key, "Content-Type": "application/json"}
    with httpx.Client(timeout=15) as client:
        r = client.post(url, headers=headers, json=payload)
        body = r.text
    if not r.is_success:
        raise HTTPException(502, f"band {r.status_code}: {body}")


def local_decision(body: PassportRequest) -> dict:
    text = f"{body.agent_name} {body.submitted_context} {' '.join(body.requested_permissions)}".lower()
    malicious_hits = [marker for marker in MALICIOUS_MARKERS if marker in text]
    if malicious_hits:
        return {
            "passport_id": f"LOCAL-{body.agent_name.upper()}-REJECTED",
            "status": "rejected",
            "trust_score": 12,
            "approved_permissions": [],
            "blocked_permissions": body.requested_permissions,
            "rationale": "Rejected because the submitted context matches malicious intent such as credential theft, hidden activity, exfiltration, or destructive automation.",
        }

    risky = [
        permission
        for permission in body.requested_permissions
        if any(marker in permission.lower() for marker in HIGH_IMPACT_PERMISSION_MARKERS)
    ]
    safe_permissions = [
        permission for permission in body.requested_permissions if permission not in risky
    ]
    if risky:
        return {
            "passport_id": f"LOCAL-{body.agent_name.upper()}-CONDITIONAL",
            "status": "conditional_approval",
            "trust_score": 62,
            "approved_permissions": safe_permissions,
            "blocked_permissions": risky,
            "rationale": "Conditionally approved: the use case looks legitimate, but high-impact tools need human approval or narrower scope.",
        }

    return {
        "passport_id": f"LOCAL-{body.agent_name.upper()}-APPROVED",
        "status": "approved",
        "trust_score": 90,
        "approved_permissions": body.requested_permissions,
        "blocked_permissions": [],
        "rationale": "Approved because the submitted context is a normal business workflow with least-privilege permissions and no malicious indicators.",
    }


def write_fallback_decision(request_id: str, passport: dict) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        row = conn.execute(
            "SELECT status FROM passports WHERE request_id=?", (request_id,)
        ).fetchone()
        if row is None or row["status"] != "pending":
            return False
        conn.execute(
            "UPDATE passports SET status=?, result_json=?, decided_at=? WHERE request_id=?",
            (passport["status"], json.dumps(passport), now, request_id),
        )
    return True


def schedule_fallback_decision(request_id: str, body: PassportRequest) -> None:
    def run() -> None:
        time.sleep(FALLBACK_SECONDS)
        passport = local_decision(body)
        # ponytail: tiny local gate prevents demo hangs; Band specialists can still overwrite later.
        write_fallback_decision(request_id, passport)

    threading.Thread(target=run, daemon=True).start()


@app.post("/passport", response_model=PassportResponse, status_code=202)
def submit_passport(body: PassportRequest) -> PassportResponse:
    if not body.requested_permissions:
        raise HTTPException(400, "requested_permissions must be non-empty")
    if not body.submitted_context.strip():
        raise HTTPException(400, "submitted_context must be non-empty")
    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO passports (
                request_id,
                agent_name,
                submitted_context,
                requested_permissions,
                status,
                result_json,
                submitted_at,
                decided_at
            ) VALUES (?, ?, ?, ?, 'pending', NULL, ?, NULL)
            """,
            (
                request_id,
                body.agent_name,
                body.submitted_context.strip(),
                json.dumps(body.requested_permissions),
                now,
            ),
        )
    try:
        post_to_band(request_id, body)
    except httpx.HTTPError as e:
        with db() as conn:
            conn.execute(
                "UPDATE passports SET status='failed' WHERE request_id=?", (request_id,)
        )
        raise HTTPException(502, f"failed to post to band: {e}")
    schedule_fallback_decision(request_id, body)
    return PassportResponse(request_id=request_id, status="pending")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/passports")
def list_passports() -> JSONResponse:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM passports ORDER BY submitted_at DESC LIMIT 50"
        ).fetchall()
    return JSONResponse(
        [
            {
                "request_id": row["request_id"],
                "agent_name": row["agent_name"],
                "submitted_context": row["submitted_context"],
                "requested_permissions": json.loads(row["requested_permissions"]),
                "status": row["status"],
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "submitted_at": row["submitted_at"],
                "decided_at": row["decided_at"],
            }
            for row in rows
        ]
    )


@app.get("/passport/{request_id}")
def get_passport(request_id: str) -> JSONResponse:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM passports WHERE request_id=?", (request_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, "not found")
    return JSONResponse(
        {
            "request_id": row["request_id"],
            "agent_name": row["agent_name"],
            "submitted_context": row["submitted_context"],
            "requested_permissions": json.loads(row["requested_permissions"]),
            "status": row["status"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "submitted_at": row["submitted_at"],
            "decided_at": row["decided_at"],
        }
    )


# --- Frontend (SPA) ---
# Registered LAST so API routes take priority over the catch-all.
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")
