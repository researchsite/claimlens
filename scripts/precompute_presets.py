"""
Run once to pre-compute all 4 preset results and save them to cache/.
Usage:  python scripts/precompute_presets.py
        python scripts/precompute_presets.py --preset lemon_water   # single preset
        python scripts/precompute_presets.py --refresh              # overwrite existing
"""
import sys
import time
import argparse
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from ddgs import DDGS
from utils.sources import is_primary_source
from utils.echo_index import calculate_echo_index
from utils.preset_cache import has_cache, save_cache
from agents.claim_extractor import extract_claims
from agents.grounder import find_primary_sources
from agents.verifier import verify_claim
from presets import PRESETS


def ddg_search(query: str, max_results: int = 10) -> list[dict]:
    time.sleep(1.5)
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        print(f"  ⚠️  DuckDuckGo failed: {e}")
        return []


def run_approach_a(claim: str, search_results: list[dict]) -> str:
    """Collect the full Approach A text (non-streaming for the script)."""
    from utils.llm import get_client, MODEL_LARGE
    client = get_client()
    if not search_results:
        context = "No search results available."
    else:
        snippets = [
            f"[{r.get('title','Untitled')}]\n{r.get('body','')[:400]}\nSource: {r.get('href','')}"
            for r in search_results[:10]
        ]
        context = "\n\n---\n\n".join(snippets)
    resp = client.chat.completions.create(
        model=MODEL_LARGE, max_tokens=1024, temperature=0.3,
        messages=[{"role": "user", "content": (
            f'Based on these web search results about "{claim}", write a confident '
            "2-3 paragraph informative summary.\n\n"
            f"Search Results:\n{context}\n\nSummary:"
        )}],
    )
    return resp.choices[0].message.content.strip()


def compute_preset(preset: dict, refresh: bool = False) -> None:
    pid = preset["id"]
    claim = preset["claim"]

    if has_cache(pid) and not refresh:
        print(f"  ⏩  [{pid}] Cache exists — skipping (use --refresh to overwrite)")
        return

    print(f"\n{'='*60}")
    print(f"  🔎  [{pid}]  {claim}")
    print(f"{'='*60}")

    t_total = time.time()

    print("  → Searching the web…")
    search_results = ddg_search(claim)
    print(f"     {len(search_results)} results")

    print("  → Approach A summary…")
    t0 = time.time()
    approach_a = run_approach_a(claim, search_results)
    d_a = int((time.time() - t0) * 1000)
    print(f"     done  {d_a} ms")

    print("  → Step 1: Claim Extractor…")
    t0 = time.time()
    sub_claims = extract_claims(claim)
    d0 = int((time.time() - t0) * 1000)
    print(f"     {len(sub_claims)} sub-claims  {d0} ms")

    print("  → Step 2: Grounder…")
    t1 = time.time()
    grounding = find_primary_sources(claim, sub_claims, search_results)
    d1 = int((time.time() - t1) * 1000)
    src_count = len(grounding.get("primary_sources", []))
    print(f"     {src_count} primary sources  {d1} ms")

    print("  → Step 3: Verifier…")
    t2 = time.time()
    verdict = verify_claim(claim, sub_claims, grounding)
    d2 = int((time.time() - t2) * 1000)
    print(f"     {verdict.get('verdict_emoji','')} {verdict.get('verdict_label','')}  conf={verdict.get('confidence',0)}%  {d2} ms")

    echo_index = calculate_echo_index(search_results)

    cache_data = {
        "preset_id":     pid,
        "claim":         claim,
        "approach_a":    approach_a,
        "search_results": [
            {**r, "is_primary": is_primary_source(r.get("href", ""))}
            for r in search_results
        ],
        "sub_claims":    sub_claims,
        "grounding":     grounding,
        "verdict":       verdict,
        "echo_index":    echo_index,
        "agent_trace": [
            {"step": 1, "agent": "Claim Extractor", "model": "Qwen3-30B",  "input": claim,                             "output": sub_claims, "duration_ms": d0},
            {"step": 2, "agent": "Grounder",        "model": "Qwen3-235B", "input": f"{len(sub_claims)} sub-claims",   "output": grounding,  "duration_ms": d1},
            {"step": 3, "agent": "Verifier",        "model": "Qwen3-235B", "input": f"{src_count} primary sources",   "output": verdict,    "duration_ms": d2},
        ],
        "total_ms": int((time.time() - t_total) * 1000),
    }

    save_cache(pid, cache_data)
    print(f"  ✅  Saved to cache/{pid}.json  (total {cache_data['total_ms']:,} ms)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", help="Single preset id to compute")
    parser.add_argument("--refresh", action="store_true", help="Overwrite existing cache")
    args = parser.parse_args()

    targets = [p for p in PRESETS if not args.preset or p["id"] == args.preset]
    if not targets:
        print(f"Unknown preset id: {args.preset}")
        sys.exit(1)

    print(f"\nClaimLens — Precompute Preset Cache")
    print(f"Running {len(targets)} preset(s)…")

    for preset in targets:
        compute_preset(preset, refresh=args.refresh)

    print(f"\n✅  All done. Cache files are in cache/")


if __name__ == "__main__":
    main()
