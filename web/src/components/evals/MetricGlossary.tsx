const METRICS = [
    {
        term: "Faithfulness",
        meaning: "The share of the answer's claims that the retrieved passages support.",
    },
    {
        term: "Answer relevancy",
        meaning: "How directly the answer addresses the question that was asked.",
    },
    {
        term: "Context precision",
        meaning: "Whether the passages that matter are ranked near the top of what was retrieved.",
    },
    {
        term: "Context recall",
        meaning: "Whether the retrieved passages contain the fact the expected answer needs.",
    },
    {
        term: "Golden pass rate",
        meaning:
            "The twenty questions: the right document is cited, the assistant abstains where it must, and engineer-only material stays blocked for Support.",
    },
    {
        term: "Red team",
        meaning:
            "Attacks that must be refused or neutralized. Each one has to leave an audit row behind.",
    },
];

export function MetricGlossary() {
    return (
        <div className="space-y-4">
            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[12rem_1fr]">
                {METRICS.map(({ term, meaning }) => (
                    <div key={term} className="contents">
                        <dt className="text-sm font-semibold text-stone-800">{term}</dt>
                        <dd className="text-sm text-stone-600">{meaning}</dd>
                    </div>
                ))}
            </dl>
            <p className="rounded-md border border-stone-200 bg-stone-100 px-3 py-2 text-sm text-stone-700">
                The judge is gpt-4o-mini (the <code className="font-mono">fast</code> alias) and
                each category has only 2 to 3 answered questions, so treat these numbers as noisy.
            </p>
        </div>
    );
}
