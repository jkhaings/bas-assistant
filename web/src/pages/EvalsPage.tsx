import { useEffect, useState, type ReactNode } from "react";
import { useApi } from "../api/context";
import { settle, type Settled } from "../api/settle";
import type { EvalRun } from "../api/types";
import { GoldenSection } from "../components/evals/GoldenSection";
import { MetricGlossary } from "../components/evals/MetricGlossary";
import { RedteamSection } from "../components/evals/RedteamSection";
import { PageHeader } from "../components/PageHeader";

type LatestRuns = { golden: EvalRun | null; redteam: EvalRun | null };

function Section({ title, children }: { title: string; children: ReactNode }) {
    return (
        <section aria-label={title} className="space-y-3">
            <h2 className="text-base font-semibold">{title}</h2>
            {children}
        </section>
    );
}

export function EvalsPage() {
    const client = useApi();
    const [latest, setLatest] = useState<Settled<LatestRuns> | null>(null);

    useEffect(() => {
        void settle(client.GET("/evals/latest")).then(setLatest);
    }, [client]);

    return (
        <div className="space-y-8">
            <PageHeader title="Evals">
                The most recent golden-set run with its RAGAS scores, and the most recent red-team
                run.
            </PageHeader>
            {latest === null && <p className="text-sm text-stone-500">Loading eval runs</p>}
            {latest && !latest.ok && (
                <p role="alert" className="text-sm text-red-700">
                    {latest.message}
                </p>
            )}
            {latest?.ok && (
                <>
                    <Section title="Golden set">
                        <GoldenSection run={latest.data.golden} />
                    </Section>
                    <Section title="Red team">
                        <RedteamSection run={latest.data.redteam} />
                    </Section>
                </>
            )}
            <Section title="What the numbers mean">
                <MetricGlossary />
            </Section>
        </div>
    );
}
