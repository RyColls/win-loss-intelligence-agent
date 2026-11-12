# Scores: recorded_B (claude-sonnet-5-5 (Claude Code subagent))

Scored against `answer_key/answer_key.json`, which the analysis never reads. Synthetic deals with planted patterns: these scores test the method and do not show how it would do on real deals.

| Check | Target | Result |
|---|---|---|
| Pattern recovery | All 6 planted patterns found | 6 of 6 |
| False findings | 0 | 0 |
| Coding accuracy | Report | 305 of 305 losses (100.0%) |
| Quote integrity | 100% | 100% of quotes in the brief; 0 of 353 coder quotes failed the check and were removed |
| Number integrity | 100% | 49 of 49 figures recomputed and matched |
| Calibration | Report | high: 285 of 285 (100%); medium: 20 of 20 (100%) |

## Planted patterns

- FOUND: P1 Feature gap upmarket. 200-500 losses: multi-state tax is the top reason at 54%; CRM says Price on 53% of them
- FOUND: P2 Mix shift. 200-500 share 20% to 44%; mix explains 3.8 of 9.0 points
- FOUND: P3 Broker conflict. 34% of broker losses coded broker-recommended (vs 0% elsewhere); 100% of those went to the bundler
- FOUND: P4 Slow demos. win rate 14% after a wait over 10 days vs 27%; slow share 16% to 41%
- FOUND: P5 Finance leader on call two. 34% with a finance leader vs 20% without (1.7x)
- FOUND: P6 Price is real in one place. top reason by segment: {'50-99': 'price', '100-199': 'slow_demo', '200-500': 'multistate'}

## False trails

- Rep tenure: tested: won 44 months vs lost 48, p=0.22; not reported as a finding
- Mobile app complaint: tested: 18 deals mention it, win rate 11% vs 24%, p=0.27; not reported as a finding

## Coding accuracy by true reason

| True reason | Agree | n | % |
|---|---|---|---|
| Broker recommended a competitor | 41 | 41 | 100% |
| Other missing capability | 28 | 28 | 100% |
| Multi-state payroll tax | 57 | 57 | 100% |
| Price | 61 | 61 | 100% |
| Slow demo | 45 | 45 | 100% |
| Project stalled | 33 | 33 | 100% |
| Unclear (no reason in the text) | 40 | 40 | 100% |

Of the 0 disagreements, 0 chose the deal's true secondary reason as primary.
Secondary reasons: 25 of the 89 planted secondary reasons were recovered (28%); 0 were coded where none was planted.
For scale: the CRM dropdown said Price on 186 losses and was right on 61 (33%).
