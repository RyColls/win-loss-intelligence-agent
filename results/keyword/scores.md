# Scores: keyword (none (regex baseline))

Scored against `answer_key/answer_key.json`, which the analysis never reads. Synthetic deals with planted patterns: these scores test the method and do not show how it would do on real deals.

| Check | Target | Result |
|---|---|---|
| Pattern recovery | All 6 planted patterns found | 4 of 6 |
| False findings | 0 | 0 |
| Coding accuracy | Report | 207 of 305 losses (67.9%) |
| Quote integrity | 100% | 100% of quotes in the brief; 0 of 239 coder quotes failed the check and were removed |
| Number integrity | 100% | 49 of 49 figures recomputed and matched |
| Calibration | Report | low: 115 of 198 (58%); medium: 92 of 107 (86%) |

## Planted patterns

- MISSED: P1 Feature gap upmarket. 200-500 losses: multi-state tax is the top reason at 38%; CRM says Price on 58% of them
- FOUND: P2 Mix shift. 200-500 share 20% to 44%; mix explains 3.8 of 9.0 points
- FOUND: P3 Broker conflict. 33% of broker losses coded broker-recommended (vs 0% elsewhere); 85% of those went to the bundler
- FOUND: P4 Slow demos. win rate 14% after a wait over 10 days vs 27%; slow share 16% to 41%
- FOUND: P5 Finance leader on call two. 34% with a finance leader vs 20% without (1.7x)
- MISSED: P6 Price is real in one place. top reason by segment: {'50-99': 'price', '100-199': 'price', '200-500': 'multistate'}

## False trails

- Rep tenure: tested: won 44 months vs lost 48, p=0.22; not reported as a finding
- Mobile app complaint: tested: 18 deals mention it, win rate 11% vs 24%, p=0.27; not reported as a finding

## Coding accuracy by true reason

| True reason | Agree | n | % |
|---|---|---|---|
| Broker recommended a competitor | 34 | 41 | 83% |
| Other missing capability | 0 | 28 | 0% |
| Multi-state payroll tax | 40 | 57 | 70% |
| Price | 58 | 61 | 95% |
| Slow demo | 15 | 45 | 33% |
| Project stalled | 22 | 33 | 67% |
| Unclear (no reason in the text) | 38 | 40 | 95% |

Of the 98 disagreements, 20 chose the deal's true secondary reason as primary.
Secondary reasons: 11 of the 89 planted secondary reasons were recovered (12%); 47 were coded where none was planted.
For scale: the CRM dropdown said Price on 186 losses and was right on 61 (33%).
