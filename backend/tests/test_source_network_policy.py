from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.crawlers.network_policy import (
    AccessRestrictedError,
    FetchError,
    FetchPolicy,
    RateLimitedError,
    RobotsDeniedError,
    ResponseTooLargeError,
    SafeHttpFetcher,
    UnsafeUrlError,
)

PUBLIC_IP = "93.184.216.34"


def policy(**overrides):
    values = dict(
        allowed_hosts=frozenset({"notices.example"}),
        allowed_path_prefixes=("/notices/",),
        user_agent="CampusCompAI-test/0.1",
        min_interval_seconds=0.0,
        max_response_bytes=1000,
        max_429_retries=1,
        max_retry_after_seconds=5.0,
    )
    values.update(overrides)
    return FetchPolicy(**values)


def fetcher(handler, *, resolver=None, sleeper=None, **overrides):
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    return SafeHttpFetcher(
        policy(**overrides),
        client=client,
        resolver=resolver or (lambda host, port: (PUBLIC_IP,)),
        sleeper=sleeper or (lambda seconds: None),
    )


def test_successful_fetch_checks_robots_and_returns_hash():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /notices/\n")
        return httpx.Response(200, text="<html><title>通知</title></html>", headers={"content-type": "text/html; charset=utf-8"})

    response = fetcher(handler).fetch("https://notices.example/notices/1")
    assert response.status_code == 200
    assert response.sha256
    assert calls == ["/robots.txt", "/notices/1"]


def test_robots_disallow_stops_before_content_request():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /notices/\n")
        raise AssertionError("content must not be requested")

    with pytest.raises(RobotsDeniedError):
        fetcher(handler).fetch("https://notices.example/notices/1")
    assert calls == ["/robots.txt"]


def test_redirect_to_unapproved_host_is_rejected():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(302, headers={"location": "https://evil.example/notices/1"})

    with pytest.raises(UnsafeUrlError):
        fetcher(handler).fetch("https://notices.example/notices/1")


def test_private_ip_is_rejected_after_resolution():
    with pytest.raises(UnsafeUrlError):
        fetcher(lambda request: httpx.Response(200), resolver=lambda host, port: ("127.0.0.1",)).fetch(
            "https://notices.example/notices/1"
        )


def test_http_url_is_rejected():
    with pytest.raises(UnsafeUrlError):
        fetcher(lambda request: httpx.Response(200)).fetch("http://notices.example/notices/1")


def test_401_and_403_stop():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(403)

    with pytest.raises(AccessRestrictedError):
        fetcher(handler).fetch("https://notices.example/notices/1")


def test_429_retry_after_sleeps_then_retries():
    calls = []
    sleeps = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if calls.count("/notices/1") == 1:
            return httpx.Response(429, headers={"retry-after": "1"})
        return httpx.Response(200, text="ok")

    response = fetcher(handler, sleeper=sleeps.append).fetch("https://notices.example/notices/1")
    assert response.status_code == 200
    assert 1.0 in sleeps


def test_429_with_long_retry_after_stops():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(429, headers={"retry-after": "60"})

    with pytest.raises(RateLimitedError):
        fetcher(handler).fetch("https://notices.example/notices/1")


def test_response_size_limit_is_enforced():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="x" * 2000)

    with pytest.raises(ResponseTooLargeError):
        fetcher(handler).fetch("https://notices.example/notices/1")


def test_login_or_captcha_page_stops():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="<html>请输入验证码</html>")

    with pytest.raises(AccessRestrictedError):
        fetcher(handler).fetch("https://notices.example/notices/1")


def test_other_http_error_is_not_silently_accepted():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(500)

    with pytest.raises(FetchError):
        fetcher(handler).fetch("https://notices.example/notices/1")


def test_redirect_target_is_rechecked_against_robots():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /notices/\nDisallow: /notices/private/\n")
        if request.url.path == "/notices/1":
            return httpx.Response(302, headers={"location": "/notices/private/1"})
        raise AssertionError("redirect target must not be requested")

    with pytest.raises(RobotsDeniedError):
        fetcher(handler).fetch("https://notices.example/notices/1")
    assert calls == ["/robots.txt", "/notices/1"]
