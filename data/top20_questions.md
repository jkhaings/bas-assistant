# Top 20 questions

The golden set: twenty questions a Delta Controls support or sales desk would plausibly get,
each derived from the real ingested corpus (`make ingest`, Sep 27 2026 run — 70 catalog PDFs,
42 product pages, 1502 chunks). Session C turns this table into `eval/golden.jsonl`.

Page numbers are the PDF's own printed page (1-indexed), matching `citations[].page` in the
`/ask` response.

| # | Question | Category | Expected document | Page | Expected fact |
|---|---|---|---|---|---|
| 1 | How many inputs and outputs does the eZNT-T331 network thermostat have? | spec | eZNT-T331 Catalog Sheet | 1 | 3 universal inputs, 3 analog outputs, 1 binary output |
| 2 | How many inputs does the Red5-PLUS-1180 base unit have? | spec | Red5-PLUS-1180 Catalog Sheet | 1 | 11 universal inputs (16-bit): 0–5 VDC, 0–10 VDC, 10 kΩ thermistor, 4–20 mA |
| 3 | What processor and memory does the Red5-PLUS-1146 controller use? | spec | Red5-PLUS-1146 Catalog Sheet | 2 | 32-bit ARM processor, 512 MB RAM, 8 GB flash memory |
| 4 | How do I order an eBM-800 I/O module? | ordering | eBM-800 Catalog Sheet | 2 | Ordered by product number; base module is "eBM-800: enteliBUS I/O module with 8 universal inputs" |
| 5 | What enteliVAULT editions are available? | ordering | enteliVAULT Catalog Sheet | 3 | Available as an enteliWEB add-on in 200, 500, 1000, 2500, and Enterprise editions |
| 6 | What does the eZNTW product number format mean? | ordering | eZNTW Catalog Sheet | 3 | Format is eZNTW-ww-xxx-aaa-B-cc-ddd-eee, each letter group a configurable option |
| 7 | What is the power requirement for the eBM-800 I/O module? | wiring-power | eBM-800 Catalog Sheet | 2 | 24 VAC/VDC, 50/60 Hz @ 5 VA, supplied from an eBX or eBCON-2 through the backplane |
| 8 | What is the power draw of the Red5-PLUS-1180? | wiring-power | Red5-PLUS-1180 Catalog Sheet | 1 | 24 VDC (20 W max); 24 VAC @ 50 VA, 100 VA max fully loaded |
| 9 | What is the power draw of the eZNTW with the Wi-Fi option? | wiring-power | eZNTW Catalog Sheet | 2 | 24 V AC/DC, 10 VA / 3 W max with Wi-Fi; 8 VA / 2 W max without |
| 10 | What BACnet device profile does the Red5-PLUS-1146 support? | protocol | Red5-PLUS-1146 Catalog Sheet | 1 | BACnet Building Controller (B-BC) |
| 11 | What BACnet device profile does enteliVAULT support? | protocol | enteliVAULT Catalog Sheet | 1 | Advanced Operator Workstation (B-AWS), Secure Connect Hub (B-SCHUB) |
| 12 | What communication ports does the eZNS network sensor have? | protocol | eZNS Catalog Sheet | 2 | RS-485 port, Delta LINKnet (up to 76800 bps), USB service port, NFC |
| 13 | What browsers does enteliWEB support? | compatibility | enteliWEB Catalog Sheet | 1 | Google Chrome 80+, Microsoft Edge 80+, Mozilla Firefox 73+, Apple Safari 13+ |
| 14 | What browsers does enteliCLOUD require, and does it need an internet connection? | compatibility | enteliCLOUD Catalog Sheet | 1 | IE 11+, Firefox 70+, Chrome 78+, Safari 13+ (Mac), Edge 44+; requires an internet connection |
| 15 | Is the eZNTW compatible with other Delta Controls wireless system components? | compatibility | eZNTW Catalog Sheet | 4 | Expands with Delta Controls LINKnet and wireless EnOcean system components |
| 16 | What is the refund policy if I'm not satisfied with my purchase? | out-of-scope | — | — | Not covered by any ingested catalog sheet or product page; must abstain |
| 17 | How do I reset my password on support.deltacontrols.com? | out-of-scope | — | — | That domain is SSO-gated and explicitly never crawled (`data/SOURCES.md`); must abstain |
| 18 | Does Delta Controls' O3 platform integrate with a Honeywell thermostat? | out-of-scope | — | — | Not covered — the corpus documents Delta Controls' own product line only; must abstain |
| 19 | What makes the DAC-633PoE suitable for fan coil applications? | engineer-only | DAC-633PoE Catalog Sheet | 1 | Native BACnet Advanced Application Controller with Power over Ethernet (PoE); support must abstain, engineer must get the citation |
| 20 | What Modbus slave address does the UNOnext start from? | engineer-only | UNOnext MODBUS RTU Protocol | 3 | Starts from 0xD0 (208); support must abstain, engineer must get the citation |

## Category counts

spec: 3 · ordering: 3 · wiring-power: 3 · protocol: 3 · compatibility: 3 · out-of-scope: 3 · engineer-only: 2

## Notes for session C

- Rows 1–15 must return `abstained: false` for both `support` and `engineer` roles, with a citation
  matching the expected document and page.
- Rows 16–18 must return `abstained: true` for every role (nothing in the corpus answers them).
- Rows 19–20 must return `abstained: true` for `support` and `abstained: false` (with a citation) for
  `engineer` and `admin` — the ACL test.
- `DAC-633PoE-Catalog-Sheet.pdf` and `UNOnext-MODBUS-RTU-Protocol.pdf` are the two documents seeded
  with `acl_groups = ["engineer"]` (see `src/bas_assistant/ingest/sources.py::ENGINEER_ONLY_FILENAMES`).

## How `rerank_threshold` was set

**Session D (current, 0.8, `cross-encoder/ms-marco-MiniLM-L-6-v2` over 15 candidates):** measured
on rows 1–18 as support and rows 19–20 as support and engineer, on the same fused candidates as
bge. Answerable questions topped out at 0.87–1.00; the must-abstain cases at 0.00 (row 16),
0.01 (17), 0.72 (18), 0.95 (19 as support) and 0.22 (20 as support). 0.8 sits between 0.72 and
0.87; row 19 as support is the one left to the answer model's `answerable: false`. Full table
and latency numbers in `docs/adr/0003-reranker.md`.

**Session A (0.5, `BAAI/bge-reranker-base` over 30 candidates):**

Session A set 0.5 from the top rerank scores of the live `/search` endpoint. Session C changed what
the reranker reads: each chunk is now scored with its document's title in front of it, and the
lexical search matches the title too (weighted above the chunk's own words). Golden rows 8 and 10
needed that. Their facts sit in short sections ("## Power / 24 VDC (20 W max) ...", "BACnet
Building Controller (B-BC)") that never name the product, and sibling catalog sheets repeat them
word for word. Before the change, row 8's power section was not among the 30 candidates at all
(vector and lexical rank both past 20). Row 10's section tied at 0.662 with four sibling products'
identical sections and ranked 7th. Scores were measured again for every row (session C
diagnostic, `retrieve()` in the app container, Sep 27 2026):

| Row | Role | Top score before | Top score after | Expected document in top 5, before / after |
|---|---|---|---|---|
| 1 | support | 1.000 | 1.000 | yes / yes |
| 2 | support | 0.999 | 1.000 | yes / yes |
| 3 | support | 0.986 | 0.998 | yes / yes |
| 4 | support | 0.921 | 0.929 | yes / yes |
| 5 | support | 0.978 | 0.981 | yes / yes |
| 6 | support | 0.982 | 0.972 | yes / yes |
| 7 | support | 0.936 | 0.991 | yes / yes |
| 8 | support | 0.757 | 0.962 | yes / yes (the power section: no / yes) |
| 9 | support | 0.976 | 0.994 | yes / yes |
| 10 | support | 0.996 | 0.999 | yes / yes (1146's own B-BC section: rank 7 / rank 3) |
| 11 | support | 0.735 | 0.972 | **no** / yes |
| 12 | support | 0.991 | 0.979 | **no** / yes |
| 13 | support | 0.994 | 0.997 | yes / yes |
| 14 | support | 0.833 | 0.998 | yes / yes |
| 15 | support | 1.000 | 1.000 | yes / yes |
| 16 | support (out-of-scope) | 0.000 | 0.000 | — |
| 17 | support (out-of-scope) | 0.068 | 0.052 | — |
| 18 | support (out-of-scope) | 0.228 | 0.211 | — |
| 19 | support (ACL-blocked) | 0.216 | 0.092 | — |
| 19 | engineer | 1.000 | 1.000 | yes / yes |
| 20 | support (ACL-blocked) | 0.388 | 0.529 | — |
| 20 | engineer | 0.554 | 0.995 | yes / yes |

After the change every answerable row scores at least 0.929 and every must-abstain row at most
0.529. The threshold moved from 0.5 to 0.7, near the middle of that gap. Row 20 as support now
scores 0.529 because the public UNOnext datasheet carries the product name. At 0.5 it would have
passed retrieval and relied on the answer model to abstain.

The top-score threshold is still a coarse signal. Session A found a warranty question phrased
around "Red5" that scored 0.95 on product-line vocabulary alone, and dropped it from the set. The
answer model's `answerable` flag and the golden eval are the real check.
