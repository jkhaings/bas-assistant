import type { ReactNode } from "react";

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
    return (
        <section aria-labelledby={id} className="space-y-4">
            <h2 id={id} className="text-2xl font-semibold tracking-tight text-stone-900">
                {title}
            </h2>
            {children}
        </section>
    );
}

export function HowIBuiltThis() {
    return (
        <article className="mx-auto max-w-3xl space-y-12 pb-8 text-base leading-relaxed text-stone-800">
            <header className="space-y-3">
                <h1 className="text-3xl font-semibold tracking-tight text-stone-900">
                    How I built this
                </h1>
                <p className="text-lg text-stone-600">
                    A support assistant that answers only from public product documentation, cites
                    the page, abstains when the documents are silent, and never files a ticket
                    without a person saying yes.
                </p>
            </header>

            <Section id="the-problem" title="The problem">
                <p>
                    Who asks product questions, where the answers live today, and what a wrong
                    answer costs.
                </p>
            </Section>

            <Section id="twenty-questions" title="The twenty questions">
                <p>The questions the assistant has to get right, and how each one is checked.</p>
            </Section>

            <Section id="request-path" title="The request path and the four fences">
                <p>What happens between pressing Ask and seeing a cited answer.</p>
            </Section>

            <Section id="langgraph" title="Why LangGraph, and what the human gate does">
                <p>
                    Why the agent is a graph with a checkpoint, and where a person has to approve.
                </p>
            </Section>

            <Section id="cost" title="How cost is metered and capped">
                <p>How every model call is priced, recorded, and stopped at the daily cap.</p>
            </Section>

            <Section id="evals" title="What the evals and the red team showed">
                <p>
                    What the golden set, RAGAS and the attacks found, and what changed because of
                    them.
                </p>
            </Section>

            <Section id="inside-a-company" title="What would change inside a company">
                <p>
                    Single sign-on, private documents, a real ticket system, and who owns the evals.
                </p>
            </Section>

            <Section id="weaknesses" title="What it does badly">
                <p>The known gaps, stated plainly.</p>
            </Section>

            <footer className="border-t border-stone-200 pt-6">
                <p>
                    The code is on{" "}
                    <a
                        href="https://github.com/jkhaings/bas-assistant"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-accent hover:underline"
                    >
                        github.com/jkhaings/bas-assistant
                    </a>
                    .
                </p>
            </footer>
        </article>
    );
}
