from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx


REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class SourceNetworkError(RuntimeError):
    """Base class for fail-closed source access errors."""


class SourceNotApprovedError(SourceNetworkError):
    """Raised before any request when the source is not approved."""


class UnsafeUrlError(SourceNetworkError):
    """Raised when a URL, redirect target, or resolved IP violates policy."""


class RobotsDeniedError(SourceNetworkError):
    """Raised when robots.txt disallows the requested path."""


class AccessRestrictedError(SourceNetworkError):
    """Raised for login, CAPTCHA, 401, or 403 responses."""


class ResponseTooLargeError(SourceNetworkError):
    """Raised when a response exceeds the configured byte limit."""


class TooManyRedirectsError(SourceNetworkError):
    """Raised when the redirect chain exceeds policy."""


class RateLimitedError(SourceNetworkError):
    def __init__(self, retry_after_seconds: float | None = None):
        self.retry_after_seconds = retry_after_seconds
        suffix = f"; retry after {retry_after_seconds:.1f}s" if retry_after_seconds is not None else ""
        super().__init__(f"来源返回429，必须退避后重试{suffix}")


class FetchError(SourceNetworkError):
    """Raised for other non-success HTTP responses."""


@dataclass(frozen=True)
class _RobotsRule:
    allow: bool
    pattern: str


@dataclass(frozen=True)
class RobotsRules:
    rules: tuple[_RobotsRule, ...]

    @classmethod
    def from_text(cls, text: str, user_agent: str) -> "RobotsRules":
        ua = user_agent.lower()
        selected: list[_RobotsRule] = []
        agents: list[str] = []
        rules: list[_RobotsRule] = []

        def flush() -> None:
            nonlocal agents, rules
            if any(agent == "*" or agent in ua for agent in agents):
                selected.extend(rules)
            agents = []
            rules = []

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field, value = line.split(":", 1)
            field = field.strip().lower()
            value = value.strip()
            if field == "user-agent":
                if rules:
                    flush()
                agents.append(value.lower())
            elif field in {"allow", "disallow"} and agents:
                rules.append(_RobotsRule(allow=field == "allow", pattern=value))
            elif not agents:
                continue
        flush()
        return cls(tuple(selected))

    def can_fetch(self, url: str) -> bool:
        path = urlsplit(url).path or "/"
        matches: list[tuple[int, bool]] = []
        for rule in self.rules:
            if not rule.pattern:
                continue
            pattern = rule.pattern
            anchored = pattern.endswith("$")
            if anchored:
                pattern = pattern[:-1]
            regex = re.escape(pattern).replace(r"\*", ".*")
            if not anchored:
                regex = regex + ".*"
            if re.match(regex, path):
                matches.append((len(rule.pattern), rule.allow))
        if not matches:
            return True
        longest = max(length for length, _ in matches)
        return any(allow for length, allow in matches if length == longest)


@dataclass(frozen=True)
class FetchPolicy:
    allowed_hosts: frozenset[str]
    allowed_path_prefixes: tuple[str, ...]
    user_agent: str = "CampusCompAI/0.1"
    min_interval_seconds: float = 1.0
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 10.0
    max_response_bytes: int = 1_000_000
    max_redirects: int = 3
    max_429_retries: int = 1
    max_retry_after_seconds: float = 30.0
    respect_robots: bool = True

    def __post_init__(self):
        if not self.allowed_hosts:
            raise ValueError("allowed_hosts cannot be empty")
        if not self.allowed_path_prefixes:
            raise ValueError("allowed_path_prefixes cannot be empty")
        if not self.user_agent.strip():
            raise ValueError("user_agent cannot be empty")
        if self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds cannot be negative")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if self.max_redirects < 0:
            raise ValueError("max_redirects cannot be negative")
        if self.max_429_retries < 0:
            raise ValueError("max_429_retries cannot be negative")


@dataclass(frozen=True)
class SafeResponse:
    url: str
    status_code: int
    content_type: str
    content: bytes
    text: str
    fetched_at: datetime

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class _RawResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes
    text: str
    content_type: str


class SafeHttpFetcher:
    """Low-frequency HTTP fetcher with fail-closed URL, DNS, robots, and rate checks."""

    def __init__(
        self,
        policy: FetchPolicy,
        *,
        client: httpx.Client | None = None,
        resolver: Callable[[str, int], Iterable[str]] | None = None,
        sleeper: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.policy = policy
        self._client = client
        self._resolver = resolver or self._default_resolver
        self._sleep = sleeper or time.sleep
        self._clock = clock or time.monotonic
        self._last_request_at: dict[str, float] = {}
        self._robots_cache: dict[str, RobotsRules | None] = {}
        self._lock = threading.Lock()

    def fetch(self, url: str) -> SafeResponse:
        return self._request(self.validate_url(url))

    def validate_url(self, url: str, *, allow_robots: bool = False) -> str:
        if not isinstance(url, str) or not url.strip() or url != url.strip():
            raise UnsafeUrlError("URL不能为空或包含首尾空白")
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            raise UnsafeUrlError("只允许HTTPS URL")
        if parts.username or parts.password:
            raise UnsafeUrlError("URL不能包含账号或密码")
        try:
            port = parts.port
        except ValueError as exc:
            raise UnsafeUrlError("URL端口非法") from exc
        if port not in (None, 443):
            raise UnsafeUrlError("来源只允许HTTPS 443端口")
        host = parts.hostname.lower().rstrip(".")
        if host not in self.policy.allowed_hosts:
            raise UnsafeUrlError(f"域名不在白名单: {host}")
        path = parts.path or "/"
        if not (allow_robots and path == "/robots.txt"):
            if not any(path.startswith(prefix) for prefix in self.policy.allowed_path_prefixes):
                raise UnsafeUrlError(f"路径不在白名单: {path}")
        addresses = tuple(self._resolver(host, port or 443))
        if not addresses:
            raise UnsafeUrlError(f"域名无法解析: {host}")
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address.split("%", 1)[0])
            except ValueError as exc:
                raise UnsafeUrlError(f"解析结果不是IP地址: {address}") from exc
            if not ip.is_global:
                raise UnsafeUrlError(f"拒绝访问非公网地址: {ip}")
        netloc = host if port in (None, 443) else f"{host}:{port}"
        return urlunsplit(("https", netloc, path, parts.query, ""))

    def _default_resolver(self, host: str, port: int) -> tuple[str, ...]:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return tuple(dict.fromkeys(info[4][0] for info in infos))

    def _require_robots_allowed(self, url: str) -> None:
        host = urlsplit(url).hostname
        assert host is not None
        if host in self._robots_cache:
            rules = self._robots_cache[host]
            if rules is not None and not rules.can_fetch(url):
                raise RobotsDeniedError(f"robots.txt禁止访问: {url}")
            return
        robots_url = f"https://{host}/robots.txt"
        try:
            response = self._request(robots_url, allow_robots=True, allowed_statuses={200, 404})
        except AccessRestrictedError as exc:
            raise RobotsDeniedError("robots.txt访问被拒绝，来源必须暂停") from exc
        if response.status_code == 404:
            rules = None
        else:
            rules = RobotsRules.from_text(response.text, self.policy.user_agent)
        self._robots_cache[host] = rules
        if rules is not None and not rules.can_fetch(url):
            raise RobotsDeniedError(f"robots.txt禁止访问: {url}")

    def _request(
        self,
        url: str,
        *,
        allow_robots: bool = False,
        allowed_statuses: set[int] | frozenset[int] = frozenset({200}),
    ) -> SafeResponse:
        current = url
        redirects = 0
        while True:
            current = self.validate_url(current, allow_robots=allow_robots)
            if self.policy.respect_robots and not allow_robots:
                self._require_robots_allowed(current)
            raw = self._request_with_429_retry(current, allow_robots=allow_robots)
            if raw.status_code in REDIRECT_STATUSES:
                redirects += 1
                if redirects > self.policy.max_redirects:
                    raise TooManyRedirectsError("重定向次数超过上限")
                location = raw.headers.get("location")
                if not location:
                    raise FetchError("重定向响应缺少Location")
                current = urljoin(current, location)
                continue
            if raw.status_code in {401, 403}:
                raise AccessRestrictedError(f"来源要求登录、验证码或拒绝访问: HTTP {raw.status_code}")
            if raw.status_code not in allowed_statuses:
                raise FetchError(f"来源返回HTTP {raw.status_code}: {current}")
            if raw.status_code == 200 and not allow_robots:
                self._reject_access_restriction_markers(raw.text)
            return SafeResponse(
                url=raw.url,
                status_code=raw.status_code,
                content_type=raw.content_type,
                content=raw.content,
                text=raw.text,
                fetched_at=datetime.now(timezone.utc),
            )

    def _request_with_429_retry(self, url: str, *, allow_robots: bool) -> _RawResponse:
        for attempt in range(self.policy.max_429_retries + 1):
            self._throttle(url)
            raw = self._perform_request(url)
            if raw.status_code != 429:
                return raw
            retry_after = self._parse_retry_after(raw.headers.get("retry-after"))
            if attempt >= self.policy.max_429_retries:
                raise RateLimitedError(retry_after)
            wait_seconds = retry_after if retry_after is not None else min(5.0, self.policy.max_retry_after_seconds)
            if wait_seconds > self.policy.max_retry_after_seconds:
                raise RateLimitedError(retry_after)
            self._sleep(wait_seconds)
        raise RateLimitedError()

    def _perform_request(self, url: str) -> _RawResponse:
        client, owned = self._get_client()
        try:
            with client.stream("GET", url, headers={"User-Agent": self.policy.user_agent, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.1"}, follow_redirects=False) as response:
                content_type = response.headers.get("content-type", "")
                if response.status_code in REDIRECT_STATUSES or response.status_code == 429:
                    return _RawResponse(str(response.url), response.status_code, dict(response.headers), b"", "", content_type)
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > self.policy.max_response_bytes:
                            raise ResponseTooLargeError("响应Content-Length超过上限")
                    except ValueError:
                        pass
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self.policy.max_response_bytes:
                        raise ResponseTooLargeError("响应大小超过上限")
                    chunks.append(chunk)
                content = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                text = content.decode(encoding, errors="replace")
                return _RawResponse(str(response.url), response.status_code, dict(response.headers), content, text, content_type)
        finally:
            if owned:
                client.close()

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.Client(
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(connect=self.policy.connect_timeout_seconds, read=self.policy.read_timeout_seconds, write=self.policy.read_timeout_seconds, pool=self.policy.connect_timeout_seconds),
        ), True

    def _throttle(self, url: str) -> None:
        host = urlsplit(url).hostname
        assert host is not None
        with self._lock:
            now = self._clock()
            last = self._last_request_at.get(host)
            wait_seconds = max(0.0, self.policy.min_interval_seconds - (now - last)) if last is not None else 0.0
        if wait_seconds > 0:
            self._sleep(wait_seconds)
        with self._lock:
            self._last_request_at[host] = self._clock()

    def _parse_retry_after(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None

    def _reject_access_restriction_markers(self, text: str) -> None:
        lowered = text.lower()
        markers = ("请输入验证码", "请先登录", "登录后查看", "captcha", "sign in to continue", "log in to continue")
        if any(marker in lowered for marker in markers):
            raise AccessRestrictedError("页面要求登录或验证码，来源必须暂停")
