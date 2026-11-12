import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import config, numcheck, stats, verify  # noqa: E402
from agent.cli import run  # noqa: E402
from agent.coder import LiveBackend, RecordedBackend, KeywordBackend, normalize, text_sha  # noqa: E402
from agent.data import coder_view, load_deals, load_taxonomy, source_text  # noqa: E402

DEALS = load_deals()
TAX = load_taxonomy()
IDS = {t["id"] for t in TAX}


# ---------------------------------------------------------------- dataset spec
def test_dataset_counts():
    assert len(DEALS) == 400
    wins = [sum(1 for d in DEALS if d["quarter"] == q and d["outcome"] == "won") for q in config.QUARTERS]
    assert wins == [28, 26, 22, 19]
    assert all(sum(1 for d in DEALS if d["quarter"] == q) == 100 for q in config.QUARTERS)


def test_crm_says_price_on_61_percent_of_losses():
    losses = [d for d in DEALS if d["outcome"] == "lost"]
    assert len(losses) == 305
    assert sum(d["crm_loss_reason"] == "Price" for d in losses) == round(0.61 * 305)


def test_text_lengths_and_emails():
    for d in DEALS:
        assert 150 <= len(d["call_notes"].split()) <= 400, d["deal_id"]
    share = sum(1 for d in DEALS if d["closing_email"]) / 400
    assert 0.25 <= share <= 0.40


def test_public_deals_carry_no_answer():
    banned = {"true_primary", "true_secondary", "ambiguous", "mobile_complaint", "finance_on_call2"}
    assert not banned & set(DEALS[0])


# ---------------------------------------------------------------- isolation
def test_coder_sees_only_the_words():
    v = coder_view(DEALS[0])
    assert set(v) == {"deal_id", "call_notes", "closing_email"}


def test_agent_code_never_names_the_answer_key():
    for p in (ROOT / "agent").glob("*.py"):
        src = p.read_text(encoding="utf-8")
        code = "\n".join(l for l in src.split("\n") if not l.strip().startswith(("#", '"""')) and "never" not in l.lower())
        assert not re.search(r"open\(|read_text\(", code) or "answer_key" not in code, p.name
        assert '"answer_key"' not in src and "'answer_key'" not in src and '"gen"' not in src, p.name


def test_pipeline_runs_without_answer_key_or_briefs(tmp_path):
    for name in ("agent", "data", "taxonomy", "recordings"):
        shutil.copytree(ROOT / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__", "in", "out"))
    r = subprocess.run([sys.executable, "-m", "agent.cli", "--backend", "recorded", "--run", "A"], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "results" / "recorded_A" / "brief.json").exists()


# ---------------------------------------------------------------- quote check
def test_exact_quote_passes_and_altered_quote_is_removed():
    d = next(x for x in DEALS if x["outcome"] == "lost")
    real = d["call_notes"].split("\n")[1].split(":", 1)[1].strip()[:60]
    good = {"primary": "price_over_budget", "secondary": None, "confidence": "high", "quotes": [real], "note": ""}
    out, st = verify.check_coding(d, good)
    assert st["failed"] == 0 and not out["dropped"]
    bad = dict(good, quotes=[real[:-3] + "xyz"])
    out, st = verify.check_coding(d, bad)
    assert st["failed"] == 1 and out["dropped"] and out["primary"] == "unclear" and out["quotes"] == []


def test_paraphrase_and_fixed_typo_fail():
    d = DEALS[1]
    q = source_text(d)[40:90]
    assert verify.quote_ok(q, source_text(d))
    assert not verify.quote_ok(q.upper(), source_text(d))
    assert not verify.quote_ok(q.replace(" ", "  ", 1), source_text(d))


def test_unclear_needs_no_quote():
    out, _ = verify.check_coding(DEALS[0], {"primary": "unclear", "secondary": None, "confidence": "low", "quotes": [], "note": ""})
    assert not out["dropped"]


# ---------------------------------------------------------------- coder backends
def test_normalize_rejects_unknown_ids():
    c = normalize({"primary": "made_up", "secondary": "unclear", "confidence": "certain", "quotes": ["a", "b", "c"]}, IDS)
    assert c["primary"] == "unclear" and c["secondary"] is None and c["confidence"] == "low" and len(c["quotes"]) == 2


def test_recorded_backend_refuses_changed_text():
    b = RecordedBackend(TAX, "A")
    d = next(x for x in DEALS if x["outcome"] == "lost")
    assert b.code(d["deal_id"], source_text(d))["primary"] in IDS
    with pytest.raises(ValueError):
        b.code(d["deal_id"], source_text(d) + " edited")


def test_keyword_backend_is_deterministic():
    b = KeywordBackend(TAX)
    d = next(x for x in DEALS if x["outcome"] == "lost")
    assert b.code(d["deal_id"], source_text(d)) == KeywordBackend(TAX).code(d["deal_id"], source_text(d))


def test_live_backend_with_fake_client():
    class Block:
        type = "text"
        text = 'Sure. {"primary": "tax_confidence", "secondary": null, "confidence": "high", "quotes": ["x"], "note": "n"}'

    class Fake:
        def __init__(self):
            self.messages = self
            self.seen = None

        def create(self, **kw):
            self.seen = kw
            return type("M", (), {"content": [Block()]})()
    f = Fake()
    out = LiveBackend(TAX, client=f).code("D001", "some text")
    assert out["primary"] == "tax_confidence" and f.seen["model"] == config.MODEL_SONNET
    assert "CRM" not in f.seen["messages"][0]["content"]


# ---------------------------------------------------------------- numbers
@pytest.fixture(scope="module")
def result():
    return run("recorded", "A", out_name="_test")


def test_every_brief_figure_recomputes(result):
    assert result["checks"]["numbers"]["problems"] == []
    assert result["checks"]["numbers"]["figures_checked"] >= 40


def test_tampered_figure_and_stray_number_are_caught(result):
    rows = json.loads((config.RESULTS_DIR / "_test" / "coded_table.json").read_text())
    c = json.loads(json.dumps(result["brief"]["claims"][1]))
    name = next(iter(c["figures"]))
    c["figures"][name]["value"] += 3
    assert any("stored" in p for p in numcheck.check_claim(c, rows))
    c2 = json.loads(json.dumps(result["brief"]["claims"][1]))
    c2["text"] += " That is 77 deals."
    assert any("numeral 77" in p for p in numcheck.check_claim(c2, rows))


def test_mix_plus_performance_equals_total(result):
    rows = json.loads((config.RESULTS_DIR / "_test" / "coded_table.json").read_text())
    d = stats.decomposition(rows)
    assert abs(d["mix_pts"] + d["performance_pts"] - d["total_pts"]) < 1e-9


def test_quotes_in_brief_are_exact(result):
    by = {d["deal_id"]: d for d in DEALS}
    n = 0
    for c in result["brief"]["claims"]:
        for q in c["evidence"]["quotes"]:
            n += 1
            assert q["quote"] in source_text(by[q["deal_id"]])
    assert n >= 20


def test_reasons_are_never_taken_from_the_crm(result):
    # shuffle the CRM field: codings must not change, because coders never see it
    import random
    deals = json.loads(json.dumps(DEALS))
    vals = [d["crm_loss_reason"] for d in deals]
    random.Random(1).shuffle(vals)
    b = RecordedBackend(TAX, "A")
    for d, v in zip(deals, vals):
        d["crm_loss_reason"] = v
    for d, o in zip(deals[:60], DEALS[:60]):
        if d["outcome"] == "lost":
            assert b.code(d["deal_id"], source_text(d)) == b.code(o["deal_id"], source_text(o))


def test_teardown():
    shutil.rmtree(config.RESULTS_DIR / "_test", ignore_errors=True)
