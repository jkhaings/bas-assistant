import type { ReactNode } from "react";
import type { Role } from "../../api/types";
import goldenJsonl from "../../../../eval/golden.jsonl?raw";

type GoldenCase = {
    id: number;
    category: string;
    question: string;
    expected_source: string | null;
    expected_page: number | null;
    expect: Partial<Record<Role, "answer" | "abstain">>;
};

// The build reads eval/golden.jsonl itself, so the table always shows the cases the eval runs.
const CASES: GoldenCase[] = goldenJsonl
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as GoldenCase);

const CHECKS = CASES.reduce((sum, golden) => sum + Object.keys(golden.expect).length, 0);
const TWO_ROLE = CASES.filter((golden) => Object.keys(golden.expect).length > 1).length;

function expected({ expect }: GoldenCase): string {
    const outcomes = Object.entries(expect);
    if (outcomes.length === 1) return outcomes[0]?.[1] ?? "";
    return outcomes.map(([role, outcome]) => `${outcome} as ${role}`).join(", ");
}

function source({ expected_source, expected_page }: GoldenCase): string {
    if (!expected_source) return "none";
    return expected_page ? `${expected_source}, page ${expected_page}` : expected_source;
}

// On a phone each row stacks into a small card, and each cell shows its column name.
function Cell({ label, children }: { label: string; children: ReactNode }) {
    return (
        <td
            data-label={label}
            className="flex gap-3 py-0.5 before:w-24 before:shrink-0 before:font-medium before:text-stone-500 before:content-[attr(data-label)] sm:table-cell sm:px-2 sm:py-2 sm:align-top sm:before:content-none"
        >
            <span className="min-w-0 break-words">{children}</span>
        </td>
    );
}

const COLUMNS = ["#", "Category", "Question", "Expected", "Source document", "Role"];

export function GoldenTable() {
    return (
        <table className="block w-full text-left text-sm sm:table">
            <caption className="mb-2 block text-left text-stone-600 sm:table-caption">
                All {CASES.length} golden cases, from eval/golden.jsonl. Each run makes {CHECKS}{" "}
                checks, because {TWO_ROLE} of them are asked as two roles.
            </caption>
            <thead className="sr-only sm:not-sr-only">
                <tr className="border-b border-stone-300">
                    {COLUMNS.map((column) => (
                        <th key={column} scope="col" className="px-2 py-2 font-medium">
                            {column}
                        </th>
                    ))}
                </tr>
            </thead>
            <tbody className="block sm:table-row-group">
                {CASES.map((golden) => (
                    <tr
                        key={golden.id}
                        className="block border-b border-stone-200 py-3 sm:table-row sm:py-0"
                    >
                        <Cell label="#">{golden.id}</Cell>
                        <Cell label="Category">{golden.category}</Cell>
                        <Cell label="Question">{golden.question}</Cell>
                        <Cell label="Expected">{expected(golden)}</Cell>
                        <Cell label="Source document">{source(golden)}</Cell>
                        <Cell label="Role">{Object.keys(golden.expect).join(", ")}</Cell>
                    </tr>
                ))}
            </tbody>
        </table>
    );
}
