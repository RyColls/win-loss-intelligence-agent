"""Step 1 of 2: generate the synthetic deals, the answer key and the writing briefs.

This step knows the answer. The analysis agent (agent/) never sees anything this script writes under
answer_key/ or gen/. It only sees data/deals.json, which holds CRM fields plus the call notes and
closing emails that were written from the briefs (datagen/assemble.py puts them together).

    python datagen/generate.py            # writes data/deals_skeleton.json, answer_key/, gen/briefs/

Everything is seeded. 400 deals, 100 per quarter, 95 wins and 305 losses (28, 26, 22, 19 wins by quarter).
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261111

COMPANY = "Lanternmere HR"          # fictional sample client
COMPETITORS = {
    "incumbent": "Brasswick Payroll",   # legacy payroll incumbent
    "bundler": "Tallyhold",             # low-price bundler that pays brokers a commission
    "multistate": "Corvane",            # newer vendor, strong in multi-state payroll
}
QUARTERS = ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"]
WINS = [28, 26, 22, 19]
SEGMENTS = ["50-99", "100-199", "200-500"]
# deals per segment per quarter: the 200-500 share grows (mix shift, planted pattern 2)
MIX = [(40, 40, 20), (36, 36, 28), (30, 34, 36), (24, 32, 44)]
MEAN_WAIT = [6.0, 7.5, 9.0, 11.0]    # mean days from first call to demo, rising (planted pattern 4)
BASE_WIN = {"50-99": 0.30, "100-199": 0.25, "200-500": 0.12}
N_TOTAL, N_WINS, N_LOSSES = 400, 95, 305
PRICE_SHARE = 0.61                   # CRM says "Price" on 61% of losses, whatever the real reason

REASONS = ["price", "multistate_tax_gap", "other_feature_gap", "broker_recommended_competitor",
           "slow_demo_followup", "no_decision", "unclear"]

FIRST = ["Maren", "Idris", "Calla", "Thaddeus", "Noor", "Bram", "Odalys", "Wren", "Soren", "Priya", "Emeka", "Linnea",
         "Tobias", "Marisol", "Kofi", "Annelise", "Dariusz", "Yuki", "Fenella", "Ravi", "Greta", "Lucian", "Imani",
         "Casper", "Beatrix", "Omar", "Signe", "Teodoro", "Nadia", "Hollis", "Ingrid", "Rafferty", "Amara", "Jules",
         "Sunniva", "Bastian", "Delphine", "Kwame", "Oriel", "Mirela"]
LAST = ["Ashgrove", "Okonkwo", "Tillbrook", "Vasquez", "Lindgren", "Parekh", "Hartigan", "Moreau", "Dunmore",
        "Fairweather", "Nakamura", "Quillfeather", "Oyelaran", "Brannigan", "Castellane", "Ivarsson", "Petrakis",
        "Whitlock", "Zeller", "Abernethy", "Rourke", "Santangelo", "Thorsen", "Underhill", "Valdivia", "Yarrow",
        "Cadogan", "Delacroix", "Eastwood", "Fonseca", "Galbraith", "Hollander", "Ibarra", "Jessamy"]
CO_A = ["Kestrel", "Marlow", "Ostrander", "Pinecrest", "Quarry", "Redfern", "Saltmarsh", "Thornfield", "Umber",
        "Vesper", "Wexcombe", "Yellowpine", "Zephyr", "Alderwick", "Brightwater", "Cobbledge", "Dunstan", "Elmcroft",
        "Fernhollow", "Gantry", "Hawkridge", "Ironbark", "Juniper", "Kingsfold", "Larkspur", "Millrace", "Nettlebed",
        "Oakhaven", "Plumtree", "Ravenscar"]
CO_B = ["Logistics", "Dental Group", "Engineering", "Foods", "Veterinary Partners", "Software", "Builders", "Labs",
        "Staffing", "Print & Pack", "Clinics", "Supply", "Media", "Energy Services", "Schools Network", "Robotics",
        "Hospitality", "Insurance Services", "Fabrication", "Analytics", "Outfitters", "Brewing", "Health Partners",
        "Design Studio", "Freight"]

TITLES_C1 = ["VP of People", "HR Director", "Head of HR", "Operations Manager", "Office Manager", "People Operations Lead",
             "Director of Operations", "HR Generalist", "COO", "Chief People Officer"]
TITLES_C2_OTHER = ["Payroll Manager", "HR Director", "Operations Director", "IT Manager", "COO", "Benefits Manager",
                   "Head of People", "Compliance Lead", "General Manager"]
FINANCE = ["CFO", "VP Finance", "Controller", "Head of Finance", "Finance Director"]

INDUSTRY_STATES = {"50-99": (1, 3), "100-199": (2, 5), "200-500": (4, 12)}
EMP_RANGE = {"50-99": (50, 99), "100-199": (100, 199), "200-500": (200, 500)}
AMOUNT_MEAN = {"50-99": 17500, "100-199": 29000, "200-500": 52000}
CRM_OTHER = ["No decision", "Went with competitor", "Missing features", "Timing / budget", "Other"]

# What the buyer should convey, in plain terms. The labels used by the analysis taxonomy never appear here.
OTHER_FEATURES = ["time-off accrual rules that differ by location", "custom multi-step approval workflows",
                  "an applicant tracking module", "automatic benefits carrier file feeds",
                  "flexible reporting for their board"]


def poisson_wait(rng, mean):
    # skewed positive waits, clipped
    v = rng.lognormvariate(math.log(max(mean, 1.0)) - 0.18, 0.6)
    return int(min(28, max(1, round(v))))


def weighted_sample_without_replacement(rng, items, weights, k):
    keyed = []
    for it, w in zip(items, weights):
        u = rng.random()
        keyed.append((u ** (1.0 / w), it))
    keyed.sort(key=lambda x: -x[0])
    return [it for _, it in keyed[:k]]


def make_deals(rng):
    deals = []
    used_cos = set()
    n = 0
    for qi, q in enumerate(QUARTERS):
        quarter_deals = []
        for si, seg in enumerate(SEGMENTS):
            for _ in range(MIX[qi][si]):
                n += 1
                lo, hi = EMP_RANGE[seg]
                src = rng.choices(["inbound", "broker", "outbound"], [0.55, 0.35, 0.10])[0]
                wait = poisson_wait(rng, MEAN_WAIT[qi])
                finance_on_call2 = rng.random() < 0.26
                c1 = rng.sample(TITLES_C1, k=rng.choice([1, 2, 2, 3]))
                c2 = rng.sample(TITLES_C2_OTHER, k=rng.choice([1, 2, 2]))
                if finance_on_call2:
                    c2 = [rng.choice(FINANCE)] + c2[: rng.choice([0, 1])]
                while True:
                    co = f"{rng.choice(CO_A)} {rng.choice(CO_B)}"
                    if co not in used_cos:
                        used_cos.add(co)
                        break
                amt = int(round(rng.lognormvariate(math.log(AMOUNT_MEAN[seg]), 0.28) / 500.0) * 500)
                quarter_deals.append({
                    "deal_id": f"D{n:03d}", "quarter": q, "segment": seg,
                    "employees": rng.randint(lo, hi), "states": rng.randint(*INDUSTRY_STATES[seg]),
                    "lead_source": src, "days_to_demo": wait, "amount": amt,
                    "rep_id": f"R{rng.randint(1, 45):02d}", "rep_tenure_months": rng.randint(3, 96),
                    "buyers_call1": c1, "buyers_call2": c2, "finance_on_call2": finance_on_call2,
                    "company": co, "buyer": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                    "buyer2": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                })
        # propensity: segment base, slow-demo halves it, a finance leader doubles it, broker deals a little lower
        props = []
        for d in quarter_deals:
            p = BASE_WIN[d["segment"]]
            if d["days_to_demo"] > 10:
                p *= 0.36
            if d["finance_on_call2"]:
                p *= 2.0
            if d["lead_source"] == "broker":
                p *= 0.75
            props.append(p)
        winners = set(id(x) for x in weighted_sample_without_replacement(rng, quarter_deals, props, WINS[qi]))
        for d in quarter_deals:
            d["outcome"] = "won" if id(d) in winners else "lost"
        deals.extend(quarter_deals)
    return deals


def assign_truth(rng, deals):
    """True primary/secondary reason for every loss, then competitor, CRM dropdown, ambiguity and false trails."""
    losses = [d for d in deals if d["outcome"] == "lost"]
    for d in losses:
        w = {"price": 0.05, "multistate_tax_gap": 0.0, "other_feature_gap": 0.09, "broker_recommended_competitor": 0.0,
             "slow_demo_followup": 0.07, "no_decision": 0.14}
        seg = d["segment"]
        if seg == "50-99":
            w["price"] += 0.60
        elif seg == "100-199":
            w["price"] += 0.06
            w["other_feature_gap"] += 0.05
        else:
            w["multistate_tax_gap"] += 0.78
            w["price"] -= 0.02
        if d["lead_source"] == "broker":
            w["broker_recommended_competitor"] += 0.55
        if d["days_to_demo"] > 10:
            w["slow_demo_followup"] += 0.36
        keys = list(w)
        d["true_primary"] = rng.choices(keys, [max(w[k], 0.0001) for k in keys])[0]
        # a secondary reason on about 40% of losses
        if rng.random() < 0.40:
            sec_pool = [k for k in keys if k != d["true_primary"]]
            d["true_secondary"] = rng.choices(sec_pool, [max(w[k], 0.02) for k in sec_pool])[0]
        else:
            d["true_secondary"] = None
    # ambiguous: about 10% of deals have no clear reason in the text (all are losses)
    amb = rng.sample(losses, k=round(0.10 * len(deals)))
    for d in amb:
        d["true_primary"], d["true_secondary"], d["ambiguous"] = "unclear", None, True
    for d in deals:
        d.setdefault("ambiguous", False)
    # competitor field
    for d in deals:
        r = d.get("true_primary")
        if r == "broker_recommended_competitor":
            c = "bundler"
        elif r == "multistate_tax_gap":
            c = rng.choices(["multistate", "incumbent", "bundler"], [0.6, 0.25, 0.15])[0]
        elif r == "price":
            c = rng.choices(["bundler", "incumbent", "none"], [0.55, 0.25, 0.20])[0]
        elif r == "no_decision":
            c = "none"
        else:
            c = rng.choices(["incumbent", "bundler", "multistate", "none"], [0.3, 0.25, 0.2, 0.25])[0]
        if d["outcome"] == "won":
            c = rng.choices(["incumbent", "bundler", "multistate", "none"], [0.28, 0.25, 0.17, 0.30])[0]
        d["competitor"] = "none" if c == "none" else COMPETITORS[c]
    # CRM loss reason: "Price" on exactly 61% of losses, whatever the real reason was
    n_price = round(PRICE_SHARE * len(losses))
    price_true = [d for d in losses if d["true_primary"] == "price"]
    others = [d for d in losses if d["true_primary"] != "price"]
    rng.shuffle(others)
    chosen = list(price_true)
    chosen += others[: max(0, n_price - len(price_true))]
    chosen_ids = {d["deal_id"] for d in chosen[:n_price]}
    for d in deals:
        if d["outcome"] != "lost":
            d["crm_loss_reason"] = None
        elif d["deal_id"] in chosen_ids:
            d["crm_loss_reason"] = "Price"
        else:
            d["crm_loss_reason"] = rng.choice(CRM_OTHER)
    # false trail: a mobile-app complaint in 8 transcripts, unrelated to the outcome or the reason
    mobile_ids = {d["deal_id"] for d in rng.sample(deals, 8)}
    for d in deals:
        d["mobile_complaint"] = d["deal_id"] in mobile_ids
    # closing email on about a third of the deals
    for d in deals:
        d["has_email"] = rng.random() < 0.34
    return deals


def reason_guidance(d, rng):
    """Plain-language instruction for the writer: what the buyer is really thinking. No taxonomy labels."""
    st = d["states"]
    def one(r):
        if r == "price":
            return ("Money is the real obstacle. The yearly cost does not fit their budget and a cheaper option exists; "
                    "the buyer says so directly in their own words, with a rough per-employee or yearly number.")
        if r == "multistate_tax_gap":
            return (f"They have employees in {st} states. The buyer is worried about how our payroll handles state and local "
                    "payroll taxes: registrations, filings, reciprocity between neighboring states, mid-year moves. Give one or "
                    "two concrete situations they asked about where our answer was thin or 'we'd have to check'. Price may come "
                    "up once in passing but is NOT the reason; they would pay our price if the tax handling were solid.")
        if r == "other_feature_gap":
            return f"A specific missing capability decided it: {rng.choice(OTHER_FEATURES)}. Not tax handling, not price."
        if r == "broker_recommended_competitor":
            return (f"Their benefits broker recommended {COMPETITORS['bundler']} and the buyer is following that advice because "
                    "they trust the broker and the broker handles their renewals. The buyer mentions the broker by role "
                    "('our broker') and says the bundle is what the broker put in front of them.")
        if r == "slow_demo_followup":
            return (f"They waited {d['days_to_demo']} days between the first call and the demo. By the time it happened the "
                    "momentum or the sponsor's patience was gone and they had started something else. The buyer mentions the "
                    "wait explicitly.")
        if r == "no_decision":
            return ("The project stalled: a budget freeze, a change of priorities or a sponsor leaving. They did not pick any "
                    "vendor. Nothing is wrong with the product or the price.")
        return ""
    if d["outcome"] == "won":
        base = (f"They chose {COMPANY}. The buyer explains in their own words what convinced them (pick one or two: the demo "
                "answered their real questions, support felt responsive, implementation plan was clear).")
        if d["finance_on_call2"]:
            base += " The finance leader on the second call asked pointed questions and ended up supportive."
        if d["days_to_demo"] <= 6:
            base += " The demo happened quickly after the first call and they liked that."
        return base
    if d["ambiguous"]:
        return ("The buyer is polite but vague: they are 'going a different direction' or 'making a change', and never says why. "
                "Do NOT hint at price, features, brokers, timing or anything that would reveal a reason. Keep it friendly and empty.")
    g = one(d["true_primary"])
    if d["true_secondary"]:
        g += " Secondary, mentioned briefly and clearly less important: " + one(d["true_secondary"]).split(".")[0] + "."
    return g


def write_briefs(rng, deals, n_batches=10):
    voices = ["brisk and practical", "chatty, thinks out loud", "formal and careful", "tired and candid",
              "friendly, a little rambling", "direct, short sentences", "analytical, cites specifics"]
    briefs = []
    for d in deals:
        words = rng.randint(170, 380)
        e_words = rng.randint(45, 110)
        brief = {
            "deal_id": d["deal_id"], "outcome": d["outcome"], "our_company": COMPANY,
            "prospect_company": d["company"], "segment_employees": d["employees"], "states_with_employees": d["states"],
            "lead_source": d["lead_source"], "competitor_in_crm": d["competitor"], "days_from_first_call_to_demo": d["days_to_demo"],
            "buyer_name": d["buyer"], "buyer_titles_call1": d["buyers_call1"], "second_buyer_name": d["buyer2"],
            "buyer_titles_call2": d["buyers_call2"], "voice": rng.choice(voices), "target_words_call_notes": words,
            "what_the_buyer_conveys": reason_guidance(d, rng),
            "include_mobile_app_complaint": d["mobile_complaint"],
            "write_closing_email": d["has_email"], "target_words_email": e_words,
        }
        briefs.append(brief)
    size = math.ceil(len(briefs) / n_batches)
    out = []
    for i in range(n_batches):
        chunk = briefs[i * size:(i + 1) * size]
        p = ROOT / "gen" / "briefs" / f"batch_{i + 1:02d}.json"
        p.write_text(json.dumps(chunk, indent=1, ensure_ascii=False), encoding="utf-8")
        out.append(p.name)
    return out


def main():
    rng = random.Random(SEED)
    deals = make_deals(rng)
    deals = assign_truth(rng, deals)
    assert len(deals) == N_TOTAL
    assert sum(d["outcome"] == "won" for d in deals) == N_WINS
    for q, w in zip(QUARTERS, WINS):
        assert sum(1 for d in deals if d["quarter"] == q and d["outcome"] == "won") == w
    assert sum(d["crm_loss_reason"] == "Price" for d in deals) == round(PRICE_SHARE * N_LOSSES)
    write_briefs(rng, deals)

    # public skeleton: CRM fields only (call notes and emails are added by assemble.py)
    pub_fields = ["deal_id", "quarter", "segment", "lead_source", "competitor", "amount", "days_to_demo", "outcome",
                  "rep_id", "rep_tenure_months", "buyers_call1", "buyers_call2", "crm_loss_reason", "company"]
    skeleton = [{k: d[k] for k in pub_fields} for d in deals]
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "deals_skeleton.json").write_text(json.dumps(skeleton, indent=1, ensure_ascii=False), encoding="utf-8")

    key = {
        "note": "Answer key. The analysis agent never reads this file. Published so a reader can see the test was fair.",
        "seed": SEED, "company": COMPANY, "competitors": COMPETITORS,
        "planted_patterns": {
            "P1_feature_gap_upmarket": "200-500 segment: most losses are weak multi-state payroll tax handling; CRM says Price",
            "P2_mix_shift": "share of 200-500 deals grows each quarter: " + ", ".join(f"{q}={m[2]}%" for q, m in zip(QUARTERS, MIX)),
            "P3_broker_conflict": "broker-sourced deals lose to the bundler because the broker recommended it",
            "P4_slow_demos": "deals waiting more than 10 days for a demo win at half the rate; mean wait by quarter " + str(MEAN_WAIT),
            "P5_finance_leader": "a finance leader on the second call roughly doubles the win rate",
            "P6_price_real_in_one_place": "price is the true main reason only in the 50-99 segment",
        },
        "false_trails": {
            "F1_rep_tenure": "rep tenure is random and unrelated to outcome",
            "F2_mobile_app_complaint": "vivid mobile-app complaint in 8 transcripts, unrelated to outcome or reason",
        },
        "ambiguous_losses": [d["deal_id"] for d in deals if d["ambiguous"]],
        "mobile_complaint_deals": [d["deal_id"] for d in deals if d["mobile_complaint"]],
        "deals": {d["deal_id"]: {"outcome": d["outcome"], "segment": d["segment"], "quarter": d["quarter"],
                                 "true_primary": d.get("true_primary"), "true_secondary": d.get("true_secondary"),
                                 "ambiguous": d["ambiguous"], "finance_on_call2": d["finance_on_call2"],
                                 "rep_tenure_months": d["rep_tenure_months"]} for d in deals},
    }
    (ROOT / "answer_key" / "answer_key.json").write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    # summary to the console
    from collections import Counter
    L = [d for d in deals if d["outcome"] == "lost"]
    print("wins by quarter:", {q: sum(1 for d in deals if d["quarter"] == q and d["outcome"] == "won") for q in QUARTERS})
    for seg in SEGMENTS:
        c = Counter(d["true_primary"] for d in L if d["segment"] == seg)
        print(seg, "losses", sum(c.values()), dict(c.most_common()))
    print("win rate wait>10:", round(sum(d["outcome"] == "won" for d in deals if d["days_to_demo"] > 10) / max(1, sum(1 for d in deals if d["days_to_demo"] > 10)), 3),
          "wait<=10:", round(sum(d["outcome"] == "won" for d in deals if d["days_to_demo"] <= 10) / max(1, sum(1 for d in deals if d["days_to_demo"] <= 10)), 3))
    print("win rate finance:", round(sum(d["outcome"] == "won" for d in deals if d["finance_on_call2"]) / sum(1 for d in deals if d["finance_on_call2"]), 3),
          "no finance:", round(sum(d["outcome"] == "won" for d in deals if not d["finance_on_call2"]) / sum(1 for d in deals if not d["finance_on_call2"]), 3))
    print("ambiguous:", len(key["ambiguous_losses"]), "emails:", sum(d["has_email"] for d in deals))


if __name__ == "__main__":
    main()
