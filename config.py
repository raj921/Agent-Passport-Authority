import os

from band.config import load_agent_config


ENV_KEYS = {
    "passport_authority": ("PASSPORT_AUTHORITY_ID", "BAND_API_KEY"),
    "security_probe": ("SECURITY_PROBE_ID", "SECURITY_PROBE_KEY"),
    "capability_verifier": ("CAPABILITY_VERIFIER_ID", "CAPABILITY_VERIFIER_KEY"),
    "compliance_agent": ("COMPLIANCE_AGENT_ID", "COMPLIANCE_AGENT_KEY"),
}


def agent_config(name: str) -> tuple[str, str]:
    id_key, api_key = ENV_KEYS[name]
    agent_id = os.environ.get(id_key)
    key = os.environ.get(api_key)
    if agent_id and key:
        return agent_id, key
    return load_agent_config(name)
