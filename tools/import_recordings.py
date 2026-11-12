"""Merge the coding agents' batch outputs into recordings/coding_run_<RUN>.json, stamping each with the hash of the
text it was given so a replay on changed text is refused.  python tools/import_recordings.py A"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.coder import text_sha  # noqa: E402


def main(run: str) -> int:
    texts = {}
    for p in sorted((ROOT / "recordings" / "in").glob("batch_*.json")):
        for row in json.loads(p.read_text(encoding="utf-8")):
            texts[row["deal_id"]] = row["text"]
    out, missing = {}, []
    for p in sorted((ROOT / "recordings" / "out" / run).glob("batch_*.json")):
        for did, c in json.loads(p.read_text(encoding="utf-8")).items():
            if did in texts:
                out[did] = {**c, "text_sha": text_sha(texts[did])}
    missing = sorted(set(texts) - set(out))
    if missing:
        print(f"run {run}: {len(missing)} deals missing, e.g. {missing[:5]}")
        return 1
    blob = {"meta": {"run": run, "model": "claude-sonnet-5-5 (Claude Code subagent)", "prompt": "recordings/PROMPT.md",
                     "n": len(out)}, "codings": dict(sorted(out.items()))}
    (ROOT / "recordings" / f"coding_run_{run}.json").write_text(json.dumps(blob, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"run {run}: {len(out)} codings saved")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
