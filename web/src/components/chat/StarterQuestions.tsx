const STARTERS = [
    "How many inputs and outputs does the eZNT-T331 network thermostat have?",
    "What is the power draw of the Red5-PLUS-1180?",
    "What browsers does enteliWEB support?",
    "What Modbus slave address does the UNOnext start from?",
];

type Props = { busy: boolean; onPick: (question: string) => void };

export function StarterQuestions({ busy, onPick }: Props) {
    return (
        <section
            aria-labelledby="starters-heading"
            className="rounded-lg border border-dashed border-stone-300 p-4"
        >
            <h2 id="starters-heading" className="text-sm font-semibold text-stone-700">
                Try a question
            </h2>
            <p className="mt-1 text-xs text-stone-500">
                The last one comes from an engineer-only document, so Support gets an abstain.
            </p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {STARTERS.map((question) => (
                    <li key={question}>
                        <button
                            type="button"
                            disabled={busy}
                            onClick={() => onPick(question)}
                            className="h-full w-full rounded-md border border-stone-200 bg-white px-3 py-2 text-left text-sm text-stone-700 hover:border-accent-line hover:bg-accent-soft disabled:opacity-50"
                        >
                            {question}
                        </button>
                    </li>
                ))}
            </ul>
        </section>
    );
}
