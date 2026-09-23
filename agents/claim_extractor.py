import json
from utils.llm import get_client, MODEL_SMALL


def extract_claims(headline: str) -> list[str]:
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL_SMALL,
        max_tokens=1024,
        temperature=0.1,
        messages=[
            {"role": "system", "content": "You are a fact-checking analyst. Extract specific, falsifiable sub-claims from viral headlines. Output ONLY valid JSON with no other text, no markdown."},
            {"role": "user", "content": f"""Extract 3–5 specific, falsifiable sub-claims from this viral headline.

Headline: "{headline}"

JSON only:
{{
    "sub_claims": ["Specific verifiable claim 1", "Specific verifiable claim 2"]
}}"""},
        ],
    )
    text = resp.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text).get("sub_claims", [headline])
    except json.JSONDecodeError:
        return [headline]
