import { useState } from "react";
import { useApi } from "../../api/context";
import { settle } from "../../api/settle";

const LINK_BUTTON = "text-xs font-medium text-stone-600 underline-offset-2 hover:underline";

type Flag = {
    reason: string;
    setReason: (reason: string) => void;
    flagged: boolean;
    sending: boolean;
    error: string | null;
    submit: () => void;
};

// Held above the form, so a cancelled form reopens with the reason and error it had.
function useFlag(requestId: string): Flag {
    const client = useApi();
    const [reason, setReason] = useState("");
    const [flagged, setFlagged] = useState(false);
    const [sending, setSending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function submit() {
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

    return { reason, setReason, flagged, sending, error, submit: () => void submit() };
}

type FormProps = { inputId: string; flag: Flag; onCancel: () => void };

function FlagForm({ inputId, flag, onCancel }: FormProps) {
    return (
        <form
            onSubmit={(event) => {
                event.preventDefault();
                flag.submit();
            }}
            className="space-y-2"
        >
            <label htmlFor={inputId} className="block text-xs font-medium text-stone-700">
                What is wrong with this answer?
            </label>
            <div className="flex flex-wrap gap-2">
                <input
                    id={inputId}
                    value={flag.reason}
                    onChange={(event) => flag.setReason(event.target.value)}
                    maxLength={1000}
                    className="min-w-0 flex-1 rounded-md border border-stone-300 px-2 py-1 text-sm"
                />
                <button
                    type="submit"
                    disabled={flag.sending || !flag.reason.trim()}
                    className="rounded-md bg-rose-700 px-3 py-1 text-xs font-medium text-white hover:bg-rose-800 disabled:opacity-50"
                >
                    Submit flag
                </button>
                <button type="button" onClick={onCancel} className={LINK_BUTTON}>
                    Cancel
                </button>
            </div>
            {flag.error && <p className="text-xs text-red-700">{flag.error}</p>}
        </form>
    );
}

export function FlagControl({ requestId }: { requestId: string }) {
    const [open, setOpen] = useState(false);
    const flag = useFlag(requestId);

    if (flag.flagged) return <p className="text-xs font-medium text-rose-700">Flagged</p>;
    if (!open) {
        return (
            <button type="button" onClick={() => setOpen(true)} className={LINK_BUTTON}>
                Flag as wrong
            </button>
        );
    }
    return <FlagForm inputId={`flag-${requestId}`} flag={flag} onCancel={() => setOpen(false)} />;
}
