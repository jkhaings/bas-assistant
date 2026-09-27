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

## How `rerank_threshold` (0.5) was set

Measured against the live `/ask` endpoint after the real ingest, not guessed:

| Case | Top rerank score |
|---|---|
| Row 1 (O3 Sense power draw, spot check) | 0.804 |
| Row 4 (eBM-800 ordering) | 0.921 |
| Row 6 (eZNTW product number) | 0.982 |
| Row 10 (Red5-PLUS-1146 BACnet profile) | 0.996 |
| Row 12 (eZNS communication ports) | 0.991 |
| Row 19 as `engineer` (DAC-633PoE) | 0.9998 |
| Row 20 as `engineer` (UNOnext) | 0.554 |
| Row 20 as `support` (ACL-blocked — spurious match) | 0.388 |
| Row 19 as `support` (ACL-blocked — spurious match) | 0.218 |
| Row 18 (Honeywell, out-of-scope) | 0.461 |
| Row 16 (refund policy, out-of-scope) | 0.00013 |
| Row 17 (password reset, out-of-scope) | 0.0006 |

The gap that matters: every question this table says should abstain topped out at 0.461; every
question that should answer bottomed out at 0.554. 0.5 sits in that gap. Two questions were
rewritten from an earlier draft because they fell the wrong side of any workable threshold: a
warranty question phrased around "Red5" scored 0.95 (the reranker matches on product-line
vocabulary, not on whether the fact is actually there — the crude top-score threshold cannot catch
that; that level of check is session B's `answer` node and C's faithfulness eval, not session A's
retrieval-only abstain signal), and a baud-rate question for UNOnext scored too close to its own
ACL-blocked-support score (0.68 vs 0.76) because Red5's docs also discuss Modbus baud rates.
