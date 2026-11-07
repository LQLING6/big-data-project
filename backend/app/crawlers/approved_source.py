from __future__ import annotations

import hashlib
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from app.crawlers.base import require_source_approval
from app.crawlers.network_policy import FetchPolicy, SafeHttpFetcher, SafeResponse


@dataclass(frozen=True)
class NoticeCandidate:
    title: str
    url: str


class StaticNoticeLinkParser(HTMLParser):
    """Extract same-site notice links from a public list page without executing scripts."""

    def __init__(self, *, base_url: str, policy: FetchPolicy, title_keywords: tuple[str, ...] = ()):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.policy = policy
        self.title_keywords = title_keywords
        self._href: str | None = None
        self._text: list[str] = []
        self._candidates: list[NoticeCandidate] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_map = {key.lower(): value for key, value in attrs}
        href = attrs_map.get("href")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        title = " ".join("".join(self._text).split())
        href = self._href
        self._href = None
        self._text = []
        if not title or href.startswith(("javascript:", "mailto:", "#")):
            return
        url = urljoin(self.base_url, href)
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in self.policy.allowed_hosts:
            return
        if not any(parts.path.startswith(prefix) for prefix in self.policy.allowed_path_prefixes):
            return
        if self.title_keywords and not any(keyword in title for keyword in self.title_keywords):
            return
        candidate = NoticeCandidate(title=title, url=url)
        if candidate not in self._candidates:
            self._candidates.append(candidate)

    def parse(self, html: str) -> list[NoticeCandidate]:
        self.feed(html)
        self.close()
        return list(self._candidates)


class ApprovedStaticPageAdapter:
    """Fetch and retain a list page plus matching detail pages.

    This adapter deliberately does not extract normalized deadline/eligibility fields yet.
    A source-specific parser can only be finalized after C01 marks a source as allowed.
    """

    def __init__(
        self,
        *,
        source,
        list_url: str,
        policy: FetchPolicy,
        fetcher: SafeHttpFetcher | None = None,
        title_keywords: tuple[str, ...] = ("通知", "公告", "竞赛", "大赛", "赛事", "报名", "动态"),
        max_items: int = 20,
        parser_version: str = "approved-static-v1",
    ):
        self.source = source
        self.list_url = list_url
        self.policy = policy
        self.fetcher = fetcher or SafeHttpFetcher(policy)
        self.title_keywords = title_keywords
        self.max_items = max_items
        self.parser_version = parser_version

    def collect(self) -> list[dict]:
        require_source_approval(self.source)
        list_page = self.fetcher.fetch(self.list_url)
        parser = StaticNoticeLinkParser(base_url=str(list_page.url), policy=self.policy, title_keywords=self.title_keywords)
        candidates = parser.parse(list_page.text)[: self.max_items]
        results: list[dict] = []
        for candidate in candidates:
            page = self.fetcher.fetch(candidate.url)
            results.append(self._result(candidate, list_page, page))
        return results

    def _result(self, candidate: NoticeCandidate, list_page: SafeResponse, detail_page: SafeResponse) -> dict:
        return {
            "external_key": hashlib.sha256(candidate.url.encode()).hexdigest()[:24],
            "title": candidate.title,
            "source_url": detail_page.url,
            "list_page_url": list_page.url,
            "parser_version": self.parser_version,
            "content_sha256": detail_page.sha256,
            "content_type": detail_page.content_type,
            "raw_text": detail_page.text,
            "fetched_at": detail_page.fetched_at.isoformat(),
            "evidence": {
                "list_page": {"url": list_page.url, "sha256": list_page.sha256},
                "detail_page": {"url": detail_page.url, "sha256": detail_page.sha256},
            },
            "parser_ready": False,
        }
