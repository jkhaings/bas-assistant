import { useState } from "react";
import { useApi } from "../api/context";
import { settle } from "../api/settle";
import type { Ticket } from "../api/types";

export type TicketDecisions = {
    busyId: string | null;
    cardErrors: Record<string, string>;
    lastDecision: string | null;
    decide: (ticket: Ticket, approve: boolean) => void;
};

export function useTicketDecisions(
    token: string,
    onTokenRejected: () => void,
    onDecided: (ticketId: string, status: Ticket["status"]) => void,
): TicketDecisions {
    const client = useApi();
    const [busyId, setBusyId] = useState<string | null>(null);
    const [cardErrors, setCardErrors] = useState<Record<string, string>>({});
    const [lastDecision, setLastDecision] = useState<string | null>(null);

    async function decide(ticket: Ticket, approve: boolean) {
        setBusyId(ticket.id);
        const result = await settle(
            client.POST("/approve", {
                params: { header: { "x-admin-token": token } },
                body: { thread_id: ticket.thread_id, approve },
            }),
        );
        setBusyId(null);
        if (!result.ok) {
            if (result.status === 401) onTokenRejected();
            else setCardErrors((errors) => ({ ...errors, [ticket.id]: result.message }));
            return;
        }
        const { status } = result.data;
        onDecided(ticket.id, status);
        setLastDecision(`"${ticket.draft.title}" was ${status}. It moved to history.`);
    }

    return {
        busyId,
        cardErrors,
        lastDecision,
        decide: (ticket, approve) => void decide(ticket, approve),
    };
}
