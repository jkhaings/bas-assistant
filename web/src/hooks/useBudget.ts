import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "../api/client";
import type { Budget } from "../api/types";

const POLL_MS = 30_000;

export function useBudget(client: ApiClient): { budget: Budget | null; refresh: () => void } {
    const [budget, setBudget] = useState<Budget | null>(null);

    const refresh = useCallback(() => {
        client
            .GET("/budget")
            .then(({ data }) => {
                if (data) setBudget(data);
            })
            // A missed poll keeps the last known figure; the next poll tries again.
            .catch(() => undefined);
    }, [client]);

    useEffect(() => {
        refresh();
        const timer = window.setInterval(refresh, POLL_MS);
        return () => window.clearInterval(timer);
    }, [refresh]);

    return { budget, refresh };
}
