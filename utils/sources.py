from urllib.parse import urlparse

PRIMARY_DOMAINS = {
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "nih.gov",
    "cdc.gov",
    "fda.gov",
    "who.int",
    "nasa.gov",
    "nature.com",
    "science.org",
    "thelancet.com",
    "nejm.org",
    "jamanetwork.com",
    "bmj.com",
    "snopes.com",
    "factcheck.org",
    "apnews.com",
    "reuters.com",
    "bbc.com",
    "wikipedia.org",
}


def get_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def is_primary_source(url: str) -> bool:
    domain = get_domain(url)
    if domain in PRIMARY_DOMAINS:
        return True
    if domain.endswith(".gov") or domain.endswith(".edu"):
        return True
    return False


def score_source(url: str) -> float:
    domain = get_domain(url)
    if domain in {"pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "nejm.org", "thelancet.com", "jamanetwork.com", "nature.com", "science.org"}:
        return 1.0
    if domain in {"cdc.gov", "fda.gov", "who.int", "nasa.gov", "nih.gov"}:
        return 0.95
    if domain.endswith(".gov"):
        return 0.9
    if domain.endswith(".edu"):
        return 0.8
    if domain in {"snopes.com", "factcheck.org"}:
        return 0.75
    if domain in {"apnews.com", "reuters.com"}:
        return 0.7
    if domain in {"bbc.com", "wikipedia.org"}:
        return 0.6
    return 0.0
