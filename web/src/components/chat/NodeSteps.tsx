type Props = { steps: string[]; running: boolean };

export function NodeSteps({ steps, running }: Props) {
    if (!running && steps.length === 0) return null;
    return (
        <div className="flex flex-wrap items-center gap-2 text-xs text-stone-500">
            {running && (
                <span aria-hidden="true" className="size-2 animate-pulse rounded-full bg-accent" />
            )}
            <span>{running ? "Working:" : "Path:"}</span>
            <ol aria-label="Graph steps" className="flex flex-wrap items-center gap-1">
                {steps.map((step, index) => (
                    <li key={`${index}-${step}`} className="flex items-center gap-1">
                        {index > 0 && <span aria-hidden="true">&rarr;</span>}
                        <span className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-stone-700">
                            {step}
                        </span>
                    </li>
                ))}
            </ol>
        </div>
    );
}
