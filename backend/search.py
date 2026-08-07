from __future__ import annotations

import html
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests

try:
    from .citation import (
        assign_citation_ids,
        build_cited_answer_from_summaries,
        build_llm_prompt,
        build_source_summaries,
        ensure_inline_citations,
        public_source,
        sources_used_from_answer,
    )
    from .crawler import clean_text, crawl_sources, dedupe_sources, source_domain
    from .evaluator import evaluate_pipeline_result
    from .ranker import rank_sources
    from .verifier import CONFLICT_MESSAGE, filter_low_quality_sources, verification_summary
except ImportError:
    from citation import (
        assign_citation_ids,
        build_cited_answer_from_summaries,
        build_llm_prompt,
        build_source_summaries,
        ensure_inline_citations,
        public_source,
        sources_used_from_answer,
    )
    from crawler import clean_text, crawl_sources, dedupe_sources, source_domain
    from evaluator import evaluate_pipeline_result
    from ranker import rank_sources
    from verifier import CONFLICT_MESSAGE, filter_low_quality_sources, verification_summary


SearchLLMClient = Callable[[str], str]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def decode_search_url(raw_url: str) -> str:
    url = html.unescape(str(raw_url or "")).strip()
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return url


def clean_html_fragment(fragment: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", fragment or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return clean_text(text)


class DuckDuckGoSearchProvider:
    name = "duckduckgo_html"

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        query = clean_text(query)
        if not query:
            return []
        results = self._html_search(query, max_results=max_results)
        if not results:
            results = self._lite_search(query, max_results=max_results)
        return results[:max_results]

    def _html_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        response = self.session.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            timeout=self.timeout,
        )
        response.raise_for_status()
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|</body>)',
            re.IGNORECASE | re.DOTALL,
        )
        results: List[Dict[str, Any]] = []
        seen = set()
        for match in pattern.finditer(response.text):
            url = decode_search_url(match.group(1))
            title = clean_html_fragment(match.group(2))
            rest = match.group(3)
            snippet_match = (
                re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.IGNORECASE | re.DOTALL)
                or re.search(r'class="result__snippet"[^>]*>(.*?)</div>', rest, re.IGNORECASE | re.DOTALL)
            )
            snippet = clean_html_fragment(snippet_match.group(1)) if snippet_match else ""
            if not url.startswith(("http://", "https://")) or not title or url in seen:
                continue
            seen.add(url)
            results.append(
                {
                    "title": title[:220],
                    "url": url,
                    "domain": source_domain(url),
                    "snippet": snippet[:900],
                    "score": max(1, 100 - len(results) * 7),
                    "provider": self.name,
                }
            )
            if len(results) >= max_results:
                break
        return results

    def _lite_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        response = self.session.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            timeout=self.timeout,
        )
        response.raise_for_status()
        link_pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
        results: List[Dict[str, Any]] = []
        seen = set()
        for match in link_pattern.finditer(response.text):
            url = decode_search_url(match.group(1))
            title = clean_html_fragment(match.group(2))
            if not url.startswith(("http://", "https://")) or not title or url in seen:
                continue
            if "duckduckgo.com" in source_domain(url):
                continue
            snippet = clean_html_fragment(response.text[match.end(): match.end() + 900])
            snippet = re.sub(r"(?i)\b(Next Page|More Results|Images|Videos|News)\b.*$", "", snippet).strip()
            seen.add(url)
            results.append(
                {
                    "title": title[:220],
                    "url": url,
                    "domain": source_domain(url),
                    "snippet": snippet[:900],
                    "score": max(1, 95 - len(results) * 7),
                    "provider": "duckduckgo_lite",
                }
            )
            if len(results) >= max_results:
                break
        return results


def clamp_source_count(max_sources: int) -> int:
    try:
        value = int(max_sources)
    except Exception:
        value = 8
    return max(5, min(value, 10))


def run_search_pipeline(
    query: str,
    max_sources: int = 8,
    llm_client: Optional[SearchLLMClient] = None,
    provider: Optional[DuckDuckGoSearchProvider] = None,
    crawl_timeout: int = 8,
) -> Dict[str, Any]:
    clean_query = clean_text(query)
    if not clean_query:
        return {
            "ok": False,
            "query": query,
            "answer": "Enter a search query.",
            "sources": [],
            "sources_used": [],
            "confidence_score": 0,
            "quality_metrics": {},
            "verification": {},
            "error": "empty_query",
            "created_at": now_iso(),
        }

    started = time.time()
    source_limit = clamp_source_count(max_sources)
    search_count = max(10, source_limit * 2)
    search_provider = provider or DuckDuckGoSearchProvider()

    search_error = ""
    try:
        raw_results = search_provider.search(clean_query, max_results=search_count)
    except Exception as error:
        search_error = str(error)[:500]
        duration = round(time.time() - started, 3)
        answer = (
            "Search is temporarily unavailable, so I could not verify this with live sources. "
            "Try again in a moment or check the search provider connection."
        )
        result = {
            "ok": False,
            "query": clean_query,
            "answer": answer,
            "sources": [],
            "sources_used": [],
            "rejected_sources": [],
            "source_summaries": [],
            "provider": search_provider.name,
            "searched_sources": 0,
            "deduped_sources": 0,
            "accepted_sources": 0,
            "ranked_sources": 0,
            "verification": {
                "confidence_inputs": {
                    "source_count": 0,
                    "trusted_source_count": 0,
                    "average_source_quality": 0,
                    "rejected_source_count": 0,
                },
                "conflict": {"has_conflict": False, "message": "", "conflicting_values": {}},
                "source_policy": "Search failed before sources could be verified.",
            },
            "llm_prompt_sent": False,
            "llm_error": "",
            "search_error": search_error,
            "fallback_used": True,
            "fallback_reason": "search_provider_failure",
            "duration_seconds": duration,
            "created_at": now_iso(),
        }
        metrics = evaluate_pipeline_result(result)
        result["confidence_score"] = metrics.get("confidence_score", 0)
        result["quality_metrics"] = metrics
        return result

    deduped = dedupe_sources(raw_results)
    crawled = crawl_sources(deduped[:search_count], timeout=crawl_timeout)
    quality_filter = filter_low_quality_sources(crawled)
    accepted_sources = quality_filter["accepted_sources"]
    rejected_sources = quality_filter["rejected_sources"]
    ranked = rank_sources(clean_query, accepted_sources, limit=source_limit)
    cited_sources = assign_citation_ids(ranked)
    verification = verification_summary(clean_query, cited_sources, rejected_sources)
    source_summaries = build_source_summaries(cited_sources)
    llm_prompt = build_llm_prompt(clean_query, cited_sources)

    answer = ""
    llm_error = ""
    if llm_client and cited_sources:
        try:
            answer = str(llm_client(llm_prompt) or "").strip()
        except Exception as error:
            llm_error = str(error)[:500]

    if not answer:
        answer = build_cited_answer_from_summaries(clean_query, cited_sources)
    if verification.get("conflict", {}).get("has_conflict") and CONFLICT_MESSAGE not in answer:
        answer = f"{CONFLICT_MESSAGE}\n\n{answer}"
    answer = ensure_inline_citations(answer, cited_sources)

    public_sources = [public_source(source) for source in cited_sources]
    used_sources = sources_used_from_answer(answer, cited_sources)
    duration = round(time.time() - started, 3)
    result = {
        "ok": bool(cited_sources),
        "query": clean_query,
        "answer": answer,
        "sources": public_sources,
        "sources_used": used_sources,
        "rejected_sources": [
            {
                "title": source.get("title", ""),
                "url": source.get("url", ""),
                "domain": source.get("domain", ""),
                "quality_score": source.get("quality_score", 0),
                "rejected_reason": source.get("rejected_reason", ""),
                "quality_reasons": source.get("quality_reasons", []),
            }
            for source in rejected_sources
        ],
        "source_summaries": source_summaries,
        "provider": search_provider.name,
        "searched_sources": len(raw_results),
        "deduped_sources": len(deduped),
        "accepted_sources": len(accepted_sources),
        "ranked_sources": len(cited_sources),
        "verification": verification,
        "llm_prompt_sent": bool(llm_client and cited_sources and not llm_error),
        "llm_error": llm_error,
        "search_error": search_error,
        "fallback_used": False,
        "fallback_reason": "",
        "duration_seconds": duration,
        "created_at": now_iso(),
    }
    metrics = evaluate_pipeline_result(result)
    result["confidence_score"] = metrics.get("confidence_score", 0)
    result["quality_metrics"] = metrics
    return result
