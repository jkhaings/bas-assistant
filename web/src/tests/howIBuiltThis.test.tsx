import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import goldenJsonl from "../../../eval/golden.jsonl?raw";
import { HowIBuiltThis } from "../pages/HowIBuiltThis";

function headings(level: number): (string | null)[] {
    return screen.getAllByRole("heading", { level }).map((heading) => heading.textContent);
}

test("How I built this has the three steps, then Known problems", () => {
    render(<HowIBuiltThis />);

    expect(headings(2)).toEqual([
        "Step 1: Before anyone asks a question",
        "Step 2: A question arrives",
        "Step 3: Around all of it",
        "Known problems",
    ]);
    const problems = screen.getByRole("region", { name: "Known problems" });
    expect(problems.querySelectorAll("li")).toHaveLength(4);
});

test("the nine sections follow the pipeline, each ending with its tools", () => {
    render(<HowIBuiltThis />);

    expect(headings(3)).toEqual([
        "RAG: the documents",
        "Embeddings",
        "Guardrails",
        "Routing",
        "Search",
        "Orchestration",
        "Cost tracking",
        "Security",
        "Evaluations",
    ]);
    for (const heading of screen.getAllByRole("heading", { level: 3 })) {
        const last = heading.closest("section")?.lastElementChild;
        expect(last?.textContent).toMatch(/^Tools: /);
    }
});

test("the page is written in the first person, never as we", () => {
    render(<HowIBuiltThis />);

    const text = screen.getByRole("article").textContent ?? "";
    expect(text).toMatch(/\bI\b/);
    expect(text).not.toMatch(/\b(we|our|us)\b/i);
});

test("the golden table has one row per case in eval/golden.jsonl", () => {
    const fileRows = goldenJsonl.split("\n").filter((line) => line.trim()).length;
    render(<HowIBuiltThis />);

    const table = screen.getByRole("table", { name: /golden cases/ });
    expect(fileRows).toBeGreaterThan(0);
    expect(table.querySelectorAll("tbody tr")).toHaveLength(fileRows);
});
