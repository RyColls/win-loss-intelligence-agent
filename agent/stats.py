"""All counting happens here, in code, from the coded table. The model never estimates a number."""
from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict

from . import config

MOBILE = re.compile(r"\b(mobile app|the app|our app|your app|app (keeps|kept|crash|froze|freezes|logs?|logged|won't|wouldn't))", re.I)


def load_roles():
    return json.loads((config.ROOT / "taxonomy" / "roles.json").read_text(encoding="utf-8"))


def role_of(reason: str, roles: dict) -> str:
    for r, ids in roles.items():
        if reason in ids:
            return r
    return "unclear" if reason == "unclear" else "other"


def build_table(deals: list[dict], coded: dict, roles: dict) -> list[dict]:
    rows = []
    for d in deals:
        row = {k: d[k] for k in ("deal_id", "quarter", "segment", "lead_source", "competitor", "amount", "days_to_demo",
                                 "outcome", "rep_tenure_months", "crm_loss_reason", "company")}
        row["finance_on_call2"] = any(t in ("CFO", "VP Finance", "Controller", "Head of Finance", "Finance Director")
                                      for t in d["buyers_call2"])
        row["mentions_mobile_app"] = bool(MOBILE.search(d["call_notes"] + " " + (d.get("closing_email") or "")))
        c = coded.get(d["deal_id"])
        if c:
            row["primary"], row["secondary"], row["confidence"] = c["primary"], c["secondary"], c["confidence"]
            row["role"] = role_of(c["primary"], roles)
            row["secondary_role"] = role_of(c["secondary"], roles) if c["secondary"] else None
        rows.append(row)
    return rows


def pct(n, d):
    return 100.0 * n / d if d else 0.0


def win_rate(rows):
    return pct(sum(r["outcome"] == "won" for r in rows), len(rows))


def reasons_by(rows, dim, roles_view=True):
    losses = [r for r in rows if r["outcome"] == "lost"]
    key = "role" if roles_view else "primary"
    out = {}
    for v in sorted({r[dim] for r in losses}):
        sub = [r for r in losses if r[dim] == v]
        c = Counter(r[key] for r in sub)
        out[v] = {"n": len(sub), "counts": dict(c), "shares": {k: pct(n, len(sub)) for k, n in c.items()}}
    return out


def crm_crosstab(rows):
    losses = [r for r in rows if r["outcome"] == "lost"]
    x = defaultdict(Counter)
    for r in losses:
        x[r["crm_loss_reason"]][r["role"]] += 1
    crm_price = [r for r in losses if r["crm_loss_reason"] == "Price"]
    coded_price = [r for r in losses if r["role"] == "price"]
    return {
        "crosstab": {k: dict(v) for k, v in x.items()},
        "crm_price_n": len(crm_price),
        "crm_price_share": pct(len(crm_price), len(losses)),
        "coded_price_share": pct(len(coded_price), len(losses)),
        "crm_price_but_not_price": sum(r["role"] != "price" for r in crm_price),
        "crm_price_but_not_price_pct": pct(sum(r["role"] != "price" for r in crm_price), len(crm_price)),
        "coded_price_marked_price": sum(r["crm_loss_reason"] == "Price" for r in coded_price),
        "n_losses": len(losses),
    }


def win_rates(rows):
    out = {"overall": win_rate(rows), "by_quarter": {}, "by_segment": {}, "by_quarter_segment": {}}
    for q in config.QUARTERS:
        out["by_quarter"][q] = win_rate([r for r in rows if r["quarter"] == q])
        for s in config.SEGMENTS:
            sub = [r for r in rows if r["quarter"] == q and r["segment"] == s]
            out["by_quarter_segment"][f"{q}|{s}"] = {"n": len(sub), "wins": sum(r["outcome"] == "won" for r in sub),
                                                      "rate": win_rate(sub)}
    for s in config.SEGMENTS:
        out["by_segment"][s] = win_rate([r for r in rows if r["segment"] == s])
    return out


def decomposition(rows, q0=None, q1=None):
    """Shift-share. Total change in win rate = mix effect + within-segment performance effect (exact, no residual)."""
    q0 = q0 or config.QUARTERS[0]
    q1 = q1 or config.QUARTERS[-1]
    def share_rate(q):
        sub = [r for r in rows if r["quarter"] == q]
        n = len(sub)
        return {s: (len([r for r in sub if r["segment"] == s]) / n,
                    win_rate([r for r in sub if r["segment"] == s]) / 100.0) for s in config.SEGMENTS}
    a, b = share_rate(q0), share_rate(q1)
    mix = sum((b[s][0] - a[s][0]) * a[s][1] for s in config.SEGMENTS) * 100
    perf = sum(b[s][0] * (b[s][1] - a[s][1]) for s in config.SEGMENTS) * 100
    total = win_rate([r for r in rows if r["quarter"] == q1]) - win_rate([r for r in rows if r["quarter"] == q0])
    return {"q0": q0, "q1": q1, "total_pts": total, "mix_pts": mix, "performance_pts": perf,
            "mix_share_of_decline": (mix / total * 100) if total else 0.0,
            "shares": {s: {"q0": a[s][0] * 100, "q1": b[s][0] * 100} for s in config.SEGMENTS},
            "segment_rates": {s: {"q0": a[s][1] * 100, "q1": b[s][1] * 100} for s in config.SEGMENTS}}


def segment_mix_by_quarter(rows):
    return {q: {s: pct(len([r for r in rows if r["quarter"] == q and r["segment"] == s]),
                       len([r for r in rows if r["quarter"] == q])) for s in config.SEGMENTS} for q in config.QUARTERS}


def demo_wait(rows):
    slow = [r for r in rows if r["days_to_demo"] > config.SLOW_DEMO_DAYS]
    fast = [r for r in rows if r["days_to_demo"] <= config.SLOW_DEMO_DAYS]
    by_q = {q: {"mean_wait": sum(r["days_to_demo"] for r in rows if r["quarter"] == q) / max(1, len([r for r in rows if r["quarter"] == q])),
                "slow_share": pct(len([r for r in slow if r["quarter"] == q]), len([r for r in rows if r["quarter"] == q]))}
            for q in config.QUARTERS}
    return {"slow_n": len(slow), "fast_n": len(fast), "slow_win_rate": win_rate(slow), "fast_win_rate": win_rate(fast),
            "ratio": (win_rate(slow) / win_rate(fast)) if win_rate(fast) else 0.0, "by_quarter": by_q}


def finance_pattern(rows):
    f = [r for r in rows if r["finance_on_call2"]]
    n = [r for r in rows if not r["finance_on_call2"]]
    return {"with_n": len(f), "without_n": len(n), "with_rate": win_rate(f), "without_rate": win_rate(n),
            "ratio": (win_rate(f) / win_rate(n)) if win_rate(n) else 0.0}


def broker_pattern(rows):
    losses = [r for r in rows if r["outcome"] == "lost"]
    b = [r for r in losses if r["lead_source"] == "broker"]
    nb = [r for r in losses if r["lead_source"] != "broker"]
    allb = [r for r in rows if r["lead_source"] == "broker"]
    alln = [r for r in rows if r["lead_source"] != "broker"]
    return {"broker_losses": len(b), "broker_win_rate": win_rate(allb), "other_win_rate": win_rate(alln),
            "broker_role_share": pct(sum(r["role"] == "broker" for r in b), len(b)),
            "other_role_share": pct(sum(r["role"] == "broker" for r in nb), len(nb)),
            "broker_role_to_bundler_pct": pct(sum(r["competitor"] == "Tallyhold" for r in b if r["role"] == "broker"),
                                              sum(r["role"] == "broker" for r in b)),
            "broker_price_or_product_share": pct(sum(r["role"] in ("price", "feature", "multistate") for r in b), len(b)),
            "other_price_or_product_share": pct(sum(r["role"] in ("price", "feature", "multistate") for r in nb), len(nb))}


def perm_test(a, b, n=5000, seed=11):
    rng = random.Random(seed)
    obs = abs(sum(a) / len(a) - sum(b) / len(b))
    pool = list(a) + list(b)
    k = len(a)
    hit = 0
    for _ in range(n):
        rng.shuffle(pool)
        if abs(sum(pool[:k]) / k - sum(pool[k:]) / (len(pool) - k)) >= obs:
            hit += 1
    return (hit + 1) / (n + 1)


def false_trail_tests(rows):
    """Candidate explanations that look plausible. Each is tested; one that does not hold up is reported as such."""
    won = [r for r in rows if r["outcome"] == "won"]
    lost = [r for r in rows if r["outcome"] == "lost"]
    tenure = {"won_mean_months": sum(r["rep_tenure_months"] for r in won) / len(won),
              "lost_mean_months": sum(r["rep_tenure_months"] for r in lost) / len(lost),
              "p_value": perm_test([r["rep_tenure_months"] for r in won], [r["rep_tenure_months"] for r in lost])}
    m = [r for r in rows if r["mentions_mobile_app"]]
    nm = [r for r in rows if not r["mentions_mobile_app"]]
    mobile = {"mention_n": len(m), "win_rate_with_mention": win_rate(m), "win_rate_without": win_rate(nm),
              "p_value": perm_test([1 if r["outcome"] == "won" else 0 for r in m], [1 if r["outcome"] == "won" else 0 for r in nm])}
    return {"rep_tenure": tenure, "mobile_app": mobile}


def theories(rows, roles):
    """Verdicts follow thresholds fixed in agent/config.py. The numbers come from the coded table."""
    losses = [r for r in rows if r["outcome"] == "lost"]
    n = len(losses)
    by_seg = {s: [r for r in losses if r["segment"] == s] for s in config.SEGMENTS}
    price_all = pct(sum(r["role"] == "price" for r in losses), n)
    price_seg = {s: pct(sum(r["role"] == "price" for r in v), len(v)) for s, v in by_seg.items()}
    prod = ("feature", "multistate")
    prod_all = pct(sum(r["role"] in prod for r in losses), n)
    prod_seg = {s: pct(sum(r["role"] in prod for r in v), len(v)) for s, v in by_seg.items()}
    bp = broker_pattern(rows)

    def verdict(overall, per_seg):
        if overall >= config.THEORY_SUPPORTED * 100 and all(v >= config.THEORY_PARTLY * 100 for v in per_seg.values()):
            return "supported"
        if overall >= config.THEORY_PARTLY * 100 or any(v >= config.PRICE_MAJORITY * 100 for v in per_seg.values()):
            return "partly supported"
        return "not supported"
    sales = verdict(price_all, price_seg)
    product = verdict(prod_all, prod_seg)
    # Marketing says the broker channel sends weak leads. "Weak leads" would show as broker deals losing for reasons
    # unrelated to the product or price AND not tied to a channel conflict. Evidence is the win-rate gap and the reasons.
    gap = bp["other_win_rate"] - bp["broker_win_rate"]
    if gap >= 3 and bp["broker_role_share"] >= 25:
        marketing = "partly supported"
    elif gap >= 3 and bp["broker_role_share"] < 25:
        marketing = "supported"
    else:
        marketing = "not supported"
    return {"sales_too_expensive": {"verdict": sales, "overall_pct": price_all, "by_segment": price_seg},
            "product_missing_features": {"verdict": product, "overall_pct": prod_all, "by_segment": prod_seg},
            "marketing_weak_broker_leads": {"verdict": marketing, **bp, "win_rate_gap_pts": gap}}


def compute_all(rows, roles):
    return {
        "n_deals": len(rows), "n_losses": sum(r["outcome"] == "lost" for r in rows), "n_wins": sum(r["outcome"] == "won" for r in rows),
        "win_rates": win_rates(rows), "mix": segment_mix_by_quarter(rows), "decomposition": decomposition(rows),
        "reasons_by_segment": reasons_by(rows, "segment"), "reasons_by_source": reasons_by(rows, "lead_source"),
        "reasons_by_competitor": reasons_by(rows, "competitor"), "reasons_by_quarter": reasons_by(rows, "quarter"),
        "primary_by_segment": reasons_by(rows, "segment", roles_view=False),
        "crm": crm_crosstab(rows), "demo_wait": demo_wait(rows), "finance": finance_pattern(rows),
        "broker": broker_pattern(rows), "false_trails": false_trail_tests(rows), "theories": theories(rows, roles),
        "confidence": Counter(r["confidence"] for r in rows if r["outcome"] == "lost"),
        "overall_reasons": {k: v for k, v in Counter(r["role"] for r in rows if r["outcome"] == "lost").items()},
    }
