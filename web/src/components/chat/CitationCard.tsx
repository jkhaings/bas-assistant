import type { Citation } from "../../api/types";

// Browser PDF viewers honour #page=N, so a PDF link lands on the cited page.
function sourceHref({ source_url, page }: Citation): string {
    return /\.pdf$/i.test(source_url) ? `${source_url}#page=${page}` : source_url;
}

export function CitationCard({ citation }: { citation: Citation }) {
    return (
        <li className="rounded-md border border-stone-200 bg-stone-50 p-3">
            <div className="flex items-baseline justify-between gap-3">
                <a
                    href={sourceHref(citation)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-accent hover:underline"
                >
                    {citation.document_title}
                    <span className="sr-only"> (opens in a new tab)</span>
                </a>
                <span className="shrink-0 text-xs text-stone-500">p. {citation.page}</span>
            </div>
            <p className="mt-1 text-sm text-stone-600">{citation.snippet}</p>
        </li>
    );
}
