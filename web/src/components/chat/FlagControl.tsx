import { useState, type FormEvent } from "react";
import { useApi } from "../../api/context";
import { settle } from "../../api/settle";

const LINK_BUTTON = "text-xs font-medium text-stone-600 underline-offset-2 hover:underline";

export function FlagControl({ requestId }: { requestId: string }) {
    const client = useApi();
    const [open, setOpen] = useState(false);
    const [reason, setReason] = useState("");
    const [flagged, setFlagged] = useState(false);
    const [sending, setSending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const inputId = `flag-${requestId}`;

    async function submit(event: FormEvent) {
        event.preventDefault();
        setSending(true);
        setError(null);
        const result = await settle(
            client.POST("/requests/{request_id}/flag", {
                params: { path: { request_id: requestId } },
                body: { reason: reason.trim() },
            }),
        );
        setSending(false);
        if (result.ok) setFlagged(true);
        else setError(result.message);
    }

    if (flagged) return <p className="text-xs font-medium text-rose-700">Flagged</p>;
    if (!open) {
        return (
            <button type="button" onClick={() => setOpen(true)} className={LINK_BUTTON}>
                Flag as wrong
            </button>
        );
    }
    return (
        <form onSubmit={(event) => void submit(event)} className="space-y-2">
            <label htmlFor={inputId} className="block text-xs font-medium text-stone-700">
                What is wrong with this answer?
            </label>
            <div className="flex flex-wrap gap-2">
                <input
                    id={inputId}
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    maxLength={1000}
                    className="min-w-0 flex-1 rounded-md border border-stone-300 px-2 py-1 text-sm"
                />
                <button
                    type="submit"
                    disabled={sending || !reason.trim()}
                    className="rounded-md bg-rose-700 px-3 py-1 text-xs font-medium text-white hover:bg-rose-800 disabled:opacity-50"
                >
                    Submit flag
                </button>
                <button type="button" onClick={() => setOpen(false)} className={LINK_BUTTON}>
                    Cancel
                </button>
            </div>
            {error && <p className="text-xs text-red-700">{error}</p>}
        </form>
    );
}
