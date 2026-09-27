import { Figure } from "../../components/Figure";
import { RUN } from "./run";
import { Section } from "./Section";

export function Cost() {
    return (
        <Section id="cost" title="How cost is metered and capped">
            <p>
                Every model call goes through a LiteLLM proxy with three aliases: fast
                (gpt-4o-mini), strong (Claude Sonnet) and embed. That covers the router, the
                query embedding, the answer and the evaluation judge. The proxy reports each
                call's cost, and the app writes one usage row per call. "Show cost" under an
                answer is that receipt.
            </p>
            <p>
                On the live run, a simple answer cost about {RUN.simpleAnswerUsd} and a complex
                one about {RUN.complexAnswerUsd}. A repeated question costs nothing, and an
                abstain costs only the router call and the query embedding, about{" "}
                {RUN.abstainUsd}. A full evaluation
                run, 22 questions plus the RAGAS judge, cost about {RUN.evalRunUsd}.
            </p>
            <p>The controls, from the cheapest to the bluntest:</p>
            <ul className="list-disc space-y-1 pl-6">
                <li>
                    An exact-match cache. Its key includes a corpus version that moves when the
                    documents change.
                </li>
                <li>Routing: simple questions never reach the strong model.</li>
                <li>A per-role daily allowance and a per-visitor rate limit.</li>
                <li>
                    A global daily cap of {RUN.dailyCapUsd}. When it is reached, the demo
                    pauses with a banner until midnight UTC.
                </li>
                <li>Budgets on the proxy's keys, and hard limits in each vendor's console.</li>
            </ul>
            <Figure
                src="/img/grafana-budget.png"
                alt="Grafana Budget dashboard: spend today against the cap, cost per answer, cost by model and stage"
                caption="The Budget dashboard on the Dashboards tab, after the live evaluation run."
            />
        </Section>
    );
}
