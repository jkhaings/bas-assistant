import { RUN } from "./run";

export function KnownProblems() {
    return (
        <section aria-labelledby="known-problems" className="space-y-4">
            <h2
                id="known-problems"
                className="text-2xl font-semibold tracking-tight text-stone-900"
            >
                Known problems
            </h2>
            <ul className="list-disc space-y-2 pl-6">
                <li>
                    Protocol questions score {RUN.protocolFaithfulness} on faithfulness: the
                    answer model sees each section's document title, but the judge sees only the
                    section text, which never names the product, so it marks correct answers as
                    unsupported.
                </li>
                <li>
                    Sibling products share catalog-sheet sections word for word, so the same
                    section from two or three related controllers can crowd the top five.
                </li>
                <li>
                    A fault report that no document covers can't become a ticket, because search
                    stops it before the answer model, which is the step that drafts tickets.
                </li>
                <li>
                    {RUN.forbiddenPdfs} catalog PDFs on Delta Controls' site now return 403,
                    meaning access denied, so they are not in the corpus.
                </li>
            </ul>
        </section>
    );
}
