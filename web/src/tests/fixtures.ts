import type { AskResponse, Receipt, Ticket } from "../api/types";
import { json, type Route } from "./fakeApi";

export const REQUEST_ID = "0b6f1c1e-3f5a-4c8e-9a51-2f1d8e7c6b10";
export const THREAD_ID = "5d2a7e44-1b9c-4f0e-8d3a-6c7b2e1f9a02";

export const ANSWER: AskResponse = {
    answer: "The eZNT-T331 has 3 inputs and 3 outputs.",
    citations: [
        {
            chunk_id: "chunk-1",
            document_title: "eZNT-T331 Catalog Sheet",
            page: 2,
            source_url: "https://example.com/docs/eznt-t331.pdf",
            snippet: "Inputs: 3 universal inputs. Outputs: 3 binary outputs.",
        },
    ],
    decision: "answered",
    route: "fast",
    model: "gpt-4o-mini",
    request_id: REQUEST_ID,
    thread_id: THREAD_ID,
    approval_required: false,
    ticket_id: null,
    notes: [],
    cache_hit: false,
};

export const RECEIPT: Receipt = {
    request_id: REQUEST_ID,
    route: "fast",
    model: "gpt-4o-mini",
    input_tokens: 1830,
    output_tokens: 64,
    cached_tokens: 0,
    usd: 0.000313,
    retrieval_ms: 212,
    rerank_ms: 95,
    model_ms: 1400,
    total_ms: 1810,
    cache_hit: false,
    calls: [
        {
            stage: "answer",
            alias: "fast",
            model: "gpt-4o-mini",
            provider: "openai",
            input_tokens: 1830,
            output_tokens: 64,
            cached_tokens: 0,
            usd: 0.000313,
            latency_ms: 1400,
            cache_hit: false,
        },
    ],
};

export const PROPOSED_TICKET: Ticket = {
    id: "9e8d7c6b-5a4f-4e3d-8c2b-1a0f9e8d7c6b",
    request_id: REQUEST_ID,
    thread_id: THREAD_ID,
    status: "proposed",
    draft: {
        title: "UNOnext Modbus address range unclear",
        body: "Customer asks where addresses start.",
    },
    approver_id: null,
    created_at: "2026-09-27T18:00:00+00:00",
};

const DOCUMENTS_FOR_ROLE: Record<string, number> = { support: 3, engineer: 5, admin: 5 };

// The top bar calls these on every page, so every App test needs them.
export function shellRoutes(): Route[] {
    return [
        {
            method: "GET",
            path: "/budget",
            respond: () =>
                json({ spent_usd: 0.12, cap_usd: 3, resets_at: "2026-09-28T00:00:00+00:00" }),
        },
        {
            method: "GET",
            path: "/documents",
            respond: (request) => {
                const role = request.headers.get("X-Demo-Role") ?? "support";
                const count = DOCUMENTS_FOR_ROLE[role] ?? 0;
                return json(
                    Array.from({ length: count }, (_, index) => ({
                        id: `doc-${index}`,
                        title: `Document ${index}`,
                        source_url: `https://example.com/${index}.pdf`,
                        product: "product",
                        doc_type: "catalog",
                    })),
                );
            },
        },
    ];
}
