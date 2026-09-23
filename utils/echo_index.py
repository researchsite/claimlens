from utils.sources import is_primary_source


def calculate_echo_index(search_results: list[dict]) -> int:
    """
    SEO Echo Chamber Index: % of top search results that are NOT primary sources.
    Range 0–100. Higher = more SEO echo, more misinformation risk.
    """
    if not search_results:
        return 50
    echo_count = sum(
        1 for r in search_results
        if not is_primary_source(r.get("href", ""))
    )
    return round((echo_count / len(search_results)) * 100)
