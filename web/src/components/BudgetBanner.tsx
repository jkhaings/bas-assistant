function resetTime(resetsAt: string): string {
    return new Date(resetsAt).toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short",
    });
}

export function BudgetBanner({ resetsAt }: { resetsAt: string | null }) {
    return (
        <div
            role="alert"
            className="bg-red-700 px-4 py-2 text-center text-sm font-medium text-white"
        >
            The demo's daily budget is used up.
            {resetsAt && ` It resets at ${resetTime(resetsAt)}.`}
        </div>
    );
}
