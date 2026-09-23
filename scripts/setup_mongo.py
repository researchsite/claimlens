"""
One-time MongoDB setup for ClaimLens.
Creates the 'claimlens' database, 'audits' collection, indexes,
and seeds all pre-computed preset results from cache/*.json.

Usage:
    python scripts/setup_mongo.py           # setup + seed all presets
    python scripts/setup_mongo.py --seed    # seed only (skip if doc already exists)
    python scripts/setup_mongo.py --reset   # drop + recreate + re-seed
"""
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import os
from pymongo import MongoClient, ASCENDING, DESCENDING


CACHE_DIR = Path(__file__).parent.parent / "cache"


def get_db(uri: str):
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")          # fast connectivity check
    return client["claimlens"]


def create_indexes(col) -> None:
    col.create_index([("timestamp", DESCENDING)],       name="by_timestamp")
    col.create_index([("claim", ASCENDING)],             name="by_claim",    unique=True)
    col.create_index([("verdict.verdict", ASCENDING)],  name="by_verdict")
    print("  ✅  Indexes created: by_timestamp, by_claim (unique), by_verdict")


def seed_presets(col, force: bool = False) -> None:
    cache_files = sorted(CACHE_DIR.glob("*.json"))
    if not cache_files:
        print("  ⚠️  No cache files found in cache/ — run precompute_presets.py first")
        return

    inserted = 0
    skipped  = 0
    for path in cache_files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        claim = data["claim"]

        if not force and col.find_one({"claim": claim}):
            print(f"  ⏩  [{path.stem}] already in DB — skipping")
            skipped += 1
            continue

        doc = {
            "claim":       claim,
            "preset_id":   data.get("preset_id", path.stem),
            "timestamp":   datetime.now(timezone.utc),
            "approach_a":  data.get("approach_a", ""),
            "verdict":     data.get("verdict", {}),
            "echo_index":  data.get("echo_index", 0),
            "sub_claims":  data.get("sub_claims", []),
            "grounding":   data.get("grounding", {}),
            "agent_trace": data.get("agent_trace", []),
            "from_cache":  True,
            "total_ms":    data.get("total_ms", 0),
        }

        if force:
            col.replace_one({"claim": claim}, doc, upsert=True)
            action = "upserted"
        else:
            col.insert_one(doc)
            action = "inserted"

        verdict = doc["verdict"]
        print(f"  ✅  [{path.stem}]  {verdict.get('verdict_emoji','')} {verdict.get('verdict_label','')} — {action}")
        inserted += 1

    print(f"\n  Summary: {inserted} inserted/upserted, {skipped} skipped")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed",  action="store_true", help="Seed presets only (skip if exists)")
    parser.add_argument("--reset", action="store_true", help="Drop audits collection, recreate, re-seed")
    args = parser.parse_args()

    uri = os.getenv("MONGODB_URI", "")
    if not uri:
        print("❌  MONGODB_URI not set in .env — aborting")
        sys.exit(1)

    print("\nClaimLens — MongoDB Setup")
    print(f"URI: {uri[:40]}…")
    print("Connecting…")

    db = get_db(uri)
    print("  ✅  Connected to MongoDB Atlas")

    if args.reset:
        db["audits"].drop()
        print("  🗑️   Dropped 'audits' collection")

    col = db["audits"]

    if not args.seed:
        create_indexes(col)

    print("\nSeeding preset cache into MongoDB…")
    seed_presets(col, force=args.reset)

    count = col.count_documents({})
    print(f"\n✅  Done. 'audits' collection now has {count} document(s).")


if __name__ == "__main__":
    main()
