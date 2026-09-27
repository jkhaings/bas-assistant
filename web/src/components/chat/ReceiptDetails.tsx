import type { Receipt } from "../../api/types";

function ms(value: number | null): string {
    return value === null ? "–" : `${Math.round(value).toLocaleString()} ms`;
}

function usd(value: number): string {
    return `$${value.toFixed(6)}`;
}

const CELL = "px-2 py-1 text-left whitespace-nowrap";

export function ReceiptDetails({ receipt }: { receipt: Receipt }) {
    return (
        <div className="space-y-3">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
                <dt className="text-stone-500">Route</dt>
                <dd>{receipt.route ?? "–"}</dd>
                <dt className="text-stone-500">Model</dt>
                <dd>{receipt.model ?? "–"}</dd>
                <dt className="text-stone-500">Tokens</dt>
                <dd>
                    {receipt.input_tokens.toLocaleString()} in /{" "}
                    {receipt.output_tokens.toLocaleString()} out (
                    {receipt.cached_tokens.toLocaleString()} cached)
                </dd>
                <dt className="text-stone-500">Cost</dt>
                <dd className="font-medium">{usd(receipt.usd)}</dd>
                <dt className="text-stone-500">Time</dt>
                <dd>
                    retrieval {ms(receipt.retrieval_ms)}, rerank {ms(receipt.rerank_ms)}, model{" "}
                    {ms(receipt.model_ms)}, total {ms(receipt.total_ms)}
                </dd>
                <dt className="text-stone-500">Cache hit</dt>
                <dd>{receipt.cache_hit ? "yes" : "no"}</dd>
            </dl>
            <div className="overflow-x-auto">
                <table className="w-full text-xs">
                    <caption className="sr-only">Model calls for this answer</caption>
                    <thead className="border-b border-stone-200 text-stone-500">
                        <tr>
                            <th className={CELL}>Stage</th>
                            <th className={CELL}>Model</th>
                            <th className={CELL}>Tokens in / out</th>
                            <th className={CELL}>USD</th>
                            <th className={CELL}>Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        {receipt.calls.map((call, index) => (
                            <tr
                                key={`${index}-${call.stage}`}
                                className="border-b border-stone-100"
                            >
                                <td className={CELL}>{call.stage}</td>
                                <td className={CELL}>{call.model}</td>
                                <td className={CELL}>
                                    {call.input_tokens.toLocaleString()} /{" "}
                                    {call.output_tokens.toLocaleString()}
                                </td>
                                <td className={CELL}>{usd(call.usd)}</td>
                                <td className={CELL}>{ms(call.latency_ms)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
