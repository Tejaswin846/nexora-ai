from __future__ import annotations

import html
import re
from typing import Any, Dict, Iterable, List, Set


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> Set[str]:
    tokens = {
        token.lower()
        for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_\-]{1,}", clean_text(text))
        if token.lower() not in STOP_WORDS
    }
    return tokens


def split_sentences(text: str) -> List[str]:
    clean = clean_text(text)
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", clean)
    return [part.strip() for part in parts if len(part.strip()) >= 35]


def source_relevance_score(query: str, source: Dict[str, Any]) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return float(source.get("score", 0) or 0)

    title_tokens = tokenize(str(source.get("title", "")))
    snippet_tokens = tokenize(str(source.get("snippet", "")))
    content_tokens = tokenize(str(source.get("content", ""))[:6000])

    title_overlap = len(query_tokens & title_tokens)
    snippet_overlap = len(query_tokens & snippet_tokens)
    content_overlap = len(query_tokens & content_tokens)
    content_length = len(clean_text(source.get("content")))
    provider_score = float(source.get("score", 0) or 0)
    quality_score = float(source.get("quality_score", 0) or 0)
    trust_tier = str(source.get("trust_tier", "")).lower()
    trust_bonus = {
        "official": 18,
        "research": 15,
        "documentation": 14,
        "trusted_news": 12,
        "organization": 5,
    }.get(trust_tier, 0)
    phrase_bonus = 12 if clean_text(query).lower() in clean_text(source.get("content")).lower() else 0
    content_bonus = min(content_length / 1200.0, 8.0)

    return (
        title_overlap * 12.0
        + snippet_overlap * 6.0
        + content_overlap * 2.5
        + provider_score * 0.15
        + quality_score * 0.25
        + trust_bonus
        + phrase_bonus
        + content_bonus
    )


def summarize_source(query: str, source: Dict[str, Any], max_chars: int = 700) -> str:
    query_tokens = tokenize(query)
    text = clean_text(source.get("content")) or clean_text(source.get("snippet"))
    if not text:
        return ""

    sentences = split_sentences(text)
    if not sentences:
        return text[:max_chars]

    scored = []
    for index, sentence in enumerate(sentences[:80]):
        tokens = tokenize(sentence)
        overlap = len(query_tokens & tokens)
        score = overlap * 10 - index * 0.15
        if len(sentence) > 220:
            score -= 1
        scored.append((score, index, sentence))

    selected = sorted(scored, key=lambda item: item[0], reverse=True)[:3]
    selected = sorted(selected, key=lambda item: item[1])
    summary = clean_text(" ".join(item[2] for item in selected))
    if not summary:
        summary = text[:max_chars]
    return summary[:max_chars].rstrip()


def rank_sources(query: str, sources: Iterable[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        item = dict(source)
        item["relevance_score"] = round(source_relevance_score(query, item), 2)
        item["summary"] = summarize_source(query, item)
        if not item["summary"]:
            continue
        ranked.append(item)

    ranked.sort(
        key=lambda item: (
            float(item.get("relevance_score", 0) or 0),
            int(bool(item.get("fetch_ok"))),
            float(item.get("score", 0) or 0),
        ),
        reverse=True,
    )
    return ranked[: max(1, limit)]
