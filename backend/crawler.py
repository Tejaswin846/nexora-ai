from __future__ import annotations

import concurrent.futures
import html
import re
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)

IGNORED_TAGS = {"script", "style", "noscript", "svg", "canvas", "iframe"}
CONTENT_TAGS = {
    "title",
    "h1",
    "h2",
    "h3",
    "p",
    "li",
    "blockquote",
    "article",
    "section",
    "main",
}


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def source_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def canonical_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not key.lower().startswith("utm_")
        and key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
    ]
    path = re.sub(r"/+$", "", parsed.path or "/")
    return urlunparse((scheme, netloc, path, "", urlencode(sorted(query_pairs)), ""))


def dedupe_sources(sources: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen_urls = set()
    seen_title_domain = set()

    for source in sources:
        if not isinstance(source, dict):
            continue
        url = clean_text(source.get("url"))
        title = clean_text(source.get("title"))
        if not url.startswith(("http://", "https://")) or not title:
            continue

        canonical = canonical_url(url)
        domain = clean_text(source.get("domain")) or source_domain(url)
        title_key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
        title_domain_key = (domain, title_key[:120])

        if canonical in seen_urls or title_domain_key in seen_title_domain:
            continue
        seen_urls.add(canonical)
        seen_title_domain.add(title_domain_key)

        item = dict(source)
        item["url"] = url
        item["canonical_url"] = canonical
        item["title"] = title[:220]
        item["domain"] = domain
        item["snippet"] = clean_text(item.get("snippet"))[:900]
        deduped.append(item)

    return deduped


class ArticleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._tag_stack: List[str] = []
        self._skip_depth = 0
        self._chunks: List[str] = []
        self.title = ""
        self.description = ""

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._tag_stack.append(tag)
        if tag in IGNORED_TAGS:
            self._skip_depth += 1
            return
        if tag == "meta":
            attrs_map = {str(key).lower(): str(value or "") for key, value in attrs}
            name = attrs_map.get("name", "").lower()
            prop = attrs_map.get("property", "").lower()
            if name == "description" or prop in {"og:description", "twitter:description"}:
                self.description = clean_text(attrs_map.get("content", ""))[:500]

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in IGNORED_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = clean_text(data)
        if not text:
            return
        current_tag = self._tag_stack[-1] if self._tag_stack else ""
        if current_tag == "title" and not self.title:
            self.title = text[:220]
        if current_tag in CONTENT_TAGS or len(text) > 80:
            self._chunks.append(text)

    def content(self, max_chars: int = 12000) -> str:
        pieces: List[str] = []
        if self.title:
            pieces.append(self.title)
        if self.description:
            pieces.append(self.description)
        pieces.extend(self._chunks)
        text = clean_text(" ".join(pieces))
        return text[:max_chars]


def extract_article_content(url: str, timeout: int = 8, max_chars: int = 12000) -> Dict[str, Any]:
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
    }
    started_url = clean_text(url)
    try:
        response = requests.get(started_url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" in content_type or "image/" in content_type or "video/" in content_type:
            return {
                "fetch_ok": False,
                "fetch_error": f"unsupported content type: {content_type[:80]}",
                "content": "",
                "final_url": response.url,
            }
        raw_text = response.text
        if "html" not in content_type:
            return {
                "fetch_ok": True,
                "fetch_error": "",
                "content": clean_text(raw_text)[:max_chars],
                "final_url": response.url,
            }
        parser = ArticleTextParser()
        parser.feed(raw_text[:750000])
        return {
            "fetch_ok": True,
            "fetch_error": "",
            "content": parser.content(max_chars=max_chars),
            "final_url": response.url,
        }
    except Exception as error:
        return {
            "fetch_ok": False,
            "fetch_error": str(error)[:500],
            "content": "",
            "final_url": started_url,
        }


def crawl_sources(
    sources: Iterable[Dict[str, Any]],
    timeout: int = 8,
    max_workers: int = 5,
) -> List[Dict[str, Any]]:
    source_list = [dict(source) for source in sources if isinstance(source, dict)]

    def crawl_one(source: Dict[str, Any]) -> Dict[str, Any]:
        article = extract_article_content(str(source.get("url", "")), timeout=timeout)
        item = dict(source)
        item.update(article)
        if not item.get("content"):
            item["content"] = clean_text(item.get("snippet"))
        item["domain"] = clean_text(item.get("domain")) or source_domain(str(item.get("url", "")))
        return item

    if not source_list:
        return []
    workers = max(1, min(max_workers, len(source_list)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(crawl_one, source_list))
