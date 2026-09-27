import type { AskResponse } from "../../api/types";
import { CitationCard } from "./CitationCard";
import { CostToggle } from "./CostToggle";
import { DecisionBadge } from "./DecisionBadge";
import { FeedbackControl } from "./FeedbackControl";
import { FlagControl } from "./FlagControl";

function routeLine({ route, model }: AskResponse): string {
    return [route && `route ${route}`, model && `model ${model}`].filter(Boolean).join(" · ");
}

function TicketCallout({ ticketId }: { ticketId: string | null }) {
    return (
        <p className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">
            Ticket proposed (id <code className="font-mono text-xs">{ticketId ?? "pending"}</code>).
            It waits for an admin to approve it on the{" "}
            <a href="#/approvals" className="font-medium underline">
                Approvals tab
            </a>
            .
        </p>
    );
}

export function AnswerView({ response }: { response: AskResponse }) {
    return (
        <div className="space-y-4 rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
                <DecisionBadge decision={response.decision} />
                {response.cache_hit && (
                    <span className="rounded-full border border-stone-300 bg-stone-100 px-2 py-0.5 text-xs font-medium text-stone-700">
                        cached
                    </span>
                )}
                <span className="text-xs text-stone-500">{routeLine(response)}</span>
            </div>
            <p className="leading-relaxed whitespace-pre-wrap text-stone-900">{response.answer}</p>
            {response.decision === "paused" && <TicketCallout ticketId={response.ticket_id} />}
            {response.notes.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-xs text-stone-600">
                    {response.notes.map((note) => (
                        <li key={note}>{note}</li>
                    ))}
                </ul>
            )}
            {response.citations.length > 0 && (
                <section aria-label="Sources">
                    <h3 className="mb-2 text-xs font-semibold tracking-wide text-stone-500 uppercase">
                        Sources
                    </h3>
                    <ul className="grid gap-2 md:grid-cols-2">
                        {response.citations.map((citation) => (
                            <CitationCard key={citation.chunk_id} citation={citation} />
                        ))}
                    </ul>
                </section>
            )}
            <div className="space-y-3 border-t border-stone-100 pt-3">
                <FeedbackControl requestId={response.request_id} />
                <FlagControl requestId={response.request_id} />
                <CostToggle requestId={response.request_id} />
            </div>
        </div>
    );
}
