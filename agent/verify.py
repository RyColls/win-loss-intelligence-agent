"""Quote check, run in code before anything reaches the brief.

A quote must appear in the deal's own text exactly as written. A quote that fails is removed. A coding whose
quotes all fail (and whose primary reason is not 'unclear') loses the claim it supported: the deal is recorded as
'unclear' and counted as dropped, never silently kept.
"""
from __future__ import annotations

from .data import source_text


def quote_ok(quote: str, text: str) -> bool:
    return bool(quote) and quote in text


def check_coding(deal: dict, coding: dict) -> tuple[dict, dict]:
    text = source_text(deal)
    kept = [q for q in coding["quotes"] if quote_ok(q, text)]
    removed = [q for q in coding["quotes"] if not quote_ok(q, text)]
    out = dict(coding)
    out["quotes"] = kept
    out["quotes_removed"] = removed
    out["dropped"] = False
    if coding["primary"] != "unclear" and not kept:
        out["raw_primary"] = coding["primary"]
        out["primary"] = "unclear"
        out["secondary"] = None
        out["confidence"] = "low"
        out["dropped"] = True
    return out, {"checked": len(coding["quotes"]), "failed": len(removed)}


def check_all(deals_by_id: dict, codings: dict) -> tuple[dict, dict]:
    checked = failed = dropped = 0
    out = {}
    for did, c in codings.items():
        res, st = check_coding(deals_by_id[did], c)
        out[did] = res
        checked += st["checked"]
        failed += st["failed"]
        dropped += res["dropped"]
    return out, {"quotes_checked": checked, "quotes_failed": failed, "codings_dropped": dropped,
                 "quote_integrity_pct": round(100.0 * (checked - failed) / checked, 1) if checked else 100.0}
