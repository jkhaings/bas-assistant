import { isRecord } from "./errors";

export type CategoryScores = {
    n: number;
    faithfulness: number | null;
    answer_relevancy: number | null;
    context_precision: number | null;
    context_recall: number | null;
};

export type GoldenScores = {
    run_at: string;
    corpus_version: string;
    golden: { passed: number; total: number; rate: number };
    failures: Record<string, string>;
    overall: CategoryScores;
    by_category: Record<string, CategoryScores>;
};

export type RedteamScores = {
    run_at: string;
    passed: number;
    total: number;
    cases: Record<string, string>;
};

// `scores` is an open object in the API schema, so check the fields the page relies on and
// trust the eval runner for the rest.
export function asGoldenScores(scores: unknown): GoldenScores | null {
    if (!isRecord(scores) || !isRecord(scores.golden) || !isRecord(scores.overall)) return null;
    if (!isRecord(scores.by_category) || !isRecord(scores.failures)) return null;
    if (typeof scores.golden.passed !== "number" || typeof scores.golden.total !== "number") {
        return null;
    }
    return scores as GoldenScores;
}

export function asRedteamScores(scores: unknown): RedteamScores | null {
    if (!isRecord(scores) || !isRecord(scores.cases)) return null;
    if (typeof scores.passed !== "number" || typeof scores.total !== "number") return null;
    return scores as RedteamScores;
}
