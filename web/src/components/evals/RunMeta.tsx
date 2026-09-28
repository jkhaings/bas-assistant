import type { EvalRun } from "../../api/types";

type Props = { run: EvalRun; runAt: string };

export function RunMeta({ run, runAt }: Props) {
    const when = new Date(runAt).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    });
    return (
        <p className="text-xs text-stone-500">
            Run {when} · corpus {run.corpus_version} · prompt{" "}
            <code className="font-mono">{run.prompt_version}</code> · cost $
            {Number(run.cost_usd).toFixed(4)}
        </p>
    );
}
