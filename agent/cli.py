"""Run the analysis:  python -m agent.cli --backend {keyword,recorded,live} [--run A]

Reads data/deals.json and taxonomy/. Writes results/<name>/: codings.json (after the quote check), coded_table.json,
stats.json, brief.json and checks.json. Never reads answer_key/ or gen/.
"""
from __future__ import annotations

import argparse
import json

from . import config
from .brief import build_brief
from .coder import code_deals, get_backend
from .data import load_deals, load_taxonomy
from .numcheck import check_brief
from .stats import build_table, compute_all, load_roles
from .verify import check_all


def run(backend_kind: str, run_id: str = "A", out_name: str | None = None) -> dict:
    deals = load_deals()
    taxonomy = load_taxonomy()
    roles = load_roles()
    backend = get_backend(backend_kind, taxonomy, run_id)
    raw = code_deals(deals, backend, taxonomy)
    by_id = {d["deal_id"]: d for d in deals}
    codings, quote_stats = check_all(by_id, raw)
    rows = build_table(deals, codings, roles)
    S = compute_all(rows, roles)
    brief = build_brief(rows, S, codings, by_id)
    # quotes used as evidence in the brief are checked again at the point of use
    ev_checked = ev_failed = 0
    for c in brief["claims"]:
        keep = []
        for q in c["evidence"]["quotes"]:
            ev_checked += 1
            d = by_id[q["deal_id"]]
            if q["quote"] in d["call_notes"] or (d.get("closing_email") and q["quote"] in d["closing_email"]):
                keep.append(q)
            else:
                ev_failed += 1
        c["evidence"]["quotes"] = keep
    num = check_brief(brief, rows)
    checks = {"backend": backend.name, "model": backend.model, "quotes": quote_stats,
              "brief_quotes": {"checked": ev_checked, "failed": ev_failed}, "numbers": num}
    name = out_name or (f"recorded_{run_id}" if backend_kind == "recorded" else backend_kind)
    out = config.RESULTS_DIR / name
    out.mkdir(parents=True, exist_ok=True)
    for fn, obj in (("codings.json", codings), ("coded_table.json", rows), ("stats.json", S), ("brief.json", brief),
                    ("checks.json", checks)):
        (out / fn).write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "brief.md").write_text(brief_md(brief), encoding="utf-8")
    return {"out": str(out), "checks": checks, "brief": brief}


SECTION = {1: "The headline", 2: "Why we lose, by company size", 3: "The three theories", 4: "What winning deals have in common",
           5: "Three recommended actions", 6: "What the data cannot tell us"}


def brief_md(brief: dict) -> str:
    L = [f"# {brief['title']}", "", "*Board brief. Lanternmere HR is a fictional sample client; the 400 deals are synthetic, with planted "
         "patterns. Every figure below was recomputed in code from the coded table, and every quote is an exact match to its call.*", ""]
    for s, name in SECTION.items():
        L += [f"## {s}. {name}", ""]
        for c in (c for c in brief["claims"] if c["section"] == s):
            own = f"**Owner: {c['owner']}.** " if c.get("owner") else ""
            L.append(f"{own}{c['text']}")
            for q in c["evidence"]["quotes"][:2]:
                L.append(f"> \u201c{q['quote']}\u201d ({q['deal_id']})")
            L.append("")
        if s == 6:
            L += [f"- {x}" for x in brief["limits"]] + [""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="recorded", choices=["keyword", "recorded", "live"])
    ap.add_argument("--run", default="A")
    a = ap.parse_args()
    r = run(a.backend, a.run)
    c = r["checks"]
    print(f"{c['backend']}: quotes {c['quotes']['quotes_checked']} checked, {c['quotes']['quotes_failed']} failed, "
          f"{c['quotes']['codings_dropped']} codings dropped; figures {c['numbers']['figures_checked']} rechecked, "
          f"{len(c['numbers']['problems'])} problems -> {r['out']}")
    for p in c["numbers"]["problems"]:
        print("  ", p)


if __name__ == "__main__":
    main()
