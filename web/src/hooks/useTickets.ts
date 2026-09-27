import { useCallback, useEffect, useState } from "react";
import { useApi } from "../api/context";
import { settle } from "../api/settle";
import type { Ticket } from "../api/types";

type TicketsState = {
    tickets: Ticket[] | null;
    loadError: string | null;
    busyId: string | null;
    cardErrors: Record<string, string>;
    lastDecision: string | null;
    reload: () => void;
    decide: (ticket: Ticket, approve: boolean) => void;
};

export function useTickets(token: string, onTokenRejected: () => void): TicketsState {
    const client = useApi();
    const [tickets, setTickets] = useState<Ticket[] | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [busyId, setBusyId] = useState<string | null>(null);
    const [cardErrors, setCardErrors] = useState<Record<string, string>>({});
    const [lastDecision, setLastDecision] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoadError(null);
        const result = await settle(
            client.GET("/tickets", { params: { header: { "x-admin-token": token } } }),
        );
        if (result.ok) setTickets(result.data);
        else if (result.status === 401) onTokenRejected();
        else setLoadError(result.message);
    }, [client, token, onTokenRejected]);

    useEffect(() => {
        void load();
    }, [load]);

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
        setTickets(
            (current) => current?.map((t) => (t.id === ticket.id ? { ...t, status } : t)) ?? null,
        );
        setLastDecision(`"${ticket.draft.title}" was ${status}. It moved to history.`);
    }

    return {
        tickets,
        loadError,
        busyId,
        cardErrors,
        lastDecision,
        reload: () => void load(),
        decide: (ticket, approve) => void decide(ticket, approve),
    };
}
