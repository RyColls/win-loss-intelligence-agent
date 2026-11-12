"""Step 1b: merge the written call notes and emails into the public deal file, and check them.

Reads data/deals_skeleton.json, gen/briefs/*.json (only to know which deals should have an email or a mobile-app
complaint) and gen/out/*.json. Writes data/deals.json, the only data file the analysis agent reads.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANNED = re.compile(r"\b(CRM|dropdown|drop-down|loss reason|price objection|feature gap|taxonomy)\b", re.I)


def words(s: str) -> int:
    return len(s.split())


def main() -> int:
    skeleton = json.loads((ROOT / "data" / "deals_skeleton.json").read_text(encoding="utf-8"))
    briefs = {}
    for p in sorted((ROOT / "gen" / "briefs").glob("batch_*.json")):
        for b in json.loads(p.read_text(encoding="utf-8")):
            briefs[b["deal_id"]] = b
    out = {}
    for p in sorted((ROOT / "gen" / "out").glob("batch_*.json")):
        out.update(json.loads(p.read_text(encoding="utf-8")))
    problems = []
    deals = []
    for d in skeleton:
        did = d["deal_id"]
        o = out.get(did)
        b = briefs[did]
        if not o:
            problems.append(f"{did}: missing")
            continue
        notes, email = o.get("call_notes"), o.get("closing_email")
        n = words(notes or "")
        if not 150 <= n <= 400:
            problems.append(f"{did}: call notes {n} words")
        if b["write_closing_email"] and not email:
            problems.append(f"{did}: email missing")
        if not b["write_closing_email"] and email:
            problems.append(f"{did}: unexpected email")
        for field, text in (("notes", notes), ("email", email)):
            if text and BANNED.search(text):
                problems.append(f"{did}: banned phrase in {field}: {BANNED.search(text).group(0)}")
        if b["include_mobile_app_complaint"] and not re.search(r"\bapp\b", notes or "", re.I):
            problems.append(f"{did}: mobile complaint requested but 'app' not found")
        if not b["include_mobile_app_complaint"] and re.search(r"mobile app", (notes or "") + (email or ""), re.I):
            problems.append(f"{did}: unrequested mobile-app mention")
        deals.append({**d, "call_notes": notes, "closing_email": email})
    wc = [words(d["call_notes"]) for d in deals if d["call_notes"]]
    print(f"deals assembled: {len(deals)} of {len(skeleton)}; call notes {min(wc, default=0)}-{max(wc, default=0)} words, "
          f"mean {sum(wc) / max(1, len(wc)):.0f}; emails {sum(1 for d in deals if d['closing_email'])}")
    if problems:
        print(f"{len(problems)} problems:")
        for p in problems[:60]:
            print(" ", p)
        return 1
    (ROOT / "data" / "deals.json").write_text(json.dumps(deals, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote data/deals.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
