import type { Ticket } from "../../api/types";
import { useTicketDecisions, type TicketDecisions } from "../../hooks/useTicketDecisions";
import { useTickets } from "../../hooks/useTickets";
import { TicketCard } from "./TicketCard";

type SectionProps = {
    id: string;
    title: string;
    tickets: Ticket[];
    empty: string;
    decisions: TicketDecisions;
};

function TicketSection({ id, title, tickets, empty, decisions }: SectionProps) {
    return (
        <section aria-labelledby={id} className="space-y-3">
            <h2 id={id} className="text-base font-semibold">
                {title}
            </h2>
            {tickets.length === 0 && <p className="text-sm text-stone-500">{empty}</p>}
            {tickets.map((ticket) => (
                <TicketCard
                    key={ticket.id}
                    ticket={ticket}
                    busy={decisions.busyId === ticket.id}
                    error={decisions.cardErrors[ticket.id] ?? null}
                    onDecide={(approve) => decisions.decide(ticket, approve)}
                />
            ))}
        </section>
    );
}

type WaitingAndHistoryProps = { tickets: Ticket[]; decisions: TicketDecisions };

function WaitingAndHistory({ tickets, decisions }: WaitingAndHistoryProps) {
    const waiting = tickets.filter((ticket) => ticket.status === "proposed");
    const history = tickets.filter((ticket) => ticket.status !== "proposed");
    return (
        <>
            <TicketSection
                id="waiting"
                title={`Waiting for approval (${waiting.length})`}
                tickets={waiting}
                empty="No tickets are waiting."
                decisions={decisions}
            />
            <TicketSection
                id="history"
                title="History"
                tickets={history}
                empty="No decisions yet."
                decisions={decisions}
            />
        </>
    );
}

type Props = { token: string; onTokenRejected: () => void };

export function TicketBoard({ token, onTokenRejected }: Props) {
    const { tickets, loadError, reload, setStatus } = useTickets(token, onTokenRejected);
    const decisions = useTicketDecisions(token, onTokenRejected, setStatus);

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
                    {decisions.lastDecision}
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
            {tickets && <WaitingAndHistory tickets={tickets} decisions={decisions} />}
        </div>
    );
}
