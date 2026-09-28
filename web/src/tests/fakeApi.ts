import { vi } from "vitest";

type Respond = (request: Request) => Response | Promise<Response>;
export type Route = { method: string; path: string | RegExp; respond: Respond };
export type RecordedCall = { method: string; path: string; headers: Headers; body: unknown };

function matches(route: Route, method: string, path: string): boolean {
    if (route.method !== method) return false;
    return typeof route.path === "string" ? route.path === path : route.path.test(path);
}

// Stubs global fetch with a router over method and path, and records every call it serves.
export function stubApi(routes: Route[]): RecordedCall[] {
    const calls: RecordedCall[] = [];
    vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
        const request =
            input instanceof Request
                ? input
                : new Request(new URL(String(input), window.location.origin), init);
        const path = new URL(request.url).pathname;
        const text = await request.clone().text();
        calls.push({
            method: request.method,
            path,
            headers: request.headers,
            body: text ? JSON.parse(text) : null,
        });
        const route = routes.find((candidate) => matches(candidate, request.method, path));
        return route ? route.respond(request) : json({ detail: "Not Found" }, 404);
    });
    return calls;
}

export function json(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}

export function noContent(): Response {
    return new Response(null, { status: 204 });
}

export function sseEvent(event: string, data: unknown): string {
    return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export function sse(...frames: string[]): Response {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
        start(controller) {
            for (const frame of frames) controller.enqueue(encoder.encode(frame));
            controller.close();
        },
    });
    return new Response(body, { headers: { "Content-Type": "text/event-stream" } });
}
