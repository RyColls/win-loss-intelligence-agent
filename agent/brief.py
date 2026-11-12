"""Assemble the board brief from computed figures. Prose is templated in code around numbers that come from stats.py;
each figure carries a query that agent/numcheck.py re-runs on the coded table. No model writes or estimates a number.
"""
from __future__ import annotations

from . import config

LABEL = {"price": "price", "multistate": "multi-state payroll tax handling", "feature": "a missing product capability",
         "broker": "a broker steering the buyer to a competitor", "slow_demo": "a slow demo", "stall": "a stalled project",
         "unclear": "no clear reason in the text"}
SEG = {"50-99": "50–99 employee", "100-199": "100–199 employee", "200-500": "200–500 employee"}
FIN = ["CFO", "VP Finance", "Controller", "Head of Finance", "Finance Director"]
Q0, Q1 = config.QUARTERS[0], config.QUARTERS[-1]


def fig(value, unit, query):
    return {"value": float(value), "unit": unit, "query": query}


def lossq(**where):
    return {"outcome": "lost", **where}


def pctq(num, den):
    return {"op": "pct", "num": num, "den": den}


class Builder:
    def __init__(self, rows, S, codings, deals_by_id):
        self.rows, self.S, self.codings, self.deals = rows, S, codings, deals_by_id
        self.claims = []

    # -------------------------------------------------------------- evidence
    def evidence(self, pred, k=3, quotes=True):
        sel = [r for r in self.rows if pred(r)]
        rank = {"high": 0, "medium": 1, "low": 2}
        sel.sort(key=lambda r: (rank.get(r.get("confidence", "low"), 3), r["deal_id"]))
        ids = [r["deal_id"] for r in sorted(sel, key=lambda r: r["deal_id"])]
        qs = []
        if quotes:
            for r in sel:
                c = self.codings.get(r["deal_id"])
                if c and c["quotes"]:
                    qs.append({"deal_id": r["deal_id"], "quote": c["quotes"][0]})
                if len(qs) >= k:
                    break
        return {"deal_ids": ids, "quotes": qs}

    def add(self, cid, section, kind, template, figures, evidence, owner=None):
        from .numcheck import fmt
        text = template.format(**{k: fmt(v) for k, v in figures.items()})
        self.claims.append({"id": cid, "section": section, "kind": kind, "text": text, "figures": figures,
                            "evidence": evidence, **({"owner": owner} if owner else {})})

    # -------------------------------------------------------------- brief
    def build(self):
        S, rows = self.S, self.rows
        wr = S["win_rates"]["by_quarter"]
        dec = S["decomposition"]
        n_losses = S["n_losses"]
        loss_all = {"outcome": "lost"}

        # 1. headline
        self.add("H1", 1, "finding",
                 "Win rate fell from {w0} to {w1} over four quarters, a drop of {drop} points. About {mix} points of the drop come from "
                 "selling to a larger share of 200–500 employee companies, which we win least often; the other {perf} points are "
                 "deals we now lose within segments.",
                 {"w0": fig(wr[Q0], "pct", pctq({"quarter": Q0, "outcome": "won"}, {"quarter": Q0})),
                  "w1": fig(wr[Q1], "pct", pctq({"quarter": Q1, "outcome": "won"}, {"quarter": Q1})),
                  "drop": fig(dec["total_pts"], "pts", {"op": "shift_share", "part": "total", "q0": Q0, "q1": Q1, "segments": config.SEGMENTS}),
                  "mix": fig(dec["mix_pts"], "pts", {"op": "shift_share", "part": "mix", "q0": Q0, "q1": Q1, "segments": config.SEGMENTS}),
                  "perf": fig(dec["performance_pts"], "pts", {"op": "shift_share", "part": "perf", "q0": Q0, "q1": Q1, "segments": config.SEGMENTS})},
                 self.evidence(lambda r: r["quarter"] in (Q0, Q1), quotes=False))
        crm = S["crm"]
        self.add("H2", 1, "finding",
                 "The CRM blames price for {crm} of losses, but in the buyers’ own words price is the main reason for only {coded}.",
                 {"crm": fig(crm["crm_price_share"], "pct", pctq({"outcome": "lost", "crm_loss_reason": "Price"}, loss_all)),
                  "coded": fig(crm["coded_price_share"], "pct", pctq({"outcome": "lost", "role": "price"}, loss_all))},
                 self.evidence(lambda r: r["outcome"] == "lost" and r["crm_loss_reason"] == "Price" and r.get("role") not in ("price", "unclear")))

        # 2. why we lose, by segment
        for i, s in enumerate(config.SEGMENTS):
            sh = S["reasons_by_segment"][s]["shares"]
            ordered = sorted(((v, k) for k, v in sh.items() if k != "unclear"), reverse=True)
            (v1, r1), (v2, r2) = ordered[0], ordered[1]
            n = S["reasons_by_segment"][s]["n"]
            self.add(f"S{i + 1}", 2, "finding",
                     "In " + SEG[s] + " deals, the most common main reason for a loss is " + LABEL[r1] + ", behind {a} of the {n} losses. "
                     "Next comes " + LABEL[r2] + ", at {b}.",
                     {"a": fig(v1, "pct", pctq(lossq(segment=s, role=r1), lossq(segment=s))),
                      "n": fig(n, "n", {"op": "count", "where": lossq(segment=s)}),
                      "b": fig(v2, "pct", pctq(lossq(segment=s, role=r2), lossq(segment=s)))},
                     self.evidence(lambda r, s=s, r1=r1: r["outcome"] == "lost" and r["segment"] == s and r.get("role") == r1))
        m = S["mix"]
        self.add("S4", 2, "finding",
                 "The mix shifted toward larger companies. 200–500 employee deals were {a} of the deals in the first quarter and {b} in the last, "
                 "and they close at {c} against {d} for smaller companies.",
                 {"a": fig(m[Q0]["200-500"], "pct", pctq({"quarter": Q0, "segment": "200-500"}, {"quarter": Q0})),
                  "b": fig(m[Q1]["200-500"], "pct", pctq({"quarter": Q1, "segment": "200-500"}, {"quarter": Q1})),
                  "c": fig(S["win_rates"]["by_segment"]["200-500"], "pct", pctq({"segment": "200-500", "outcome": "won"}, {"segment": "200-500"})),
                  "d": fig(100.0 * sum(1 for r in rows if r["segment"] != "200-500" and r["outcome"] == "won") / sum(1 for r in rows if r["segment"] != "200-500"),
                           "pct", pctq({"segment": ["50-99", "100-199"], "outcome": "won"}, {"segment": ["50-99", "100-199"]}))},
                 self.evidence(lambda r: r["segment"] == "200-500" and r["quarter"] == Q1, quotes=False))
        seg3 = "200-500"
        sh3 = S["reasons_by_segment"][seg3]["shares"]
        crm3 = 100.0 * sum(1 for r in rows if r["outcome"] == "lost" and r["segment"] == seg3 and r["role"] == "multistate" and r["crm_loss_reason"] == "Price") / max(1, sum(1 for r in rows if r["outcome"] == "lost" and r["segment"] == seg3 and r["role"] == "multistate"))
        self.add("S5", 2, "finding",
                 "Where the loss is about multi-state payroll tax handling, the CRM records {crm} of those deals as Price. The tax handling gap in "
                 "200–500 employee deals is invisible in the dropdown.",
                 {"crm": fig(crm3, "pct", pctq({"outcome": "lost", "segment": seg3, "role": "multistate", "crm_loss_reason": "Price"},
                                                {"outcome": "lost", "segment": seg3, "role": "multistate"}))},
                 self.evidence(lambda r: r["outcome"] == "lost" and r["segment"] == seg3 and r.get("role") == "multistate" and r["crm_loss_reason"] == "Price"))

        # 3. the three theories
        T = S["theories"]
        t1, t2, t3 = T["sales_too_expensive"], T["product_missing_features"], T["marketing_weak_broker_leads"]
        self.add("T1", 3, "verdict",
                 "Sales says we are too expensive: " + t1["verdict"] + ". Price is the main reason for {all} of losses overall, {a} in 50–99 "
                 "employee deals and {c} in 200–500.",
                 {"all": fig(t1["overall_pct"], "pct", pctq(lossq(role="price"), loss_all)),
                  "a": fig(t1["by_segment"]["50-99"], "pct", pctq(lossq(segment="50-99", role="price"), lossq(segment="50-99"))),
                  "c": fig(t1["by_segment"]["200-500"], "pct", pctq(lossq(segment="200-500", role="price"), lossq(segment="200-500")))},
                 self.evidence(lambda r: r["outcome"] == "lost" and r.get("role") == "price"))
        self.add("T2", 3, "verdict",
                 "Product says we are missing features: " + t2["verdict"] + ". A missing capability, mostly multi-state payroll tax handling, "
                 "is the main reason for {all} of losses overall and {c} in 200–500 employee deals, against {a} in 50–99.",
                 {"all": fig(t2["overall_pct"], "pct", pctq(lossq(role=["feature", "multistate"]), loss_all)),
                  "c": fig(t2["by_segment"]["200-500"], "pct", pctq(lossq(segment="200-500", role=["feature", "multistate"]), lossq(segment="200-500"))),
                  "a": fig(t2["by_segment"]["50-99"], "pct", pctq(lossq(segment="50-99", role=["feature", "multistate"]), lossq(segment="50-99")))},
                 self.evidence(lambda r: r["outcome"] == "lost" and r.get("role") in ("feature", "multistate")))
        self.add("T3", 3, "verdict",
                 "Marketing says the broker channel sends weak leads: " + t3["verdict"] + ". Broker deals do win less often ({bw} against {ow}), but "
                 "{br} of broker losses end because the broker steered the buyer to a competitor, against {ob} of other losses. That is a channel "
                 "conflict, not weak leads.",
                 {"bw": fig(t3["broker_win_rate"], "pct", pctq({"lead_source": "broker", "outcome": "won"}, {"lead_source": "broker"})),
                  "ow": fig(t3["other_win_rate"], "pct", pctq({"lead_source": ["inbound", "outbound"], "outcome": "won"}, {"lead_source": ["inbound", "outbound"]})),
                  "br": fig(t3["broker_role_share"], "pct", pctq(lossq(lead_source="broker", role="broker"), lossq(lead_source="broker"))),
                  "ob": fig(t3["other_role_share"], "pct", pctq(lossq(lead_source=["inbound", "outbound"], role="broker"), lossq(lead_source=["inbound", "outbound"])))},
                 self.evidence(lambda r: r["outcome"] == "lost" and r["lead_source"] == "broker" and r.get("role") == "broker"))

        # 4. what winning deals have in common
        F, D = S["finance"], S["demo_wait"]
        win_fin = [r for r in rows if r["outcome"] == "won" and r["finance_on_call2"]]
        ev = {"deal_ids": [r["deal_id"] for r in win_fin], "quotes": []}
        for r in win_fin:
            d = self.deals[r["deal_id"]]
            for line in d["call_notes"].split("\n"):
                head = line.split(":", 1)[0]
                if any(t in head for t in FIN) and len(line.split(":", 1)[-1].split()) >= 12:
                    ev["quotes"].append({"deal_id": r["deal_id"], "quote": line.split(":", 1)[1].strip()})
                    break
            if len(ev["quotes"]) >= 3:
                break
        self.add("W1", 4, "finding",
                 "Deals with a finance leader on the second call win {a} of the time, against {b} without one. That is {x} times as often.",
                 {"a": fig(F["with_rate"], "pct", pctq({"finance_on_call2": True, "outcome": "won"}, {"finance_on_call2": True})),
                  "b": fig(F["without_rate"], "pct", pctq({"finance_on_call2": False, "outcome": "won"}, {"finance_on_call2": False})),
                  "x": fig(F["ratio"], "x", {"op": "ratio", "a": pctq({"finance_on_call2": True, "outcome": "won"}, {"finance_on_call2": True}),
                                                    "b": pctq({"finance_on_call2": False, "outcome": "won"}, {"finance_on_call2": False})})},
                 ev)
        slow_where = {"days_to_demo": {"gt": 10}}
        fast_where = {"days_to_demo": {"lte": 10}}
        self.add("W2", 4, "finding",
                 "Deals that wait more than 10 days for a demo win {a} of the time, against {b} when the demo comes within 10 days. The share of "
                 "deals that wait that long grew from {s0} in the first quarter to {s1} in the last.",
                 {"a": fig(D["slow_win_rate"], "pct", pctq({**slow_where, "outcome": "won"}, slow_where)),
                  "b": fig(D["fast_win_rate"], "pct", pctq({**fast_where, "outcome": "won"}, fast_where)),
                  "s0": fig(D["by_quarter"][Q0]["slow_share"], "pct", pctq({**slow_where, "quarter": Q0}, {"quarter": Q0})),
                  "s1": fig(D["by_quarter"][Q1]["slow_share"], "pct", pctq({**slow_where, "quarter": Q1}, {"quarter": Q1}))},
                 self.evidence(lambda r: r["outcome"] == "lost" and r.get("role") == "slow_demo"))

        # 5. recommended actions, one owner each
        n_ms = sum(1 for r in rows if r["outcome"] == "lost" and r["segment"] == "200-500" and r["role"] == "multistate")
        self.add("A1", 5, "action",
                 "Close the multi-state payroll tax gap for companies with 200–500 employees. It is the main reason for {n} lost deals, "
                 "{p} of all losses in that segment.",
                 {"n": fig(n_ms, "n", {"op": "count", "where": lossq(segment="200-500", role="multistate")}),
                  "p": fig(sh3.get("multistate", 0.0), "pct", pctq(lossq(segment="200-500", role="multistate"), lossq(segment="200-500")))},
                 self.evidence(lambda r: r["outcome"] == "lost" and r["segment"] == "200-500" and r.get("role") == "multistate"), owner="Product")
        self.add("A2", 5, "action",
                 "Book the demo within 10 days of the first call, and ask for a finance leader on the second call. Slow demos win {a} of the time "
                 "against {b} for fast ones, and a finance leader on the second call lifts the win rate to {c}.",
                 {"a": fig(D["slow_win_rate"], "pct", pctq({**slow_where, "outcome": "won"}, slow_where)),
                  "b": fig(D["fast_win_rate"], "pct", pctq({**fast_where, "outcome": "won"}, fast_where)),
                  "c": fig(F["with_rate"], "pct", pctq({"finance_on_call2": True, "outcome": "won"}, {"finance_on_call2": True}))},
                 self.evidence(lambda r: r["outcome"] == "lost" and r.get("role") == "slow_demo"), owner="Sales")
        self.add("A3", 5, "action",
                 "Fix the broker conflict. Where a broker is involved, {br} of lost deals go to a competitor the broker recommended, and "
                 "{bn} of those losses go to the low-price bundler. Agree what brokers may recommend, and bring them into the evaluation early.",
                 {"br": fig(S["broker"]["broker_role_share"], "pct", pctq(lossq(lead_source="broker", role="broker"), lossq(lead_source="broker"))),
                  "bn": fig(S["broker"]["broker_role_to_bundler_pct"], "pct", pctq(lossq(lead_source="broker", role="broker", competitor="Tallyhold"),
                                                                                    lossq(lead_source="broker", role="broker")))},
                 self.evidence(lambda r: r["outcome"] == "lost" and r["lead_source"] == "broker" and r.get("role") == "broker"),
                 owner="Marketing and Partnerships")

        # 6. what the data cannot tell us
        n_unc = sum(1 for r in rows if r["outcome"] == "lost" and r["role"] == "unclear")
        cells = [v["n"] for v in S["win_rates"]["by_quarter_segment"].values()]
        self.add("C1", 6, "caveat",
                 "{u} of {n} losses ({p}) have no clear reason in the text. They are left as unclear, not guessed.",
                 {"u": fig(n_unc, "n", {"op": "count", "where": lossq(role="unclear")}),
                  "n": fig(n_losses, "n", {"op": "count", "where": loss_all}),
                  "p": fig(100.0 * n_unc / n_losses, "pct", pctq(lossq(role="unclear"), loss_all))},
                 self.evidence(lambda r: r["outcome"] == "lost" and r.get("role") == "unclear"))
        small = min(cells)
        self.add("C2", 6, "caveat",
                 "A single segment in a single quarter holds as few as {m} deals, so one cell’s win rate moves a lot with one deal. "
                 "The quarter-to-quarter split between mix and performance rests on those small cells.",
                 {"m": fig(small, "n", {"op": "count", "where": {"quarter": Q1, "segment": "50-99"}})
                  if small == S["win_rates"]["by_quarter_segment"][f"{Q1}|50-99"]["n"] else fig(
                      small, "n", {"op": "count", "where": _cell_where(S, small)})},
                 {"deal_ids": [], "quotes": []})
        return self.claims


def _cell_where(S, small):
    for k, v in S["win_rates"]["by_quarter_segment"].items():
        if v["n"] == small:
            q, s = k.split("|")
            return {"quarter": q, "segment": s}
    raise ValueError(small)


STATIC_LIMITS = [
    "All 400 deals, buyers and companies are synthetic and were written for this project. Recovering planted patterns tests the method. "
    "It does not show the agent would be as accurate on real deals or that these causes hold in any real market.",
    "A win-rate association is not proof of cause. Slow demos, a finance leader on the call and broker involvement may travel with other things "
    "the CRM does not record.",
    "The buyers’ words come from call excerpts and some emails. What was said off the call, or never said, is not in the data.",
    "Coding is by a model reading the text; it can misread a reason. The method note reports how often it did, against the answer key.",
]


def build_brief(rows, S, codings, deals_by_id):
    b = Builder(rows, S, codings, deals_by_id)
    claims = b.build()
    return {"title": "Why Lanternmere HR is losing deals", "claims": claims, "limits": STATIC_LIMITS}
