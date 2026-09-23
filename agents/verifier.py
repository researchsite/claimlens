import json
from utils.llm import get_client, MODEL_LARGE

VERDICT_META = {
    "verified":    ("🟢", "Verified Real"),
    "exaggerated": ("🟡", "Exaggerated / Unverifiable"),
    "fabricated":  ("🔴", "Fabricated Hoax"),
}


def verify_claim(original_claim: str, sub_claims: list[str], grounding: dict) -> dict:
    client = get_client()
    sources = grounding.get("primary_sources", [])
    notes = grounding.get("notes", "No notes.")

    src_text = "\n".join(
        f"• {s.get('title','')} ({s.get('domain_type','')}): {s.get('relevant_quote','')} [supports={s.get('supports_claim',False)}]"
        for s in sources
    ) if sources else "No primary sources found."

    resp = client.chat.completions.create(
        model=MODEL_LARGE,
        max_tokens=2048,
        temperature=0.1,
        messages=[
            {"role": "system", "content": (
                "You are a conservative fact-checker.\n"
                "- 'verified': Primary sources CONFIRM the claim.\n"
                "- 'exaggerated': Claim overstates evidence, OR no primary sources found.\n"
                "- 'fabricated': Primary sources DIRECTLY CONTRADICT the claim.\n"
                "NEVER call 'fabricated' just because evidence is absent — use 'exaggerated'.\n"
                "Output ONLY valid JSON, no markdown."
            )},
            {"role": "user", "content": f"""Fact-check: "{original_claim}"

Sub-claims:
{chr(10).join(f"- {c}" for c in sub_claims)}

Primary sources:
{src_text}

Notes: {notes}

JSON only:
{{
    "verdict": "verified|exaggerated|fabricated",
    "confidence": 85,
    "rewritten_claim": "Accurate 1-2 sentence version based only on found evidence",
    "reasoning": "2-3 sentences explaining this verdict",
    "key_evidence": "Most important piece of evidence"
}}"""},
        ],
    )
    text = resp.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {"verdict": "exaggerated", "confidence": 30,
                  "rewritten_claim": "Unable to verify.", "reasoning": "Parsing error.", "key_evidence": "N/A"}

    # Normalize confidence: model sometimes returns 0-1 float instead of 0-100 int
    conf = result.get("confidence", 50)
    if isinstance(conf, float) and conf <= 1.0:
        conf = int(conf * 100)
    result["confidence"] = max(0, min(100, int(conf)))

    key = result.get("verdict", "exaggerated")
    emoji, label = VERDICT_META.get(key, VERDICT_META["exaggerated"])
    result["verdict_emoji"] = emoji
    result["verdict_label"] = label
    result["primary_sources"] = sources
    return result
