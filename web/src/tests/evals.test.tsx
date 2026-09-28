import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { App } from "../App";
import type { EvalRun } from "../api/types";
import { json, stubApi } from "./fakeApi";
import { shellRoutes } from "./fixtures";

const RUN_AT = "2026-09-27T20:00:00+00:00";
const CATEGORY = {
    n: 3,
    faithfulness: 0.9,
    answer_relevancy: 0.85,
    context_precision: 0.8,
    context_recall: 0.75,
};

const GOLDEN_SCORES = {
    run_at: RUN_AT,
    corpus_version: "corpus-7",
    golden: { passed: 21, total: 22, rate: 21 / 22 },
    failures: { "q07-protocol": "expected document not cited" },
    overall: { ...CATEGORY, n: 16, faithfulness: 0.76 },
    by_category: { spec: CATEGORY, protocol: { ...CATEGORY, n: 2, faithfulness: 0.111 } },
};

const REDTEAM_SCORES = {
    run_at: RUN_AT,
    passed: 1,
    total: 2,
    cases: {
        test_direct_injection_is_refused: "passed",
        test_tracking_image_is_stripped: "failed",
    },
};

function evalRun(kind: EvalRun["kind"], scores: Record<string, unknown>): EvalRun {
    return {
        id: "3c1f7a2e-8b4d-4e6f-9a0b-1c2d3e4f5a6b",
        kind,
        corpus_version: "corpus-7",
        prompt_version: "answer-v3",
        scores,
        cost_usd: "0.0600",
        created_at: RUN_AT,
    };
}

function openEvals(golden: EvalRun | null, redteam: EvalRun | null) {
    stubApi([
        ...shellRoutes(),
        { method: "GET", path: "/evals/latest", respond: () => json({ golden, redteam }) },
    ]);
    window.location.hash = "#/evals";
    render(<App />);
}

function redteamCase(sentence: string) {
    const row = screen.getByText(sentence).closest("li");
    if (!row) throw new Error(`no red-team row reads "${sentence}"`);
    return within(row);
}

test("a golden run shows the pass rate and the RAGAS scores, with low scores marked", async () => {
    openEvals(evalRun("golden", GOLDEN_SCORES), null);

    expect(await screen.findByText("21/22 (95%)")).toBeInTheDocument();
    const table = within(screen.getByRole("table", { name: "RAGAS scores by question category" }));
    const protocol = within(table.getByRole("row", { name: /^protocol/ }));
    expect(protocol.getByTitle("Below 0.5")).toHaveTextContent("0.111 (low)");
    expect(table.getAllByTitle("Below 0.5")).toHaveLength(1);
    expect(table.getByRole("row", { name: /^overall/ })).toHaveTextContent("0.760");
});

test("golden failures are listed with their reason", async () => {
    openEvals(evalRun("golden", GOLDEN_SCORES), null);

    const question = await screen.findByText("q07-protocol");
    expect(question.closest("li")).toHaveTextContent("q07-protocol: expected document not cited");
});

test("scores in a shape the page does not know show a fallback instead of numbers", async () => {
    openEvals(evalRun("golden", { accuracy: 0.9 }), null);

    expect(
        await screen.findByText("This run's scores are in a shape this page does not read."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

test("red-team cases read as sentences with their result", async () => {
    openEvals(null, evalRun("redteam", REDTEAM_SCORES));

    expect(await screen.findByText("1/2 passed")).toBeInTheDocument();
    expect(redteamCase("Direct injection is refused").getByText("passed")).toBeInTheDocument();
    expect(redteamCase("Tracking image is stripped").getByText("failed")).toBeInTheDocument();
});
