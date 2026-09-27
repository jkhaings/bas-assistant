# ADR 0003: Reranker — MiniLM cross-encoder over 15 candidates, loaded at startup

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
