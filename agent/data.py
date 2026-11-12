"""Loading. The agent reads data/deals.json and nothing else from data/. It never opens answer_key/ or gen/."""
from __future__ import annotations

import json
from . import config


def load_deals():
    return json.loads(config.DEALS_PATH.read_text(encoding="utf-8"))


def load_taxonomy():
    return json.loads(config.TAXONOMY_PATH.read_text(encoding="utf-8"))


def coder_view(deal: dict) -> dict:
    """What a coder is allowed to see: the words only. No CRM loss reason, no segment, no outcome flags."""
    return {"deal_id": deal["deal_id"], "call_notes": deal["call_notes"], "closing_email": deal.get("closing_email")}


def source_text(deal: dict) -> str:
    parts = [deal["call_notes"]]
    if deal.get("closing_email"):
        parts.append(deal["closing_email"])
    return "\n\n".join(parts)
