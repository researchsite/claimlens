from typing import Generator
from utils.llm import get_client, MODEL_LARGE


def stream_approach_a(claim: str, search_results: list[dict]) -> Generator[str, None, None]:
    client = get_client()
    if not search_results:
        context = "No search results available."
    else:
        snippets = [
            f"[{r.get('title','Untitled')}]\n{r.get('body','')[:400]}\nSource: {r.get('href','')}"
            for r in search_results[:10]
        ]
        context = "\n\n---\n\n".join(snippets)

    stream = client.chat.completions.create(
        model=MODEL_LARGE,
        max_tokens=1024,
        temperature=0.3,
        stream=True,
        messages=[{"role": "user", "content": (
            f'Based on these web search results about "{claim}", write a confident '
            "2-3 paragraph informative summary. Synthesize what these sources say.\n\n"
            f"Search Results:\n{context}\n\nSummary:"
        )}],
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
