import { useState } from "react";
import { useApi } from "../../api/context";
import { settle } from "../../api/settle";
import type { FeedbackValue } from "../../api/types";

const OPTIONS: { value: FeedbackValue; label: string }[] = [
    { value: "used_as_is", label: "Used as-is" },
    { value: "used_with_edits", label: "Used with edits" },
    { value: "not_used", label: "Not used" },
];

export function FeedbackControl({ requestId }: { requestId: string }) {
    const client = useApi();
    const [selected, setSelected] = useState<FeedbackValue | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function vote(value: FeedbackValue) {
        setError(null);
        const result = await settle(
            client.POST("/requests/{request_id}/feedback", {
                params: { path: { request_id: requestId } },
                body: { value },
            }),
        );
        if (result.ok) setSelected(value);
        else setError(result.message);
    }

    return (
        <div>
            <div
                role="group"
                aria-label="Did you use this answer?"
                className="flex flex-wrap items-center gap-2"
            >
                <span className="text-xs text-stone-500">Did you use this answer?</span>
                {OPTIONS.map(({ value, label }) => {
                    const pressed = selected === value;
                    const tone = pressed
                        ? "border-accent bg-accent text-white"
                        : "border-stone-300 bg-white text-stone-700 hover:bg-stone-100";
                    return (
                        <button
                            key={value}
                            type="button"
                            aria-pressed={pressed}
                            onClick={() => void vote(value)}
                            className={`rounded-full border px-3 py-1 text-xs font-medium ${tone}`}
                        >
                            {label}
                        </button>
                    );
                })}
            </div>
            {error && <p className="mt-1 text-xs text-red-700">{error}</p>}
        </div>
    );
}
