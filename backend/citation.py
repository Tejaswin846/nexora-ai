from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


def assign_citation_ids(sources: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cited: List[Dict[str, Any]] = []
    for index, source in enumerate(sources, start=1):
        item = dict(source)
        item["id"] = index
        item["citation_id"] = f"S{index}"
        cited.append(item)
    return cited


def public_source(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": source.get("id"),
        "citation_id": source.get("citation_id"),
        "title": source.get("title", ""),
        "url": source.get("url", ""),
        "domain": source.get("domain", ""),
        "snippet": source.get("snippet", ""),
        "summary": source.get("summary", ""),
        "score": source.get("score", 0),
        "relevance_score": source.get("relevance_score", 0),
        "quality_score": source.get("quality_score", 0),
        "trust_tier": source.get("trust_tier", ""),
        "provider": source.get("provider", ""),
        "fetch_ok": bool(source.get("fetch_ok")),
    }


def build_source_summaries(sources: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for source in sources:
        citation_id = source.get("citation_id", "")
        summary = str(source.get("summary", "")).strip()
        if not citation_id or not summary:
            continue
        summaries.append(
            {
                "citation_id": citation_id,
                "title": source.get("title", ""),
                "domain": source.get("domain", ""),
                "url": source.get("url", ""),
                "summary": summary,
            }
        )
    return summaries


def build_llm_prompt(query: str, sources: Iterable[Dict[str, Any]]) -> str:
    lines = [
        "Answer the user question using only the source summaries below.",
        "Cite factual claims inline using the source IDs exactly like [S1] or [S2].",
        "If the sources are weak or incomplete, say what is missing instead of guessing.",
        "",
        f"Question: {query}",
        "",
        "Source summaries:",
    ]
    for source in sources:
        citation_id = source.get("citation_id", "")
        title = source.get("title", "")
        domain = source.get("domain", "")
        summary = source.get("summary", "")
        if citation_id and summary:
            lines.append(f"[{citation_id}] {title} ({domain})")
            lines.append(f"Summary: {summary}")
            lines.append(f"URL: {source.get('url', '')}")
            lines.append("")
    lines.append("Write the final answer now with inline citations.")
    return "\n".join(lines)


def ensure_inline_citations(answer: str, sources: List[Dict[str, Any]]) -> str:
    text = str(answer or "").strip()
    if not text or not sources or re.search(r"\[S\d+\]", text):
        return text
    first_ids = " ".join(f"[{source.get('citation_id')}]" for source in sources[:2] if source.get("citation_id"))
    if not first_ids:
        return text
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() and not line.strip().endswith(":"):
            lines[index] = line.rstrip() + " " + first_ids
            return "\n".join(lines)
    return text + " " + first_ids


def citation_ids_in_answer(answer: str) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for match in re.findall(r"\[(S\d+)\]", str(answer or "")):
        if match not in seen:
            seen.add(match)
            ordered.append(match)
    return ordered


def sources_used_from_answer(answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ids = citation_ids_in_answer(answer)
    if not ids:
        return [public_source(source) for source in sources]
    by_id = {str(source.get("citation_id")): source for source in sources}
    return [public_source(by_id[citation_id]) for citation_id in ids if citation_id in by_id]


def build_cited_answer_from_summaries(query: str, sources: List[Dict[str, Any]]) -> str:
    if not sources:
        return (
            "I could not find enough reliable source content to answer this query. "
            "Try a more specific query or check the search provider connection."
        )

    lines = [
        f"Here is the best answer I can build from the retrieved sources for: {query}",
        "",
    ]
    for source in sources[:5]:
        citation = source.get("citation_id", "")
        summary = str(source.get("summary", "")).strip()
        title = str(source.get("title", "")).strip()
        if summary:
            label = f"{title}: " if title else ""
            lines.append(f"- {label}{summary} [{citation}]")
    lines.append("")
    lines.append("These citations map to the source list returned with this response.")
    return "\n".join(lines).strip()
