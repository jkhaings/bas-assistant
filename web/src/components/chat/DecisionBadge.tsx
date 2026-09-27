import type { Decision } from "../../api/types";

const TONES: Record<Decision, string> = {
    answered: "border-emerald-200 bg-emerald-50 text-emerald-800",
    abstained: "border-amber-200 bg-amber-50 text-amber-800",
    refused: "border-rose-200 bg-rose-50 text-rose-800",
    paused: "border-sky-200 bg-sky-50 text-sky-800",
    failed: "border-red-300 bg-red-50 text-red-800",
};

export function DecisionBadge({ decision }: { decision: Decision }) {
    return (
        <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${TONES[decision]}`}>
            {decision}
        </span>
    );
}
