import { useEffect, useState } from "react";
import type { ApiClient } from "../api/client";

// The client carries the role, so a new client (role switch) refetches the count.
export function useDocumentCount(client: ApiClient): number | null {
    const [count, setCount] = useState<number | null>(null);

    useEffect(() => {
        let current = true;
        setCount(null);
        client
            .GET("/documents")
            .then(({ data }) => {
                if (current && data) setCount(data.length);
            })
            // Without a count the chip stays hidden; nothing else depends on it.
            .catch(() => undefined);
        return () => {
            current = false;
        };
    }, [client]);

    return count;
}
