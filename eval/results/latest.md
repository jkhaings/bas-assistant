# Golden set and RAGAS, 2026-09-27T19:11:28+00:00

Corpus version `1`, prompt version `a3faba05b3b9`. Cost $0.0625 (answers $0.0308, RAGAS judge $0.0317).

## Golden pass rate: 21/22 (95%)

| # | Role | Category | Expect | Decision | Result |
|---|---|---|---|---|---|
| 1 | support | spec | answer | answered | pass |
| 2 | support | spec | answer | answered | pass |
| 3 | support | spec | answer | answered | pass |
| 4 | support | ordering | answer | answered | pass |
| 5 | support | ordering | answer | answered | pass |
| 6 | support | ordering | answer | answered | pass |
| 7 | support | wiring-power | answer | answered | pass |
| 8 | support | wiring-power | answer | answered | pass |
| 9 | support | wiring-power | answer | answered | pass |
| 10 | support | protocol | answer | answered | pass |
| 11 | support | protocol | answer | answered | pass |
| 12 | support | protocol | answer | answered | pass |
| 13 | support | compatibility | answer | answered | pass |
| 14 | support | compatibility | answer | answered | pass |
| 15 | support | compatibility | answer | answered | pass |
| 16 | support | out-of-scope | abstain | refused | FAIL: expected an abstain, got refused citing [] |
| 17 | support | out-of-scope | abstain | abstained | pass |
| 18 | support | out-of-scope | abstain | abstained | pass |
| 19 | support | engineer-only | abstain | abstained | pass |
| 19 | engineer | engineer-only | answer | answered | pass |
| 20 | support | engineer-only | abstain | abstained | pass |
| 20 | engineer | engineer-only | answer | answered | pass |

## RAGAS by category (answered rows; judge = `fast` alias)

| Category | n | Faithfulness | Answer relevancy | Context precision | Context recall |
|---|---|---|---|---|---|
| compatibility | 3 | 1.000 | 0.822 | 1.000 | 1.000 |
| engineer-only | 2 | 0.833 | 0.965 | 0.500 | 1.000 |
| ordering | 3 | 1.000 | 0.881 | 0.817 | 1.000 |
| protocol | 3 | 0.500 | 0.809 | 0.389 | 0.917 |
| spec | 3 | 1.000 | 0.907 | 0.956 | 1.000 |
| wiring-power | 3 | 1.000 | 1.000 | 0.900 | 1.000 |
| overall | 17 | 0.892 | 0.893 | 0.775 | 0.985 |
