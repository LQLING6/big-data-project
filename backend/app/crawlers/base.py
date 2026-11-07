from typing import Protocol

from app.crawlers.network_policy import SourceNotApprovedError


class SourceAdapter(Protocol):
    def collect(self) -> list[dict]:
        """Return normalized notices with raw evidence. Must not bypass access controls."""
        ...


def require_source_approval(source) -> None:
    """Fail closed. This check alone does NOT authorize network access."""
    if source.is_demo:
        return
    if source.policy_status != "approved" or not source.network_enabled:
        raise SourceNotApprovedError("来源未获准采集；禁止绕过登录、验证码或反爬限制")
