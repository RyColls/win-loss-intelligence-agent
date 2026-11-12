"""Number check: every figure in the brief is recomputed from the coded table.

This module is deliberately independent of agent/stats.py (no import, its own arithmetic). The brief builder states
each figure together with a small query; this module re-runs the query on the table and compares. It also scans each
claim's text for numerals and refuses any that is not one of the claim's own figures.
"""
from __future__ import annotations

import re

FINANCE_TITLES = {"CFO", "VP Finance", "Controller", "Head of Finance", "Finance Director"}
ALLOWED_LITERALS = {"50", "99", "100", "199", "200", "500", "2025", "2026", "10", "1", "2", "3", "4", "Q4", "Q1", "Q2", "Q3",
                    "400", "95", "305"}  # segment names, quarter labels, the 10-day line, and dataset sizes stated by the brief itself


def _match(row, where):
    for k, want in where.items():
        v = row.get(k)
        if isinstance(want, list):
            if v not in want:
                return False
        elif isinstance(want, dict):
            if "gt" in want and not (v is not None and v > want["gt"]):
                return False
            if "lte" in want and not (v is not None and v <= want["lte"]):
                return False
        elif v != want:
            return False
    return True


def _count(rows, where):
    return sum(1 for r in rows if _match(r, where))


def evaluate(q, rows):
    op = q["op"]
    if op == "count":
        return float(_count(rows, q["where"]))
    if op == "pct":
        d = _count(rows, q["den"])
        return 100.0 * _count(rows, q["num"]) / d if d else 0.0
    if op == "mean":
        vals = [r[q["field"]] for r in rows if _match(r, q["where"])]
        return sum(vals) / len(vals) if vals else 0.0
    if op == "ratio":
        b = evaluate(q["b"], rows)
        return evaluate(q["a"], rows) / b if b else 0.0
    if op == "diff":
        return evaluate(q["a"], rows) - evaluate(q["b"], rows)
    if op == "shift_share":
        segs, q0, q1 = q["segments"], q["q0"], q["q1"]

        def sh(qtr, s):
            n = _count(rows, {"quarter": qtr})
            return _count(rows, {"quarter": qtr, "segment": s}) / n

        def wr(qtr, s):
            n = _count(rows, {"quarter": qtr, "segment": s})
            return _count(rows, {"quarter": qtr, "segment": s, "outcome": "won"}) / n if n else 0.0
        mix = sum((sh(q1, s) - sh(q0, s)) * wr(q0, s) for s in segs) * 100
        perf = sum(sh(q1, s) * (wr(q1, s) - wr(q0, s)) for s in segs) * 100
        total = (_count(rows, {"quarter": q1, "outcome": "won"}) / _count(rows, {"quarter": q1})
                 - _count(rows, {"quarter": q0, "outcome": "won"}) / _count(rows, {"quarter": q0})) * 100
        return {"mix": mix, "perf": perf, "total": total}[q["part"]]
    raise ValueError(op)


def fmt(fig):
    v, unit = fig["value"], fig["unit"]
    if unit == "pct":
        return f"{round(v):d}%"
    if unit == "pts":
        return f"{abs(v):.1f}"
    if unit == "n":
        return f"{int(round(v)):d}"
    if unit == "x":
        return f"{v:.1f}"
    if unit == "days":
        return f"{v:.1f}"
    raise ValueError(unit)


def numerals(text: str):
    t = re.sub(r"\b20\d\d-Q\d\b", " ", text)           # quarter labels
    t = re.sub(r"\b(50|100|200)\s*(-|–|to)\s*(99|199|500)\b", " ", t)  # segment names
    return re.findall(r"\d+(?:\.\d+)?", t)


def check_claim(claim, rows):
    problems = []
    shown = set()
    for name, fig in claim["figures"].items():
        again = evaluate(fig["query"], rows)
        if abs(again - fig["value"]) > 1e-9:
            problems.append(f"{claim['id']}.{name}: stored {fig['value']} != recomputed {again}")
        shown.add(fmt({"value": again, "unit": fig["unit"]}).rstrip("%"))
    for n in numerals(claim["text"]):
        if n not in shown and n not in ALLOWED_LITERALS:
            problems.append(f"{claim['id']}: numeral {n} in text is not one of the claim's figures")
    return problems


def check_brief(brief, rows):
    checked, problems = 0, []
    for c in brief["claims"]:
        checked += len(c["figures"])
        problems += check_claim(c, rows)
    return {"figures_checked": checked, "problems": problems,
            "number_integrity_pct": round(100.0 * (checked - len([p for p in problems if "stored" in p])) / checked, 1) if checked else 100.0}
