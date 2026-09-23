from agents.claim_extractor import extract_claims
from agents.grounder import find_primary_sources
from agents.verifier import verify_claim
from utils.echo_index import calculate_echo_index


def run_audit(claim: str, search_results: list[dict]) -> dict:
    """
    Full 3-agent audit pipeline: Extractor → Grounder → Verifier.
    Returns verdict + intermediate results for display.
    """
    sub_claims = extract_claims(claim)
    grounding = find_primary_sources(claim, sub_claims, search_results)
    verdict = verify_claim(claim, sub_claims, grounding)
    echo_index = calculate_echo_index(search_results)

    return {
        "sub_claims": sub_claims,
        "grounding": grounding,
        "verdict": verdict,
        "echo_index": echo_index,
    }
