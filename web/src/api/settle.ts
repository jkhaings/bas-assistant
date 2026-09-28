import { describeError } from "./errors";

export type Settled<T> =
    { ok: true; data: T } | { ok: false; status: number | null; message: string };

type FetchResult<T> = { data?: T; error?: unknown; response: Response };

// One place that turns an openapi-fetch call, including a network failure, into data or a
// message the page can show as-is.
export async function settle<T>(call: Promise<FetchResult<T>>): Promise<Settled<T>> {
    try {
        const { data, error, response } = await call;
        // openapi-fetch fills `data` for every ok response (undefined only for 204).
        if (response.ok) return { ok: true, data: data as T };
        return { ok: false, status: response.status, message: describeError(error) };
    } catch (error) {
        return { ok: false, status: null, message: describeError(error) };
    }
}
