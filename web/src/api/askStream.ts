import { EventSourceParserStream, type EventSourceMessage } from "eventsource-parser/stream";
import type { ApiClient } from "./client";
import { GENERIC_ERROR, describeError } from "./errors";
import { isRecord } from "./guards";
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
    stream: ReadableStream<Uint8Array<ArrayBuffer>>,
    onNode: (node: string) => void,
): Promise<AskOutcome> {
    // A reader rather than `for await`: Safari cannot async-iterate a ReadableStream.
    const events = stream
        .pipeThrough(new TextDecoderStream())
        .pipeThrough(new EventSourceParserStream())
        .getReader();
    let outcome = NO_ANSWER;
    for (let next = await events.read(); !next.done; next = await events.read()) {
        outcome = outcomeOf(next.value, onNode) ?? outcome;
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
