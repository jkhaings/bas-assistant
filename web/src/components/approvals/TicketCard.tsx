import type { Ticket } from "../../api/types";

const STATUS_TONES: Record<Ticket["status"], string> = {
    proposed: "border-sky-200 bg-sky-50 text-sky-800",
    approved: "border-emerald-200 bg-emerald-50 text-emerald-800",
    filed: "border-emerald-200 bg-emerald-50 text-emerald-800",
    rejected: "border-stone-300 bg-stone-100 text-stone-700",
};

type DecisionProps = { busy: boolean; onDecide: (approve: boolean) => void };

function DecisionButtons({ busy, onDecide }: DecisionProps) {
    return (
        <div className="flex gap-2">
            <button
                type="button"
                disabled={busy}
                onClick={() => onDecide(true)}
                className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-50"
            >
                Approve
            </button>
            <button
                type="button"
                disabled={busy}
                onClick={() => onDecide(false)}
                className="rounded-md border border-stone-300 bg-white px-4 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-100 disabled:opacity-50"
            >
                Deny
            </button>
        </div>
    );
}

type Props = {
    ticket: Ticket;
    busy: boolean;
    error: string | null;
    onDecide: (approve: boolean) => void;
};

export function TicketCard({ ticket, busy, error, onDecide }: Props) {
    const created = new Date(ticket.created_at).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    });
    return (
        <article className="space-y-3 rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 className="font-semibold text-stone-900">{ticket.draft.title}</h3>
                <span
                    className={`rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_TONES[ticket.status]}`}
                >
                    {ticket.status}
                </span>
            </div>
            <p className="text-xs text-stone-500">
                Proposed {created} · thread{" "}
                <code className="font-mono">{ticket.thread_id.slice(0, 8)}</code>
            </p>
            <p className="text-sm whitespace-pre-wrap text-stone-700">{ticket.draft.body}</p>
            {ticket.status === "proposed" && <DecisionButtons busy={busy} onDecide={onDecide} />}
            {error && (
                <p role="alert" className="text-sm text-red-700">
                    {error}
                </p>
            )}
        </article>
    );
}
