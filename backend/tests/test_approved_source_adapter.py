from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.crawlers.approved_source import ApprovedStaticPageAdapter
from app.crawlers.network_policy import FetchPolicy, SafeHttpFetcher, SourceNotApprovedError


def source(*, approved=True, enabled=True):
    return SimpleNamespace(is_demo=False, policy_status="approved" if approved else "pending", network_enabled=enabled)


def policy():
    return FetchPolicy(
        allowed_hosts=frozenset({"notices.example"}),
        allowed_path_prefixes=("/notices/",),
        user_agent="CampusCompAI-test/0.1",
        min_interval_seconds=0.0,
        max_response_bytes=5000,
    )


def make_adapter(handler, *, approved=True, enabled=True):
    p = policy()
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    fetcher = SafeHttpFetcher(p, client=client, resolver=lambda host, port: ("93.184.216.34",), sleeper=lambda seconds: None)
    return ApprovedStaticPageAdapter(
        source=source(approved=approved, enabled=enabled),
        list_url="https://notices.example/notices/",
        policy=p,
        fetcher=fetcher,
        title_keywords=("通知",),
        max_items=3,
    )


def test_unapproved_source_never_calls_transport():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200)

    adapter = make_adapter(handler, approved=False)
    with pytest.raises(SourceNotApprovedError):
        adapter.collect()
    assert calls == []


def test_approved_but_disabled_source_never_calls_transport():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200)

    adapter = make_adapter(handler, approved=True, enabled=False)
    with pytest.raises(SourceNotApprovedError):
        adapter.collect()
    assert calls == []


def test_adapter_collects_matching_links_and_evidence():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /notices/\n")
        if request.url.path == "/notices/":
            return httpx.Response(200, text='<a href="/notices/1">报名通知</a><a href="/other/2">其他链接</a>')
        if request.url.path == "/notices/1":
            return httpx.Response(200, text="<html>报名通知正文</html>", headers={"content-type": "text/html; charset=utf-8"})
        return httpx.Response(404)

    results = make_adapter(handler).collect()
    assert len(results) == 1
    assert results[0]["title"] == "报名通知"
    assert results[0]["source_url"] == "https://notices.example/notices/1"
    assert results[0]["content_sha256"]
    assert results[0]["parser_ready"] is False
    assert results[0]["evidence"]["list_page"]["sha256"]
