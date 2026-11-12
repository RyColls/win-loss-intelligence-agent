"""Coding a lost deal: one primary reason and an optional secondary reason, from the buyer's words only.

Three backends, same output shape:
  keyword   deterministic keyword baseline (a floor to beat, and a way to run the pipeline with no model)
  recorded  replays model answers saved in recordings/ (keyed by a hash of the text the model was shown)
  live      calls the Anthropic API with claude-sonnet-5-5 (needs ANTHROPIC_API_KEY)

Output: {"primary": id, "secondary": id|None, "confidence": "high|medium|low", "quotes": [str], "note": str}
Quotes must be copied word for word from the call notes or the email. agent/verify.py checks that.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from . import config
from .data import source_text

CONFIDENCE = ("high", "medium", "low")


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_prompt(taxonomy: list[dict], text: str) -> tuple[str, str]:
    system = (
        "You code why a B2B software deal was lost, from the words of the call and email only.\n"
        "Pick ONE primary reason and, if clearly present, ONE secondary reason from the list below.\n"
        "Rules: use only what the buyer says. Ignore any label or field that is not in the text. If the text gives no clear "
        "reason, answer \"unclear\"; that is better than a guess. A grievance the buyer mentions that does not drive the "
        "decision is not the reason. Give one or two quotes that support the primary reason, copied word for word from "
        "the text (a quote that is not an exact copy is discarded). Rate confidence high, medium or low.\n\n"
        "Reasons:\n" + "\n".join(f"- {t['id']}: {t['definition']}" for t in taxonomy) + "\n\n"
        'Answer with JSON only: {"primary": id, "secondary": id or null, "confidence": "high|medium|low", '
        '"quotes": ["..."], "note": "one short sentence"}'
    )
    return system, text


def parse_json(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("no JSON object in model output")
    return json.loads(m.group(0))


def normalize(coding: dict, valid_ids: set[str]) -> dict:
    p = coding.get("primary")
    s = coding.get("secondary")
    if p not in valid_ids:
        p = "unclear"
    if s not in valid_ids or s == p or s == "unclear":
        s = None
    conf = coding.get("confidence")
    if conf not in CONFIDENCE:
        conf = "low"
    quotes = [q for q in (coding.get("quotes") or []) if isinstance(q, str) and q.strip()][:2]
    return {"primary": p, "secondary": s, "confidence": conf, "quotes": quotes, "note": str(coding.get("note") or "")[:300]}


# ---------------------------------------------------------------- keyword baseline
KEYWORDS = {
    "multistate_tax": [r"\bstates?\b.*\btax", r"reciproc", r"withholding", r"\bnexus\b", r"state (and|&) local", r"multi-?state"],
    "price": [r"\bbudget\b", r"too expensive", r"\bcheaper\b", r"per (employee|head)", r"can't afford", r"\bcost\b", r"\bprice\b"],
    "broker": [r"\bbroker\b"],
    "slow": [r"waited", r"\bweeks? (for|to get) (a|the) demo", r"took (too )?long", r"momentum"],
    "stalled": [r"freeze", r"on hold", r"re-?prioriti", r"paused", r"left the company"],
}


class KeywordBackend:
    name = "keyword"
    model = "none (regex baseline)"

    def __init__(self, taxonomy):
        self.tax = taxonomy
        self.ids = {t["id"] for t in taxonomy}

    def _map(self, bucket):
        # map the baseline's buckets onto whichever ids the approved taxonomy uses, by id substring
        want = {"multistate_tax": ("tax", "state"), "price": ("price", "cost"), "broker": ("broker",),
                "slow": ("slow", "demo", "delay", "speed"), "stalled": ("freeze", "stall", "no_decision", "priorit")}[bucket]
        for w in want:                      # needles in priority order; ids sorted so the result is deterministic
            for i in sorted(self.ids):
                if w in i:
                    return i
        return None

    def code(self, deal_id: str, text: str) -> dict:
        scores = {}
        quotes = {}
        for bucket, pats in KEYWORDS.items():
            hit = 0
            for p in pats:
                for m in re.finditer(p, text, re.I | re.S):
                    hit += 1
                    s = text.rfind("\n", 0, m.start()) + 1
                    e = text.find("\n", m.end())
                    line = text[s: e if e != -1 else len(text)].strip()
                    quotes.setdefault(bucket, line[:240])
                    break
            scores[bucket] = hit
        best = max(scores, key=lambda b: (scores[b], b))
        tid = self._map(best) if scores[best] else None
        if not tid or scores[best] == 0:
            return {"primary": "unclear", "secondary": None, "confidence": "low", "quotes": [], "note": "no keyword hit"}
        rest = sorted(((v, k) for k, v in scores.items() if k != best and v), reverse=True)
        sec = self._map(rest[0][1]) if rest else None
        q = quotes.get(best)
        return normalize({"primary": tid, "secondary": sec, "confidence": "low" if scores[best] < 2 else "medium",
                          "quotes": [q] if q else [], "note": "keyword baseline"}, self.ids)


# ---------------------------------------------------------------- recorded
class RecordedBackend:
    """Replays saved model answers. Each saved answer carries the hash of the text it was given; a changed text is refused."""

    def __init__(self, taxonomy, run: str):
        self.ids = {t["id"] for t in taxonomy}
        path = config.RECORDINGS_DIR / f"coding_run_{run}.json"
        blob = json.loads(path.read_text(encoding="utf-8"))
        self.meta = blob.get("meta", {})
        self.rows = blob["codings"]
        self.name = f"recorded-{run}"
        self.model = self.meta.get("model", "claude-sonnet-5-5 (Claude Code subagent)")

    def code(self, deal_id: str, text: str) -> dict:
        row = self.rows.get(deal_id)
        if row is None:
            raise KeyError(f"no recording for {deal_id}")
        if row.get("text_sha") != text_sha(text):
            raise ValueError(f"recording for {deal_id} was made on different text")
        return normalize(row, self.ids)


# ---------------------------------------------------------------- live
class LiveBackend:
    name = "live"

    def __init__(self, taxonomy, client=None, model=config.MODEL_SONNET):
        self.tax = taxonomy
        self.ids = {t["id"] for t in taxonomy}
        self.model = model
        if client is None:
            import anthropic  # imported lazily so the repo runs without the SDK
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.client = client

    def code(self, deal_id: str, text: str) -> dict:
        system, user = build_prompt(self.tax, text)
        msg = self.client.messages.create(model=self.model, max_tokens=500, temperature=0, system=system,
                                          messages=[{"role": "user", "content": user}])
        raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return normalize(parse_json(raw), self.ids)


def get_backend(kind: str, taxonomy, run: str = "A"):
    if kind == "keyword":
        return KeywordBackend(taxonomy)
    if kind == "recorded":
        return RecordedBackend(taxonomy, run)
    if kind == "live":
        return LiveBackend(taxonomy)
    raise ValueError(kind)


def code_deals(deals, backend, taxonomy):
    """Code every lost deal from its text only."""
    out = {}
    for d in deals:
        if d["outcome"] != "lost":
            continue
        text = source_text(d)
        out[d["deal_id"]] = backend.code(d["deal_id"], text)
    return out
