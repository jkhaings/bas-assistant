import { asGoldenScores } from "../../api/evalScores";
import type { EvalRun } from "../../api/types";
import { RagasTable } from "./RagasTable";
import { RunMeta } from "./RunMeta";

export function GoldenSection({ run }: { run: EvalRun | null }) {
    if (!run)
        return <p className="text-sm text-stone-500">No golden-set run has been recorded yet.</p>;
    const scores = asGoldenScores(run.scores);
    if (!scores)
        return (
            <p className="text-sm text-stone-500">
                This run's scores are in a shape this page does not read.
            </p>
        );
    const { passed, total, rate } = scores.golden;
    const failures = Object.entries(scores.failures);
    return (
        <div className="space-y-4">
            <div className="space-y-1">
                <p className="text-2xl font-semibold tabular-nums">
                    {passed}/{total} ({Math.round(rate * 100)}%)
                </p>
                <RunMeta run={run} runAt={scores.run_at} />
            </div>
            {failures.length > 0 && (
                <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm">
                    <p className="font-medium text-red-800">Failures</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-red-800">
                        {failures.map(([question, reason]) => (
                            <li key={question}>
                                <span className="font-mono">{question}</span>: {reason}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
            <RagasTable byCategory={scores.by_category} overall={scores.overall} />
        </div>
    );
}
