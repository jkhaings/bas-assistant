import { asRedteamScores } from "../../api/evalScores";
import type { EvalRun } from "../../api/types";
import { RunMeta } from "./RunMeta";

function caseSentence(testName: string): string {
    const words = testName.replace(/^test_/, "").replaceAll("_", " ");
    return words.charAt(0).toUpperCase() + words.slice(1);
}

export function RedteamSection({ run }: { run: EvalRun | null }) {
    if (!run)
        return <p className="text-sm text-stone-500">No red-team run has been recorded yet.</p>;
    const scores = asRedteamScores(run.scores);
    if (!scores)
        return (
            <p className="text-sm text-stone-500">
                This run's scores are in a shape this page does not read.
            </p>
        );
    return (
        <div className="space-y-4">
            <div className="space-y-1">
                <p className="text-2xl font-semibold tabular-nums">
                    {scores.passed}/{scores.total} passed
                </p>
                <RunMeta run={run} runAt={scores.run_at} />
            </div>
            <ul className="divide-y divide-stone-100 rounded-lg border border-stone-200 bg-white">
                {Object.entries(scores.cases).map(([name, result]) => {
                    const passed = result === "passed";
                    const tone = passed
                        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                        : "border-red-300 bg-red-50 text-red-800";
                    return (
                        <li
                            key={name}
                            className="flex items-start justify-between gap-3 px-3 py-2 text-sm"
                        >
                            <span>{caseSentence(name)}</span>
                            <span
                                className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${tone}`}
                            >
                                {result}
                            </span>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}
