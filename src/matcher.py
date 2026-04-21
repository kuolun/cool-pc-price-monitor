"""Match TrackingRule[] against RawProduct[] using A+C hybrid."""
from __future__ import annotations

from src.models import MatchResult, RawProduct, TrackingRule


def match(rules: list[TrackingRule], raw: list[RawProduct]) -> list[MatchResult]:
    return [_match_one(rule, raw) for rule in rules]


def _match_one(rule: TrackingRule, raw: list[RawProduct]) -> MatchResult:
    # C mode: option_value_hint + must ALSO pass match_all (because option_value
    # repeats across <select> elements — e.g., case and psu both have value=140)
    if rule.option_value_hint:
        for r in raw:
            if (
                r.option_value == rule.option_value_hint
                and r.price is not None
                and all(kw in r.option_text for kw in rule.match_all)
                and not any(kw in r.option_text for kw in rule.exclude)
            ):
                return MatchResult(
                    rule=rule, raw=r, mode="option_value", confidence=1.0
                )
        # hint missing or match_all/exclude didn't hit → fall through to A mode

    # A mode: match_all ALL present, exclude NONE present, price not None
    candidates = [
        r for r in raw
        if all(kw in r.option_text for kw in rule.match_all)
        and not any(kw in r.option_text for kw in rule.exclude)
        and r.price is not None
    ]

    if not candidates:
        return MatchResult(rule=rule, raw=None, mode="not_found", confidence=0.0)

    if len(candidates) == 1:
        return MatchResult(
            rule=rule, raw=candidates[0], mode="keyword", confidence=1.0
        )

    # Multiple candidates → pick shortest option_text; confidence drops
    best = min(candidates, key=lambda r: len(r.option_text))
    return MatchResult(
        rule=rule, raw=best, mode="keyword",
        confidence=1.0 / len(candidates),
    )
