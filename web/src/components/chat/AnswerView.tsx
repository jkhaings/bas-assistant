import type { AskResponse, Citation, Decision } from "../../api/types";
import { CitationCard } from "./CitationCard";
import { CostToggle } from "./CostToggle";
import { DecisionBadge } from "./DecisionBadge";
import { FlagControl } from "./FlagControl";

function routeLine({ route, model }: AskResponse): string {
    return [route && `route ${route}`, model && `model ${model}`].filter(Boolean).join(" · ");
}

// The ticket flow stays off the chat: a gated turn shows as the graph will close it, answered
// when it cites a passage (the validator requires one for an answer) and abstained otherwise.
function shownDecision({ decision, citations }: AskResponse): Decision {
    if (decision !== "paused") return decision;
    return citations.length > 0 ? "answered" : "abstained";
}

// The graph's only note is the one for a ticket suggested to a role that cannot file it.
// TODO(post-weekend): AskResponse has no needs_ticket flag, so this reads approval_required and
// the notes, and an unanswerable paused turn still shows the graph's ticket wording
// (HANDOFF_ui-simple.md, Known gaps).
function flaggedForFollowUp({ approval_required, notes }: AskResponse): boolean {
    return approval_required || notes.length > 0;
}

function Sources({ citations }: { citations: Citation[] }) {
    return (
        <section aria-label="Sources">
            <h3 className="mb-2 text-xs font-semibold tracking-wide text-stone-500 uppercase">
                Sources
            </h3>
            <ul className="grid gap-2 md:grid-cols-2">
                {citations.map((citation) => (
                    <CitationCard key={citation.chunk_id} citation={citation} />
                ))}
            </ul>
        </section>
    );
}

export function AnswerView({ response }: { response: AskResponse }) {
    return (
        <div className="space-y-4 rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
                <DecisionBadge decision={shownDecision(response)} />
                {response.cache_hit && (
                    <span className="rounded-full border border-stone-300 bg-stone-100 px-2 py-0.5 text-xs font-medium text-stone-700">
                        cached
                    </span>
                )}
                <span className="text-xs text-stone-500">{routeLine(response)}</span>
            </div>
            <p className="leading-relaxed whitespace-pre-wrap text-stone-900">{response.answer}</p>
            {flaggedForFollowUp(response) && (
                <p className="text-xs text-stone-500">Flagged for follow-up</p>
            )}
            {response.citations.length > 0 && <Sources citations={response.citations} />}
            <div className="space-y-3 border-t border-stone-100 pt-3">
                <FlagControl requestId={response.request_id} />
                <CostToggle requestId={response.request_id} />
            </div>
        </div>
    );
}
