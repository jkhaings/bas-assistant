# ADR 0003: Reranker — MiniLM cross-encoder over 20 candidates, loaded at startup

Status: accepted (Sep 27, session D)

## Context

Session B's live receipts showed `rerank_ms` of 15,096 and 20,562 in the container, with total latency of 24 s and 54 s. The target is a p95 under 8 s (reranking: under 3 s). The configuration then was `BAAI/bge-reranker-base` (XLM-RoBERTa base, 12 layers × 768) scoring the 30 fused candidates. The checks below ran in the order they were asked for.

## Checks

1. **Loaded once, or per request?** Once per process (`functools.cache`), but lazily: the first request after a restart paid for loading the model and for Hugging Face hub checks. The fix: `retrieval.rerank.load_reranker` runs in the app's lifespan, so `/healthz` answers only once the model is in memory. After the fix, the first call after a restart took 1,688 ms of reranking, no more than a warm call.
2. **Emulated on the Mac?** No. The host is arm64 and the Docker server is `linux/arm64`. Every image in compose is `linux/arm64`, including the app, LiteLLM, Postgres, Redis, Prometheus, Grafana and the Langfuse stack. Inside the app container `uname -m` is `aarch64`, and torch 2.14.0+cpu uses 8 threads on 8 CPUs.
3. **30 → 15 candidates** (`retrieval.pipeline.FUSED_TOP_N`). Quality did not change (below): every hit bge made from 30 candidates was already in the fused top 15. Latency roughly halves, but that is still far over 3 s:

   | Timing | bge@30 | bge@15 |
   |---|---|---|
   | A/B, same process and same minutes | median 58.8 s (22 queries) | median 29.3 s (4 queries) |
   | Uncontended | 15–21 s (session B) | about 7–10 s (inferred, not measured) |

   The A/B ran while session C's stack was running its own reranker on the same 8 CPUs, which inflated the absolute numbers. The bge@15 uncontended figure is inferred from the halving; I did not measure it.
4. **MiniLM** (`cross-encoder/ms-marco-MiniLM-L-6-v2`, 6 layers × 384). In the same A/B its median was 5.8 s against bge@30's 58.8 s. Through the real endpoint (`POST /search`, 20 golden questions × support and engineer, 40 calls), with session C's app idle in 11 of 12 CPU samples:

   | | rerank_ms |
   |---|---|
   | p50 | 979 |
   | p95 | 2,177 |
   | max | 6,932 (the one sample with session C's app at 620% CPU) |

## Quality on the golden set

The A/B scored identical fused candidates (the pipeline's own `_fused_candidates`) with each model. It covered 22 queries: rows 1–18 of `data/top20_questions.md` as support, and rows 19–20 as support and as engineer. A hit means the expected document is among the top 5 parents.

| Config | Expected document in top 5 (17) | Correct abstain (5) |
|---|---|---|
| bge-reranker-base @30, threshold 0.5 (before) | 15 | 5 |
| bge-reranker-base @15, threshold 0.5 | 15 | 5 |
| MiniLM @15, threshold 0.5 | 16 | 3 |
| **MiniLM @15, threshold 0.8 (shipped)** | **16** | **4** |

- **Row 11** (enteliVAULT BACnet profile) misses with every model.
- **Row 12** (eZNS ports): MiniLM finds it, bge does not.
- **Scores:**

  | Model | Answerable top scores | Must-abstain top scores (rows 16, 17, 18, 19 as support, 20 as support) |
  |---|---|---|
  | bge | 0.55–1.00 | 0.00, 0.04, 0.23, 0.22, 0.39 |
  | MiniLM | 0.87–1.00 | 0.00, 0.01, 0.72, 0.95, 0.22 |

  MiniLM's scores are more saturated. `rerank_threshold` moves from 0.5 to 0.8, between the highest out-of-scope score (0.72) and the lowest answerable one (0.87).
- **The abstain lost**: row 19 as support ("What makes the DAC-633PoE suitable for fan coil applications?"). The DAC-633PoE sheet is engineer-only and stays invisible to support, because the ACL is enforced in SQL, not by the reranker. MiniLM gives an eZFC product-page passage about fan coils 0.95, so that question now reaches the answer model instead of abstaining for free. There the model must return `answerable: false`, which the validator turns into the fixed abstain message. The cost is one answer call, not a leak.
- **Through `/search` with MiniLM @15, threshold 0.8**: 37 of 40 golden checks pass (row 11 for both roles, and row 19 as support).

## Decision

Ship MiniLM over 15 candidates, loaded at startup, with `rerank_threshold` 0.8.

Scores go through an explicit sigmoid (`activation_fn`), so the threshold stays in 0–1 for either model; bge already used sigmoid by default, and MiniLM ships raw logits. `CORPUS_VERSION` moves to "2", so answers cached under the old reranker are not served.

## Consequences

- p95 reranking goes from 15–21 s to about 2 s. The quality trade is one retrieval-level abstain for one extra hit, on 20 rows.
- The threshold was tuned on 20 rows. Session C's golden eval and RAGAS run should confirm it or move it.
- The model is about 90 MB in the `model_cache` volume. A fresh volume downloads it at first start, so the app's healthcheck `start_period` is 120 s.
- If quality needs bge back: a GPU host, or sentence-transformers' ONNX backend (a new dependency). Lowering `max_length` below 512 is the other lever not tried.

## Post-merge with session C (Sep 27): titles in the reranker input, threshold 0.96

Session C, still on bge-reranker-base, made the reranker read each chunk with its document title and moved the threshold to 0.7. The merged code keeps MiniLM, now with titles. The threshold was set again from the golden set through the app's own `retrieve()` (15 candidates, threshold 0, inside the container):

- **Hits**: the expected document is in the top 5 for all 17 answerable checks (without titles: 16 of 17).
- **Answerable checks**: top scores 0.988–1.000.
- **Must-abstain checks**: row 16 at 0.000, row 17 at 0.138, row 20 as support at 0.168, row 18 at 0.505, and row 19 as support at 0.944.

`rerank_threshold` is 0.96, so every must-abstain check abstains at retrieval, before any answer call. That includes row 19 as support, which reached the answer model under the 0.8 setting. The margins are narrow (0.016 below, 0.028 above) and were fitted on 22 checks, so the threshold must be re-checked whenever the corpus, the reranker or its input changes. The per-row table is in `data/top20_questions.md`.

### Candidates back up to 20 (post-merge)

The golden eval at 15 candidates passed 21 of 22 checks. The miss was row 13 ("What browsers does enteliWEB support?"). Its answer, enteliWEB's `## Client Browser` section, scores 1.000 with MiniLM, the best of any candidate, but fuses at rank 18, so 15 cut it before reranking. The 30 → 15 check in the A/B above missed this, because it counted the right document in the top 5, not the right section.

Both settings were timed on the same fused pools, interleaved in one process, over the 22 golden checks, with titles making every pair longer:

| Candidates | Rerank p50 | Rerank p95 | Golden (`make eval`) |
|---|---|---|---|
| 15 | 1,336 ms | 2,637 ms | 21 / 22 (row 13 abstains) |
| 20 | 2,045 ms | 3,419 ms | 22 / 22 |

Jason chose 20. The rerank p95 is about 0.4 s over the 3 s rerank budget, and inside the 8 s end-to-end target. Threshold 0.96 holds at 20: the scan was repeated with the same split (answerable 0.988–1.000, must-abstain up to 0.944).
