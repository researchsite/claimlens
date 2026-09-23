"""
Optional MongoDB persistence for ClaimLens audit results.
Activated only when MONGODB_URI is present in the environment.
Falls back to no-op silently when not configured.
"""
import os
from datetime import datetime, timezone

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is not None:
        return _db
    uri = os.getenv("MONGODB_URI", "")
    if not uri:
        return None
    try:
        from pymongo import MongoClient
        _client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        _db = _client["claimlens"]
        return _db
    except Exception:
        return None


def save_audit(claim: str, result: dict, approach_a: str = "") -> str | None:
    """
    Persist an audit result. Returns the inserted _id as string, or None if
    MongoDB is not configured or the insert fails.
    """
    db = _get_db()
    if db is None:
        return None
    try:
        doc = {
            "claim":        claim,
            "timestamp":    datetime.now(timezone.utc),
            "approach_a":   approach_a,
            "verdict":      result.get("verdict", {}),
            "echo_index":   result.get("echo_index", 0),
            "sub_claims":   result.get("sub_claims", []),
            "grounding":    result.get("grounding", {}),
            "agent_trace":  result.get("agent_trace", []),
            "from_cache":   result.get("from_cache", False),
            "preset_id":    result.get("preset_id", ""),
        }
        # upsert: update existing record for the same claim (handles preset re-views
        # and duplicate custom queries gracefully without unique-key errors)
        res = db["audits"].replace_one({"claim": claim}, doc, upsert=True)
        oid = res.upserted_id or db["audits"].find_one({"claim": claim}, {"_id": 1})["_id"]
        return str(oid)
    except Exception:
        return None


def get_recent_audits(limit: int = 20) -> list[dict]:
    """Return the most recent `limit` audits, newest first."""
    db = _get_db()
    if db is None:
        return []
    try:
        docs = list(db["audits"].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit))
        return docs
    except Exception:
        return []


def is_connected() -> bool:
    return _get_db() is not None
