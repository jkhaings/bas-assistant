import type { Budget } from "../api/types";

const CHIP = "rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap";

function dollars(value: number): string {
    return `$${value.toFixed(2)}`;
}

export function BudgetChip({ budget }: { budget: Budget | null }) {
    if (!budget) return null;
    const exhausted = budget.spent_usd >= budget.cap_usd;
    const tone = exhausted
        ? "border-red-300 bg-red-50 text-red-800"
        : "border-stone-300 bg-stone-50 text-stone-700";
    return (
        <span
            className={`${CHIP} ${tone}`}
            title="Model spend today (UTC) against the demo's daily cap"
        >
            Today {dollars(budget.spent_usd)} of {dollars(budget.cap_usd)}
        </span>
    );
}

export function DocumentsChip({ count }: { count: number | null }) {
    if (count === null) return null;
    return (
        <span
            className={`${CHIP} border-accent-line bg-accent-soft text-accent-strong`}
            title="Documents the current role is allowed to retrieve from"
        >
            {count} {count === 1 ? "document" : "documents"} visible
        </span>
    );
}
