import type { Ticket } from "../../api/types";
import { useTickets } from "../../hooks/useTickets";
import { TicketCard } from "./TicketCard";

type Props = { token: string; onTokenRejected: () => void };

export function TicketBoard({ token, onTokenRejected }: Props) {
    const { tickets, loadError, busyId, cardErrors, lastDecision, reload, decide } = useTickets(
        token,
        onTokenRejected,
    );

    function ticketSection(id: string, title: string, list: Ticket[], empty: string) {
        return (
            <section aria-labelledby={id} className="space-y-3">
                <h2 id={id} className="text-base font-semibold">
                    {title}
                </h2>
                {list.length === 0 && <p className="text-sm text-stone-500">{empty}</p>}
                {list.map((ticket) => (
                    <TicketCard
                        key={ticket.id}
                        ticket={ticket}
                        busy={busyId === ticket.id}
                        error={cardErrors[ticket.id] ?? null}
                        onDecide={(approve) => decide(ticket, approve)}
                    />
                ))}
            </section>
        );
    }

    const waiting = tickets?.filter((ticket) => ticket.status === "proposed") ?? [];
    const history = tickets?.filter((ticket) => ticket.status !== "proposed") ?? [];

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3">
                <button
                    type="button"
                    onClick={reload}
                    className="rounded-md border border-stone-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-stone-100"
                >
                    Refresh
                </button>
                <p aria-live="polite" className="text-sm text-emerald-800">
                    {lastDecision}
                </p>
            </div>
            {loadError && (
                <p role="alert" className="text-sm text-red-700">
                    {loadError}
                </p>
            )}
            {tickets === null && !loadError && (
                <p className="text-sm text-stone-500">Loading tickets</p>
            )}
            {tickets && (
                <>
                    {ticketSection(
                        "waiting",
                        `Waiting for approval (${waiting.length})`,
                        waiting,
                        "No tickets are waiting.",
                    )}
                    {ticketSection("history", "History", history, "No decisions yet.")}
                </>
            )}
        </div>
    );
}
