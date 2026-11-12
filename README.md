# Win/loss intelligence agent

A proof of concept for an **analysis agent**. It reads 400 closed deals, codes why each one was lost from what
the buyer said on the call, and writes a two-page board brief in which every claim links to the quotes and deals
behind it. Code does all the counting and checks every quote and number before it reaches the brief.

> **Everything here is fictional.** Lanternmere HR (a made-up HR and payroll company), its people, its three
> competitors and all 400 deals are invented: synthetic deals with planted patterns, written for this project.
> Recovering planted patterns tests the method. It does not prove the agent would be as accurate on real deals.
> Nothing here is a finding about a real company or market, and nothing is deployed.

👉 [Open the brief](https://rycolls.github.io/win-loss-intelligence-agent/), one web page with the board brief, its
evidence and the test results. Click any marked claim to see the buyer quotes and deals behind it. GitHub shows
`.html` files as code instead of rendering them, so use that link. The page source is `docs/index.html`.

The brief as plain text: [BRIEF.md](BRIEF.md).

## The question

The sample client's win rate fell from 28% to 19% in four quarters. Sales says the product is too expensive, Product
says features are missing, Marketing says the broker channel sends weak leads. The CRM loss reason says "Price" on
61% of losses, and the revenue chief does not believe it.

## What the agent found

| Theory | Verdict | Why |
|---|---|---|
| Sales: we are too expensive | Partly supported | Price is the main reason for 20% of losses overall: 44% in 50–99 employee deals, 1% in 200–500 |
| Product: we are missing features | Partly supported | A missing capability is the main reason for 58% of losses in 200–500 employee deals, mostly multi-state payroll tax handling, against 6% in 50–99 |
| Marketing: brokers send weak leads | Partly supported | Broker deals win less often (19% against 27%), but 34% of broker losses happen because the broker recommended a competitor. That is a channel conflict |

Of the 9.0-point drop in win rate, 3.8 points come from selling to more large companies and 5.2 from winning less
within each company size. Two things go with winning: a demo within 10 days (27% win rate against 14%) and a finance
leader on the second call (34% against 20%).

## How it works

```
step 1 (knows the answer)                      step 2 (never sees the answer)
datagen/generate.py -> answer_key/, gen/briefs  taxonomy from a 40-loss sample (Haiku gathers, Sonnet proposes)
Sonnet writes calls and emails from the briefs  Sonnet codes each loss from the call text only
datagen/assemble.py -> data/deals.json   --->   code: quote check -> coded table -> counts -> brief -> number check
                                                evals/score.py compares the result with the answer key
```

| Job | Done by | Check in code |
|---|---|---|
| Pull reason phrases from a 40-deal sample | Claude Haiku | None needed: input to the taxonomy only |
| Propose the reason categories | Claude Sonnet | Fixed in `taxonomy/taxonomy.json` before coding |
| Code each loss: main reason, optional second reason, confidence, quotes | Claude Sonnet | Every quote must match the call word for word, or it is removed with its claim (`agent/verify.py`) |
| Count, split mix from performance, rule on the theories | Code (`agent/stats.py`) | A second module with its own arithmetic recomputes every figure in the brief (`agent/numcheck.py`) |
| Write the brief | Code templates around computed figures (`agent/brief.py`) | Any numeral in a claim that is not one of its checked figures fails the build |

The coder is shown the call notes and the closing email. It is never shown the CRM loss reason, the company size
or the answer key.

## Test results

Scored against `answer_key/answer_key.json` after the analysis finished. Full report:
[results/recorded_A/scores.md](results/recorded_A/scores.md).

| Check | Target | Measured |
|---|---|---|
| Pattern recovery | All 6 planted patterns found | 6 of 6 |
| False findings | 0 | 0 (rep tenure and a planted mobile-app complaint were tested and left out) |
| Coding accuracy | Report it | 305 of 305 losses match on the main reason; 23 of 89 planted secondary reasons recovered (26%) |
| Quote integrity | 100% | 381 of 381 coder quotes are exact matches |
| Number integrity | 100% | 49 of 49 figures matched the independent recount |
| Calibration | Report both | High confidence 284 of 284 correct; medium 21 of 21. None rated low |
| Stability | Report disagreements | Two full runs agree on the main reason for 305 of 305 losses, on the secondary for 299 |

**Read the 100% with care.** A perfect match says the test was too easy more than it says the agent is perfect. In
these synthetic calls a buyer who has a reason states it fairly plainly. For scale, a keyword-matching baseline
(`--backend keyword`) matched 207 of 305 (68%) and found 4 of 6 patterns, and the CRM dropdown's "Price" was right
on 61 of 186 losses (33%). The harder measure is the secondary reason, where the agent recovered about a quarter.

## Where it is weak

- Secondary reasons are mostly missed.
- Confidence could not be tested, because nothing was wrong.
- The seven reason categories came from a 40-deal sample and were accepted as proposed, with no second reviewer.
- The model answers were recorded from Claude Sonnet and Haiku running as Claude Code subagents and are replayed
  from `recordings/`. The direct API backend (`--backend live`) is unit-tested against a fake client but was not
  run against the live API in this build.
- Seven of the 400 generated call notes came back under 150 words and were extended by hand with neutral small
  talk. The brief asked for the client to be called Harborlight HR; it was renamed because real businesses use
  similar names.
- Win-rate gaps are associations in 400 synthetic deals, not proof of cause.

## Run it

Python 3.11 or newer. No API key is needed for the recorded and keyword backends.

```
pip install -r requirements-dev.txt
python -m pytest                                          # 20 tests
python -m agent.cli --backend recorded --run A            # run the analysis from recorded model answers
python -m evals.score --run recorded_A --second recorded_B
python demo/build.py                                      # rebuild docs/index.html
python datagen/generate.py                                # regenerate the skeleton, answer key and writing briefs
# live model: ANTHROPIC_API_KEY=... pip install anthropic && python -m agent.cli --backend live
```

## Layout

| Path | What it is |
|---|---|
| `datagen/` | Seeded generator and assembler (step 1) |
| `gen/` | The generation prompt, the per-deal writing briefs and the written calls |
| `answer_key/` | The planted patterns and each deal's true reason. Never read by `agent/` |
| `data/deals.json` | The 400 deals as the agent sees them |
| `taxonomy/` | The sample, the gathered phrases, the approved reason categories |
| `agent/` | Coder backends, quote check, counting, brief builder, number check |
| `recordings/` | The coding prompt, inputs and both recorded runs |
| `evals/score.py` | The seven checks |
| `results/` | Outputs and scores for both recorded runs and the keyword baseline |
| `demo/`, `docs/` | The page builder and the built page |

MIT licensed. A proof of concept by Ryan Collins.
