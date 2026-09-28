import { useCallback, useEffect, useState } from "react";
import { useApi } from "../api/context";
import { settle } from "../api/settle";
import type { Ticket } from "../api/types";

type TicketList = {
    tickets: Ticket[] | null;
    loadError: string | null;
    reload: () => void;
    setStatus: (ticketId: string, status: Ticket["status"]) => void;
};

export function useTickets(token: string, onTokenRejected: () => void): TicketList {
    const client = useApi();
    const [tickets, setTickets] = useState<Ticket[] | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);

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

    function setStatus(ticketId: string, status: Ticket["status"]) {
        setTickets(
            (current) => current?.map((t) => (t.id === ticketId ? { ...t, status } : t)) ?? null,
        );
    }

    return { tickets, loadError, reload: () => void load(), setStatus };
}
