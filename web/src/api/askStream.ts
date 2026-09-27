import { createParser, type EventSourceMessage } from "eventsource-parser";
import type { ApiClient } from "./client";
import { GENERIC_ERROR, describeError, isRecord } from "./errors";
import { settle } from "./settle";
import type { AskResponse } from "./types";

export type AskOutcome =
    { kind: "answer"; response: AskResponse } | { kind: "error"; message: string };

type AskBody = { question: string; thread_id: string | null };

// A stream that closes without an answer or error event means the server failed mid-turn.
const NO_ANSWER: AskOutcome = { kind: "error", message: GENERIC_ERROR };

function outcomeOf(message: EventSourceMessage, onNode: (node: string) => void): AskOutcome | null {
    const payload: unknown = JSON.parse(message.data);
    if (message.event === "node" && isRecord(payload) && typeof payload.node === "string") {
        onNode(payload.node);
        return null;
    }
    // The answer event carries AskResponse exactly; the OpenAPI schema cannot type SSE payloads.
    if (message.event === "answer") return { kind: "answer", response: payload as AskResponse };
    if (message.event === "error") {
        return { kind: "error", message: describeError(payload) };
    }
    return null;
}

async function readOutcome(
    stream: ReadableStream<Uint8Array>,
    onNode: (node: string) => void,
): Promise<AskOutcome> {
    let outcome = NO_ANSWER;
    const parser = createParser({
        onEvent: (message) => {
            outcome = outcomeOf(message, onNode) ?? outcome;
        },
    });
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    for (let chunk = await reader.read(); !chunk.done; chunk = await reader.read()) {
        parser.feed(decoder.decode(chunk.value, { stream: true }));
    }
    return outcome;
}

export async function askStream(
    client: ApiClient,
    body: AskBody,
    onNode: (node: string) => void,
): Promise<AskOutcome> {
    const result = await settle(client.POST("/ask/stream", { body, parseAs: "stream" }));
    if (!result.ok) return { kind: "error", message: result.message };
    if (!result.data) return NO_ANSWER;
    return readOutcome(result.data, onNode).catch(() => NO_ANSWER);
}
