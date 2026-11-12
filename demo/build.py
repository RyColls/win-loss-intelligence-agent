"""Build docs/index.html: the board brief with its evidence in the margin.

    python demo/build.py [--run recorded_A]

Everything on the page comes from committed files: results/<run>/ (brief, stats, coded table, scores), data/deals.json,
taxonomy/. The answer key is included only so a reader can check a deal against it; the analysis never read it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.numcheck import _count, evaluate, fmt  # noqa: E402

TRUTH_TO_ROLE = {"price": "price", "multistate_tax_gap": "multistate", "other_feature_gap": "feature",
                 "broker_recommended_competitor": "broker", "slow_demo_followup": "slow_demo", "no_decision": "stall",
                 "unclear": "unclear", None: None}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def speaker_of(deal, quote):
    for text in (deal["call_notes"], deal.get("closing_email") or ""):
        i = text.find(quote)
        if i < 0:
            continue
        if text is not deal["call_notes"]:
            return "closing email"
        line = text[text.rfind("\n", 0, i) + 1:i]
        head = line.split(":", 1)[0].strip() if ":" in line else ""
        if not head:
            # speaker label is on an earlier line of the same turn
            prev = text[:i].rstrip().split("\n")
            for ln in reversed(prev):
                if ":" in ln[:60]:
                    head = ln.split(":", 1)[0].strip()
                    break
        return head or "buyer"
    return "buyer"


def figure_view(f, rows):
    q = f["query"]
    out = {"shown": fmt(f), "unit": f["unit"]}
    if q["op"] == "pct":
        out["num"], out["den"] = _count(rows, q["num"]), _count(rows, q["den"])
    return out


def build(run: str) -> str:
    res = ROOT / "results" / run
    brief, S, table, scores, codings = (load(res / f) for f in ("brief.json", "stats.json", "coded_table.json", "scores.json", "codings.json"))
    deals = load(ROOT / "data" / "deals.json")
    key = load(ROOT / "answer_key" / "answer_key.json")
    by_id = {d["deal_id"]: d for d in deals}
    trow = {r["deal_id"]: r for r in table}

    for c in brief["claims"]:
        assert all(abs(evaluate(f["query"], table) - f["value"]) < 1e-9 for f in c["figures"].values())
        c["figs"] = [figure_view(f, table) for f in c["figures"].values()]
        del c["figures"]
        for q in c["evidence"]["quotes"]:
            q["speaker"] = speaker_of(by_id[q["deal_id"]], q["quote"])
            q["company"] = by_id[q["deal_id"]]["company"]

    out_deals = []
    for d in deals:
        r = trow[d["deal_id"]]
        c = codings.get(d["deal_id"])
        k = key["deals"][d["deal_id"]]
        out_deals.append({
            "id": d["deal_id"], "q": d["quarter"], "seg": d["segment"], "src": d["lead_source"], "comp": d["competitor"],
            "amt": d["amount"], "wait": d["days_to_demo"], "won": d["outcome"] == "won", "crm": d["crm_loss_reason"],
            "co": d["company"], "b1": d["buyers_call1"], "b2": d["buyers_call2"], "notes": d["call_notes"], "email": d["closing_email"],
            "role": r.get("role"), "sec": r.get("secondary_role"), "conf": r.get("confidence"),
            "quotes": c["quotes"] if c else [], "note": c["note"] if c else "",
            "truth": TRUTH_TO_ROLE[k["true_primary"]], "truth2": TRUTH_TO_ROLE[k["true_secondary"]],
        })

    kw = load(ROOT / "results" / "keyword" / "scores.json")
    data = {
        "run": run, "model": scores["model"], "brief": brief, "deals": out_deals,
        "taxonomy": load(ROOT / "taxonomy" / "taxonomy.json"), "roles": load(ROOT / "taxonomy" / "roles.json"),
        "stats": {"reasons_by_segment": S["reasons_by_segment"], "decomposition": S["decomposition"], "crm": S["crm"],
                  "win_by_quarter": S["win_rates"]["by_quarter"], "n_losses": S["n_losses"], "n_wins": S["n_wins"]},
        "scores": {k: scores[k] for k in ("pattern_recovery", "false_findings", "quote_integrity", "number_integrity", "calibration",
                                         "crm_dropdown_baseline")},
        "accuracy": {k: scores["coding_accuracy"][k] for k in ("n", "agree", "pct", "by_reason", "secondary")},
        "stability": {k: v for k, v in scores.get("stability", {}).items() if k != "second_run"} if "stability" in scores else None,
        "keyword": {"pct": kw["coding_accuracy"]["pct"], "agree": kw["coding_accuracy"]["agree"], "patterns": kw["pattern_recovery"]["found"]},
        "competitors": key["competitors"],
    }
    tpl = (ROOT / "demo" / "template.html").read_text(encoding="utf-8")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return tpl.replace("/*__DATA__*/null", blob)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="recorded_A")
    a = ap.parse_args()
    html = build(a.run)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "index.html").write_text(html, encoding="utf-8")
    print(f"wrote docs/index.html ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
