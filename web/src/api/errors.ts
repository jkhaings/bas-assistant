import { LIMIT_REASONS, type LimitDetail, type LimitReason } from "./types";

export const GENERIC_ERROR = "Something went wrong. Please try again.";
export const NETWORK_ERROR = "Could not reach the server. Check your connection and try again.";

export function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isLimitReason(value: unknown): value is LimitReason {
    return LIMIT_REASONS.some((reason) => reason === value);
}

function asLimitDetail(value: unknown): LimitDetail | null {
    if (!isRecord(value)) return null;
    const { reason, message, resets_at } = value;
    if (!isLimitReason(reason) || typeof message !== "string") return null;
    return { reason, message, resets_at: typeof resets_at === "string" ? resets_at : null };
}

// HTTP errors wrap the limit in `detail`; the stream's error event sends it bare.
export function limitDetailOf(error: unknown): LimitDetail | null {
    if (isRecord(error) && "detail" in error) return asLimitDetail(error.detail);
    return asLimitDetail(error);
}

function capitalize(text: string): string {
    return text.charAt(0).toUpperCase() + text.slice(1);
}

function describeValidationItem(item: unknown): string | null {
    if (!isRecord(item) || typeof item.msg !== "string") return null;
    const field = Array.isArray(item.loc) ? item.loc.at(-1) : undefined;
    return typeof field === "string" && field !== "body" ? `${field}: ${item.msg}` : item.msg;
}

function describeValidation(items: unknown[]): string {
    const messages = items.map(describeValidationItem).filter((text) => text !== null);
    return messages.length > 0 ? capitalize(messages.join("; ")) : GENERIC_ERROR;
}

export function describeError(error: unknown): string {
    // fetch rejects (TypeError) only when the request never got a response.
    if (error instanceof Error) return NETWORK_ERROR;
    const limit = limitDetailOf(error);
    if (limit) return limit.message;
    if (!isRecord(error)) return GENERIC_ERROR;
    const { detail } = error;
    if (typeof detail === "string") return capitalize(detail);
    if (Array.isArray(detail)) return describeValidation(detail);
    return GENERIC_ERROR;
}
