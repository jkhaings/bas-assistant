# Golden set and RAGAS, 2026-09-27T23:35:06+00:00

Corpus version `2.112.2026-09-27T23:17:56.018010+00:00`, prompt version `a2d7b390625a`. Cost $0.0529 (answers $0.0220, RAGAS judge $0.0309).

## Golden pass rate: 22/22 (100%)

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
| 16 | support | out-of-scope | abstain | abstained | pass |
| 17 | support | out-of-scope | abstain | abstained | pass |
| 18 | support | out-of-scope | abstain | abstained | pass |
| 19 | support | engineer-only | abstain | abstained | pass |
| 19 | engineer | engineer-only | answer | answered | pass |
| 20 | support | engineer-only | abstain | abstained | pass |
| 20 | engineer | engineer-only | answer | answered | pass |

## RAGAS by category (answered rows; judge = `fast` alias)

| Category | n | Faithfulness | Answer relevancy | Context precision | Context recall |
|---|---|---|---|---|---|
| compatibility | 3 | 1.000 | 0.824 | 0.983 | 1.000 |
| engineer-only | 2 | 0.528 | 0.982 | 0.500 | 1.000 |
| ordering | 3 | 1.000 | 0.922 | 0.889 | 1.000 |
| protocol | 3 | 0.111 | 0.811 | 0.750 | 1.000 |
| spec | 3 | 0.889 | 0.907 | 0.722 | 1.000 |
| wiring-power | 3 | 0.806 | 1.000 | 1.000 | 1.000 |
| overall | 17 | 0.734 | 0.903 | 0.825 | 1.000 |
