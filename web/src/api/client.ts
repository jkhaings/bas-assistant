import createClient, { type Client } from "openapi-fetch";
import { limitDetailOf } from "./errors";
import type { paths } from "./schema";
import type { Role } from "./types";

export type ApiClient = Client<paths>;

type ClientOptions = {
    role: Role;
    onBudgetReached: (resetsAt: string | null) => void;
};

export function createApiClient({ role, onBudgetReached }: ClientOptions): ApiClient {
    const client = createClient<paths>({
        // An absolute base keeps Request construction valid outside a browser page (tests).
        baseUrl: window.location.origin,
        headers: { "X-Demo-Role": role },
        // Looked up per call rather than captured once, so a stubbed fetch is honoured.
        fetch: (request) => globalThis.fetch(request),
    });
    client.use({
        async onResponse({ response }) {
            if (response.status !== 503) return undefined;
            const body: unknown = await response
                .clone()
                .json()
                .catch(() => null);
            const limit = limitDetailOf(body);
            if (limit?.reason === "daily_budget_reached") onBudgetReached(limit.resets_at);
            return undefined;
        },
    });
    return client;
}
