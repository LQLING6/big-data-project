"""Extension point for member D. No model key or external request in the starter."""
from typing import Protocol


class ExplanationProvider(Protocol):
    def select_reasons(self, *, profile: dict, competition: dict, allowed_reasons: list[dict]) -> list[str]:
        """Return allowed reason codes only. Caller must revalidate evidence and versions."""
        ...


class RulesProvider:
    def select_reasons(self, *, profile: dict, competition: dict, allowed_reasons: list[dict]) -> list[str]:
        return [reason["code"] for reason in allowed_reasons]


def validate_reason_codes(codes: list[str], allowed_reasons: list[dict]) -> list[dict]:
    allowed = {reason["code"]: reason for reason in allowed_reasons}
    if not isinstance(codes, list) or any(not isinstance(code, str) or code not in allowed for code in codes):
        raise ValueError("模型输出包含无证据支持的理由")
    return [allowed[code] for code in dict.fromkeys(codes)]
