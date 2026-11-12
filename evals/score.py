"""Score a finished analysis against the answer key. This is the only code that opens answer_key/.

    python -m evals.score --run recorded_A [--second recorded_B]

Writes results/<run>/scores.json and scores.md. Pass criteria were fixed here before the first scored run.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRUTH_TO_ROLE = {"price": "price", "multistate_tax_gap": "multistate", "other_feature_gap": "feature",
                 "broker_recommended_competitor": "broker", "slow_demo_followup": "slow_demo", "no_decision": "stall",
                 "unclear": "unclear"}
ROLE_NAME = {"price": "Price", "multistate": "Multi-state payroll tax", "feature": "Other missing capability",
             "broker": "Broker recommended a competitor", "slow_demo": "Slow demo", "stall": "Project stalled",
             "unclear": "Unclear (no reason in the text)"}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def claim(brief, cid):
    return next(c for c in brief["claims"] if c["id"] == cid)


def top_role(S, seg):
    sh = S["reasons_by_segment"][seg]["shares"]
    return max(((v, k) for k, v in sh.items() if k != "unclear"))[1]


def pattern_recovery(brief, S):
    """One mechanical test per planted pattern, on what the brief states."""
    out = []
    ms = S["reasons_by_segment"]["200-500"]["shares"].get("multistate", 0)
    crm = claim(brief, "S5")["figures"]["crm"]["value"]
    out.append(("P1 Feature gap upmarket", top_role(S, "200-500") == "multistate" and ms >= 40 and crm >= 50,
                f"200-500 losses: multi-state tax is the top reason at {ms:.0f}%; CRM says Price on {crm:.0f}% of them"))
    d = S["decomposition"]
    sh = d["shares"]["200-500"]
    out.append(("P2 Mix shift", sh["q1"] - sh["q0"] >= 10 and d["mix_pts"] < 0,
                f"200-500 share {sh['q0']:.0f}% to {sh['q1']:.0f}%; mix explains {abs(d['mix_pts']):.1f} of {abs(d['total_pts']):.1f} points"))
    b = S["broker"]
    out.append(("P3 Broker conflict", b["broker_role_share"] >= 2 * max(b["other_role_share"], 1) and b["broker_role_to_bundler_pct"] >= 70,
                f"{b['broker_role_share']:.0f}% of broker losses coded broker-recommended (vs {b['other_role_share']:.0f}% elsewhere); "
                f"{b['broker_role_to_bundler_pct']:.0f}% of those went to the bundler"))
    w = S["demo_wait"]
    q = list(w["by_quarter"].values())
    out.append(("P4 Slow demos", w["ratio"] <= 0.65 and q[-1]["slow_share"] > q[0]["slow_share"],
                f"win rate {w['slow_win_rate']:.0f}% after a wait over 10 days vs {w['fast_win_rate']:.0f}%; slow share {q[0]['slow_share']:.0f}% to {q[-1]['slow_share']:.0f}%"))
    f = S["finance"]
    out.append(("P5 Finance leader on call two", f["ratio"] >= 1.5,
                f"{f['with_rate']:.0f}% with a finance leader vs {f['without_rate']:.0f}% without ({f['ratio']:.1f}x)"))
    tops = {s: top_role(S, s) for s in ("50-99", "100-199", "200-500")}
    out.append(("P6 Price is real in one place", tops["50-99"] == "price" and tops["100-199"] != "price" and tops["200-500"] != "price",
                f"top reason by segment: {tops}"))
    return [{"pattern": n, "found": bool(ok), "evidence": e} for n, ok, e in out]


def false_findings(brief, S):
    hits = []
    for c in brief["claims"]:
        if c["kind"] in ("finding", "verdict", "action") and re.search(r"tenure|mobile app|\bapp\b", c["text"], re.I):
            hits.append(c["id"])
    ft = S["false_trails"]
    return {"count": len(hits), "claims": hits,
            "rep_tenure": f"tested: won {ft['rep_tenure']['won_mean_months']:.0f} months vs lost {ft['rep_tenure']['lost_mean_months']:.0f}, "
                          f"p={ft['rep_tenure']['p_value']:.2f}; not reported as a finding",
            "mobile_app": f"tested: {ft['mobile_app']['mention_n']} deals mention it, win rate {ft['mobile_app']['win_rate_with_mention']:.0f}% vs "
                          f"{ft['mobile_app']['win_rate_without']:.0f}%, p={ft['mobile_app']['p_value']:.2f}; not reported as a finding"}


def accuracy(table, key):
    rows = [r for r in table if r["outcome"] == "lost"]
    per = defaultdict(lambda: [0, 0])
    conf = defaultdict(lambda: [0, 0])
    confusion = defaultdict(Counter)
    wrong = []
    hit = 0
    for r in rows:
        truth = TRUTH_TO_ROLE[key[r["deal_id"]]["true_primary"]]
        ok = r["role"] == truth
        hit += ok
        per[truth][0] += ok
        per[truth][1] += 1
        conf[r["confidence"]][0] += ok
        conf[r["confidence"]][1] += 1
        confusion[truth][r["role"]] += 1
        if not ok:
            wrong.append({"deal_id": r["deal_id"], "truth": truth, "coded": r["role"], "confidence": r["confidence"],
                          "truth_secondary": TRUTH_TO_ROLE.get(key[r["deal_id"]]["true_secondary"] or "", None)})
    sec_match = sum(1 for w in wrong if w["coded"] == w["truth_secondary"])
    has_sec = [r for r in rows if key[r["deal_id"]]["true_secondary"]]
    sec_right = sum(1 for r in has_sec if TRUTH_TO_ROLE[key[r["deal_id"]]["true_secondary"]] == r.get("secondary_role"))
    sec_extra = sum(1 for r in rows if not key[r["deal_id"]]["true_secondary"] and r.get("secondary_role"))
    return {"n": len(rows), "agree": hit, "pct": 100.0 * hit / len(rows),
            "by_reason": {k: {"agree": a, "n": n, "pct": 100.0 * a / n} for k, (a, n) in sorted(per.items())},
            "by_confidence": {k: {"agree": a, "n": n, "pct": 100.0 * a / n} for k, (a, n) in conf.items()},
            "confusion": {k: dict(v) for k, v in confusion.items()},
            "disagreements": wrong, "disagreements_matching_true_secondary": sec_match,
            "secondary": {"planted": len(has_sec), "recovered": sec_right, "pct": 100.0 * sec_right / max(1, len(has_sec)),
                          "coded_where_none_planted": sec_extra}}


def crm_baseline(table, key):
    """How well the CRM dropdown itself matches the key, for scale. Only 'Price' maps to a reason."""
    rows = [r for r in table if r["outcome"] == "lost"]
    said = [r for r in rows if r["crm_loss_reason"] == "Price"]
    right = sum(1 for r in said if key[r["deal_id"]]["true_primary"] == "price")
    return {"crm_price_n": len(said), "crm_price_correct": right, "pct": 100.0 * right / len(said)}


def stability(t1, t2):
    a = {r["deal_id"]: r for r in t1 if r["outcome"] == "lost"}
    b = {r["deal_id"]: r for r in t2 if r["outcome"] == "lost"}
    diff = [{"deal_id": k, "run_1": a[k]["role"], "run_2": b[k]["role"]} for k in sorted(a) if a[k]["role"] != b[k]["role"]]
    pairs = Counter(tuple(sorted((d["run_1"], d["run_2"]))) for d in diff)
    return {"n": len(a), "same": len(a) - len(diff), "pct": 100.0 * (len(a) - len(diff)) / len(a), "disagreements": diff,
            "secondary_same": sum(a[k].get("secondary_role") == b[k].get("secondary_role") for k in a),
            "confidence_same": sum(a[k]["confidence"] == b[k]["confidence"] for k in a),
            "by_pair": {" / ".join(k): v for k, v in pairs.most_common()}}


def score(run, second=None):
    key = load(ROOT / "answer_key" / "answer_key.json")["deals"]
    res = ROOT / "results" / run
    brief, S, table, checks = (load(res / f) for f in ("brief.json", "stats.json", "coded_table.json", "checks.json"))
    pr = pattern_recovery(brief, S)
    acc = accuracy(table, key)
    out = {
        "run": run, "backend": checks["backend"], "model": checks["model"],
        "pattern_recovery": {"found": sum(p["found"] for p in pr), "of": len(pr), "detail": pr},
        "false_findings": false_findings(brief, S),
        "coding_accuracy": acc,
        "crm_dropdown_baseline": crm_baseline(table, key),
        "quote_integrity": {**checks["quotes"], "brief_quotes_checked": checks["brief_quotes"]["checked"],
                            "brief_quotes_failed": checks["brief_quotes"]["failed"],
                            "pct_in_brief": 100.0 if checks["brief_quotes"]["failed"] == 0 else
                            100.0 * (1 - checks["brief_quotes"]["failed"] / checks["brief_quotes"]["checked"])},
        "number_integrity": checks["numbers"],
        "calibration": acc["by_confidence"],
    }
    if second:
        t2 = load(ROOT / "results" / second / "coded_table.json")
        st = stability(table, t2)
        s2 = load(ROOT / "results" / second / "stats.json")
        b2 = load(ROOT / "results" / second / "brief.json")
        st["second_run"] = second
        st["second_run_patterns_found"] = sum(p["found"] for p in pattern_recovery(b2, s2))
        st["second_run_accuracy_pct"] = accuracy(t2, key)["pct"]
        v1 = {k: v["verdict"] for k, v in S["theories"].items()}
        v2 = {k: v["verdict"] for k, v in s2["theories"].items()}
        st["verdicts_same"] = v1 == v2
        out["stability"] = st
    (res / "scores.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    (res / "scores.md").write_text(to_md(out), encoding="utf-8")
    return out


def to_md(o):
    a = o["coding_accuracy"]
    L = [f"# Scores: {o['run']} ({o['model']})", "",
         "Scored against `answer_key/answer_key.json`, which the analysis never reads. Synthetic deals with planted patterns: "
         "these scores test the method and do not show how it would do on real deals.", "",
         "| Check | Target | Result |", "|---|---|---|",
         f"| Pattern recovery | All 6 planted patterns found | {o['pattern_recovery']['found']} of {o['pattern_recovery']['of']} |",
         f"| False findings | 0 | {o['false_findings']['count']} |",
         f"| Coding accuracy | Report | {a['agree']} of {a['n']} losses ({a['pct']:.1f}%) |",
         f"| Quote integrity | 100% | {o['quote_integrity']['pct_in_brief']:.0f}% of quotes in the brief; "
         f"{o['quote_integrity']['quotes_failed']} of {o['quote_integrity']['quotes_checked']} coder quotes failed the check and were removed |",
         f"| Number integrity | 100% | {o['number_integrity']['figures_checked'] - len([p for p in o['number_integrity']['problems'] if 'stored' in p])} "
         f"of {o['number_integrity']['figures_checked']} figures recomputed and matched |",
         "| Calibration | Report | " + "; ".join(f"{k}: {v['agree']} of {v['n']} ({v['pct']:.0f}%)" for k, v in sorted(o['calibration'].items())) + " |"]
    if "stability" in o:
        s = o["stability"]
        L.append(f"| Stability | Report | two runs agree on {s['same']} of {s['n']} losses ({s['pct']:.1f}%) |")
    L += ["", "## Planted patterns", ""] + [f"- {'FOUND' if p['found'] else 'MISSED'}: {p['pattern']}. {p['evidence']}" for p in o["pattern_recovery"]["detail"]]
    L += ["", "## False trails", "", f"- Rep tenure: {o['false_findings']['rep_tenure']}", f"- Mobile app complaint: {o['false_findings']['mobile_app']}"]
    L += ["", "## Coding accuracy by true reason", "", "| True reason | Agree | n | % |", "|---|---|---|---|"]
    L += [f"| {ROLE_NAME[k]} | {v['agree']} | {v['n']} | {v['pct']:.0f}% |" for k, v in a["by_reason"].items()]
    L += ["", f"Of the {a['n'] - a['agree']} disagreements, {a['disagreements_matching_true_secondary']} chose the deal's true secondary reason as primary.",
          f"Secondary reasons: {a['secondary']['recovered']} of the {a['secondary']['planted']} planted secondary reasons were recovered "
          f"({a['secondary']['pct']:.0f}%); {a['secondary']['coded_where_none_planted']} were coded where none was planted.",
          f"For scale: the CRM dropdown said Price on {o['crm_dropdown_baseline']['crm_price_n']} losses and was right on "
          f"{o['crm_dropdown_baseline']['crm_price_correct']} ({o['crm_dropdown_baseline']['pct']:.0f}%)."]
    if "stability" in o:
        s = o["stability"]
        L += ["", "## Stability", "", f"Second run: {s['second_run']}. It found {s['second_run_patterns_found']} of 6 patterns with "
              f"{s['second_run_accuracy_pct']:.1f}% coding accuracy; theory verdicts {'match' if s['verdicts_same'] else 'DIFFER'}.",
              "Disagreements by pair: " + ("; ".join(f"{k}: {v}" for k, v in s["by_pair"].items()) or "none"),
              f"The two runs gave the same secondary reason on {s['secondary_same']} of {s['n']} losses and the same confidence on {s['confidence_same']}."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="recorded_A")
    ap.add_argument("--second")
    a = ap.parse_args()
    o = score(a.run, a.second)
    print(to_md(o))
