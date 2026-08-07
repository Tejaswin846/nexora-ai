from __future__ import annotations

import html
import re
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse


CONFLICT_MESSAGE = "Multiple sources report different information."

TRUSTED_NEWS_DOMAINS = {
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "reuters.com",
    "npr.org",
    "theguardian.com",
    "nytimes.com",
    "washingtonpost.com",
    "wsj.com",
    "ft.com",
    "economist.com",
    "bloomberg.com",
    "cnbc.com",
}

RESEARCH_DOMAINS = {
    "arxiv.org",
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "nature.com",
    "science.org",
    "thelancet.com",
    "nejm.org",
    "acm.org",
    "ieee.org",
    "jstor.org",
    "springer.com",
    "sciencedirect.com",
}

DOCUMENTATION_DOMAINS = {
    "docs.python.org",
    "developer.mozilla.org",
    "developer.apple.com",
    "learn.microsoft.com",
    "cloud.google.com",
    "docs.aws.amazon.com",
    "kubernetes.io",
    "docs.docker.com",
    "docs.github.com",
    "platform.openai.com",
    "docs.anthropic.com",
}

LOW_QUALITY_DOMAINS = {
    "pinterest.com",
    "instagram.com",
    "facebook.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "quora.com",
}

SPAM_PATTERNS = [
    r"\bcasino\b",
    r"\bviagra\b",
    r"\badult\b",
    r"\btorrent\b",
    r"\bfree\s+download\b",
    r"\bbuy\s+now\b",
    r"\bcoupon\s+code\b",
    r"\bmake\s+money\s+fast\b",
    r"\bclick\s+here\b",
    r"\bsponsored\s+links?\b",
    r"\bpayday\s+loan\b",
]

NEGATIVE_PATTERNS = [
    r"\bnot\b",
    r"\bno\b",
    r"\bfalse\b",
    r"\bdenied\b",
    r"\brejected\b",
    r"\bfailed\b",
    r"\bdecrease(?:d|s)?\b",
    r"\blower(?:ed|s)?\b",
]

POSITIVE_PATTERNS = [
    r"\byes\b",
    r"\btrue\b",
    r"\bapproved\b",
    r"\bconfirmed\b",
    r"\bsucceeded\b",
    r"\bincrease(?:d|s)?\b",
    r"\braise(?:d|s)?\b",
]


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def source_domain(url: str) -> str:
    try:
        host = urlparse(str(url or "")).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def source_text(source: Dict[str, Any], limit: int = 12000) -> str:
    text = " ".join(
        clean_text(source.get(key))
        for key in ("title", "snippet", "summary", "content")
        if clean_text(source.get(key))
    )
    return text[:limit]


def classify_trust_tier(source: Dict[str, Any]) -> str:
    domain = clean_text(source.get("domain")) or source_domain(str(source.get("url", "")))
    domain = domain.lower()
    path = urlparse(str(source.get("url", ""))).path.lower()

    if domain.endswith(".gov") or domain.endswith(".mil") or domain in {"europa.eu", "who.int", "worldbank.org", "imf.org"}:
        return "official"
    if domain.endswith(".edu") or domain in RESEARCH_DOMAINS:
        return "research"
    if domain in DOCUMENTATION_DOMAINS or "docs" in domain or "/docs" in path or "/documentation" in path:
        return "documentation"
    if domain in TRUSTED_NEWS_DOMAINS:
        return "trusted_news"
    if domain.endswith(".org"):
        return "organization"
    return "general"


def spam_signals(source: Dict[str, Any]) -> List[str]:
    domain = (clean_text(source.get("domain")) or source_domain(str(source.get("url", "")))).lower()
    text = source_text(source, limit=4000).lower()
    signals: List[str] = []
    if domain in LOW_QUALITY_DOMAINS:
        signals.append("low_quality_domain")
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, text):
            signals.append(f"spam_pattern:{pattern}")
    if len(clean_text(source.get("title"))) < 4:
        signals.append("missing_title")
    if not str(source.get("url", "")).startswith(("http://", "https://")):
        signals.append("invalid_url")
    if len(clean_text(source.get("content")) or clean_text(source.get("snippet"))) < 80:
        signals.append("thin_content")
    return signals


def score_source_quality(source: Dict[str, Any]) -> Tuple[int, List[str]]:
    score = 45
    reasons: List[str] = []
    tier = classify_trust_tier(source)

    trust_bonus = {
        "official": 35,
        "research": 30,
        "documentation": 28,
        "trusted_news": 24,
        "organization": 12,
        "general": 0,
    }.get(tier, 0)
    score += trust_bonus
    if trust_bonus:
        reasons.append(f"trusted:{tier}")

    content_len = len(clean_text(source.get("content")) or clean_text(source.get("snippet")))
    if source.get("fetch_ok"):
        score += 8
        reasons.append("fetch_ok")
    if content_len >= 300:
        score += 10
        reasons.append("enough_content")
    elif content_len >= 120:
        score += 4
        reasons.append("some_content")

    try:
        relevance = float(source.get("relevance_score", source.get("score", 0)) or 0)
    except Exception:
        relevance = 0
    score += int(min(max(relevance, 0), 100) * 0.08)

    signals = spam_signals(source)
    if signals:
        reasons.extend(signals)
        score -= 35 + min(25, len(signals) * 8)

    return max(0, min(100, score)), reasons


def filter_low_quality_sources(
    sources: Iterable[Dict[str, Any]],
    min_quality_score: int = 35,
) -> Dict[str, Any]:
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    for source in sources:
        if not isinstance(source, dict):
            continue
        item = dict(source)
        quality_score, reasons = score_source_quality(item)
        item["quality_score"] = quality_score
        item["quality_reasons"] = reasons
        item["trust_tier"] = classify_trust_tier(item)
        item["domain"] = clean_text(item.get("domain")) or source_domain(str(item.get("url", "")))

        if quality_score < min_quality_score or any(reason.startswith("spam_pattern:") for reason in reasons):
            item["rejected_reason"] = "low_quality_or_spam"
            rejected.append(item)
        else:
            accepted.append(item)

    accepted.sort(
        key=lambda item: (
            int(item.get("quality_score", 0) or 0),
            float(item.get("relevance_score", item.get("score", 0)) or 0),
        ),
        reverse=True,
    )
    return {
        "accepted_sources": accepted,
        "rejected_sources": rejected,
        "rejected_count": len(rejected),
    }


def extract_explicit_claim_value(source: Dict[str, Any]) -> str:
    value = source.get("claim_value")
    if value is None:
        return ""
    return clean_text(value).lower()


def representative_values(query: str, source: Dict[str, Any]) -> List[str]:
    explicit = extract_explicit_claim_value(source)
    if explicit:
        return [explicit]

    text = source_text(source, limit=2500)
    lower_query = clean_text(query).lower()
    values: List[str] = []

    if re.search(r"\b(when|date|year|founded|released|launched|elected|born|died)\b", lower_query):
        values.extend(re.findall(r"\b(?:18|19|20)\d{2}\b", text))

    if re.search(r"\b(price|rate|percent|percentage|score|how much|how many|market cap|revenue|cost)\b", lower_query):
        number_pattern = r"(?:[$₹€£]\s?\d+(?:,\d{3})*(?:\.\d+)?|\d+(?:,\d{3})*(?:\.\d+)?\s?%)"
        values.extend(re.findall(number_pattern, text))

    if re.search(r"\b(is|are|was|were|did|does|do|can|should)\b", lower_query):
        has_positive = any(re.search(pattern, text.lower()) for pattern in POSITIVE_PATTERNS)
        has_negative = any(re.search(pattern, text.lower()) for pattern in NEGATIVE_PATTERNS)
        if has_positive and not has_negative:
            values.append("positive")
        if has_negative and not has_positive:
            values.append("negative")

    normalized = []
    seen = set()
    for value in values:
        normalized_value = clean_text(value).lower()
        if normalized_value and normalized_value not in seen:
            seen.add(normalized_value)
            normalized.append(normalized_value)
    return normalized[:3]


def detect_conflicting_information(query: str, sources: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    value_to_sources: Dict[str, List[str]] = {}
    source_count = 0

    for source in sources:
        if not isinstance(source, dict):
            continue
        source_count += 1
        citation_id = str(source.get("citation_id") or source.get("id") or f"source_{source_count}")
        for value in representative_values(query, source):
            value_to_sources.setdefault(value, []).append(citation_id)

    values_with_sources = {
        value: sorted(set(source_ids))
        for value, source_ids in value_to_sources.items()
        if source_ids
    }
    has_conflict = source_count >= 2 and len(values_with_sources) >= 2
    return {
        "has_conflict": has_conflict,
        "message": CONFLICT_MESSAGE if has_conflict else "",
        "conflicting_values": values_with_sources if has_conflict else {},
    }


def verification_summary(query: str, sources: List[Dict[str, Any]], rejected_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    conflict = detect_conflicting_information(query, sources)
    trusted_count = sum(1 for source in sources if source.get("trust_tier") in {"official", "research", "documentation", "trusted_news"})
    avg_quality = 0.0
    if sources:
        avg_quality = round(sum(float(source.get("quality_score", 0) or 0) for source in sources) / len(sources), 2)
    return {
        "confidence_inputs": {
            "source_count": len(sources),
            "trusted_source_count": trusted_count,
            "average_source_quality": avg_quality,
            "rejected_source_count": len(rejected_sources),
        },
        "conflict": conflict,
        "source_policy": "Prefer official, government, documentation, research, and trusted-news sources; reject spam and thin low-quality pages.",
    }
