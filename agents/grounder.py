import json
import requests
from utils.llm import get_client, MODEL_LARGE
from utils.sources import is_primary_source


def _search_wikipedia(query: str) -> list[dict]:
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query, "srlimit": 3, "format": "json"},
            timeout=6,
        )
        results = []
        for item in resp.json().get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = item.get("snippet", "").replace('<span class="searchmatch">', "").replace("</span>", "")
            results.append({"title": title, "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}", "snippet": snippet})
        return results
    except Exception:
        return []


def _search_openfda(query: str) -> list[dict]:
    try:
        resp = requests.get("https://api.fda.gov/drug/label.json",
                            params={"search": f'description:"{query}"', "limit": 2}, timeout=6)
        if resp.status_code != 200:
            return []
        results = []
        for item in resp.json().get("results", []):
            brand = item.get("openfda", {}).get("brand_name", ["Unknown Drug"])[0]
            desc = item.get("description", [""])[0][:300] if item.get("description") else ""
            results.append({"title": f"FDA Drug Label: {brand}", "url": "https://www.fda.gov", "snippet": desc})
        return results
    except Exception:
        return []


def find_primary_sources(claim: str, sub_claims: list[str], search_results: list[dict]) -> dict:
    client = get_client()
    primary_from_search = [r for r in search_results if is_primary_source(r.get("href", ""))]
    wiki = _search_wikipedia(claim)
    fda = _search_openfda(claim)

    lines = []
    for r in primary_from_search[:5]:
        lines.append(f"[Primary] {r.get('title','')} — {r.get('href','')}\n{r.get('body','')[:300]}")
    for r in wiki:
        lines.append(f"[Wikipedia] {r['title']} — {r['url']}\n{r['snippet']}")
    for r in fda:
        lines.append(f"[OpenFDA] {r['title']} — {r['url']}\n{r['snippet']}")
    for r in [x for x in search_results if not is_primary_source(x.get("href", ""))][:4]:
        lines.append(f"[SEO Blog] {r.get('title','')} — {r.get('href','')}\n{r.get('body','')[:200]}")

    sources_text = "\n\n".join(lines) if lines else "No sources found."

    resp = client.chat.completions.create(
        model=MODEL_LARGE,
        max_tokens=2048,
        temperature=0.1,
        messages=[
            {"role": "system", "content": "You are a research librarian identifying authoritative primary sources. Output ONLY valid JSON, no markdown."},
            {"role": "user", "content": f"""Analyze these sources for: "{claim}"

Sub-claims:
{chr(10).join(f"- {c}" for c in sub_claims)}

Sources:
{sources_text}

JSON only:
{{
    "primary_sources": [
        {{
            "url": "...",
            "title": "...",
            "domain_type": "pubmed|gov|edu|official|wikipedia|factcheck",
            "relevant_quote": "Max 80 words",
            "supports_claim": true,
            "reliability": "high|medium|low"
        }}
    ],
    "primary_source_count": 0,
    "notes": "One sentence on what primary evidence was found or absent"
}}"""},
        ],
    )
    text = resp.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"primary_sources": [], "primary_source_count": 0, "notes": "Parsing error in grounder."}
